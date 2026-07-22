#!/usr/bin/env python3
"""
Backtest do NOVO filtro de sanity-check: odd_favorito (Match Odds) vs odd_10/odd_01 (Correct Score).

Motivacao: em 10/07/2026, o jogo Finn Harps v Treaty United foi aprovado com
odd_favorito=1.04 (favorito esmagador) mas odd_10 == odd_01 == 12.5 (dados de
Correct Score nao refletiram o favoritismo, mercado CS fino/pouco liquido).
O filtro RAZAO_ODD_MAXIMA nao pegou isso porque a razao odd_01/odd_10 deu 1.0,
dentro do limite de 1.8 -- o problema nao era a razao em si, e sim os dados
de odd_10 nao serem confiaveis quando o favorito e muito forte.

NOVO FILTRO: quando odd_favorito <= ODD_FAVORITO_SUSPEITO (favorito muito forte),
exige que odd_10 seja significativamente MENOR que odd_01 (o placar 1-0 do
favorito deveria ser mais provavel = odd de lay mais baixa). Se odd_10/odd_01
> RAZAO_10_01_MAX_FAVORITO_FORTE, os dados de CS sao considerados suspeitos e
o jogo e reprovado.

Roda contra o HISTORICO COMPLETO de analises (aprovadas e reprovadas) do bot
LAY, comparando:
  - cenario "atual": filtros de producao, sem o novo filtro
  - cenario "com_filtro_favorito": filtros atuais + novo filtro de sanity-check

Nao escreve nada no Supabase -- so imprime o comparativo no terminal.
"""
import os
import sys
import json
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, "/home/ubuntu/bot-prelive-betfair")
with open("/home/ubuntu/bot-prelive-betfair/.env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

import betfair_client as bf
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")
BOT_ID_LAY = "7449c515-4a4e-4ad3-acda-32916034e9c1"

# Filtros atuais de producao (espelham bot_prelive.py)
ATUAL = {
    "RAZAO_ODD_MAXIMA": 1.8,
    "ODD_01_MINIMA": 5.0,
    "ODD_01_MAXIMA": 20.0,
    "LIQUIDEZ_MINIMA_CS_DISPONIVEL": 150.0,
}

# Parametros do novo filtro de sanity-check
ODD_FAVORITO_SUSPEITO = 1.15            # abaixo disso, favorito e' considerado "muito forte"
RAZAO_10_01_MAX_FAVORITO_FORTE = 0.75   # odd_10 deve ser <= 75% da odd_01 quando favorito for forte

CENARIOS = {
    "atual": {**ATUAL, "FILTRO_FAVORITO": False},
    "com_filtro_favorito": {**ATUAL, "FILTRO_FAVORITO": True},
}

CACHE_PLACAR = {}


def buscar_placar_final(market_id: str, runners_cs_map: dict = None):
    if not market_id:
        return None, "sem_market_id_salvo"
    if market_id in CACHE_PLACAR:
        return CACHE_PLACAR[market_id]
    runners_cs_map = runners_cs_map or {}
    rpc = json.dumps({
        "jsonrpc": "2.0",
        "method": "SportsAPING/v1.0/listMarketBook",
        "params": {"marketIds": [market_id], "priceProjection": {"priceData": []}},
        "id": 1,
    })
    livros = bf.chamar_api(rpc) or []
    if not livros:
        CACHE_PLACAR[market_id] = (None, "sem_book")
        return CACHE_PLACAR[market_id]
    book = livros[0]
    if book.get("status") != "CLOSED":
        CACHE_PLACAR[market_id] = (None, f"status={book.get('status')}")
        return CACHE_PLACAR[market_id]
    for r in book.get("runners", []):
        if r.get("status") == "WINNER":
            sel_id = r.get("selectionId")
            placar = runners_cs_map.get(str(sel_id)) or runners_cs_map.get(sel_id) or f"ID:{sel_id}"
            CACHE_PLACAR[market_id] = (placar, "ok")
            return CACHE_PLACAR[market_id]
    CACHE_PLACAR[market_id] = (None, "sem_vencedor")
    return CACHE_PLACAR[market_id]


def calcular_pnl_lay(placar_final, odd_01, liability=100.0, comissao=0.0636):
    placar_lay = "0 - 1"
    if odd_01 <= 1:
        return None, "odd_invalida"
    stake = liability / (odd_01 - 1)
    if placar_final == placar_lay:
        return -liability, "PERDA"
    return round(stake * (1 - comissao), 2), "VITORIA"


def elegivel_cenario(a, cenario):
    odd_01 = a.get("odd_01")
    odd_10 = a.get("odd_10")
    odd_favorito = a.get("odd_favorito")
    liq = a.get("liquidez_disponivel")
    if odd_01 is None:
        return False, "sem_odd_01"
    odd_01 = float(odd_01)
    odd_10 = float(odd_10) if odd_10 is not None else 0
    liq = float(liq) if liq is not None else 0

    if not (cenario["ODD_01_MINIMA"] <= odd_01 <= cenario["ODD_01_MAXIMA"]):
        return False, "odd_01_fora_faixa"
    if odd_10 and odd_10 > odd_01:
        return False, "lay_10_mais_caro_que_01"
    if liq < cenario["LIQUIDEZ_MINIMA_CS_DISPONIVEL"]:
        return False, "liquidez_insuficiente"
    if odd_10 and odd_10 > 0:
        razao = odd_01 / odd_10
        if razao > cenario["RAZAO_ODD_MAXIMA"]:
            return False, "razao_odd_alta"

    if cenario["FILTRO_FAVORITO"] and odd_favorito is not None:
        odd_favorito = float(odd_favorito)
        if odd_favorito <= ODD_FAVORITO_SUSPEITO and odd_10 and odd_10 > 0:
            razao_10_01 = odd_10 / odd_01
            if razao_10_01 > RAZAO_10_01_MAX_FAVORITO_FORTE:
                return False, f"dados_cs_suspeitos_favorito_forte(odd_fav={odd_favorito},odd10/01={razao_10_01:.2f})"

    return True, None


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERRO: SUPABASE_URL/SUPABASE_KEY nao encontrados no .env")
        return

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Buscando TODAS as analises com odd_01 preenchido (aprovadas e reprovadas)...")
    todas = []
    pagina = 0
    while True:
        inicio = pagina * 1000
        fim = inicio + 999
        resp = (sb.table("analises")
                .select("*")
                .eq("bot_id", BOT_ID_LAY)
                .not_.is_("odd_01", "null")
                .not_.is_("market_id_cs", "null")
                .range(inicio, fim)
                .execute())
        if not resp.data:
            break
        todas.extend(resp.data)
        if len(resp.data) < 1000:
            break
        pagina += 1

    print(f"Total de analises com odd_01 + market_id_cs: {len(todas)}\n")
    if not todas:
        print("Nada para processar.")
        return

    resultados_por_cenario = defaultdict(list)
    excluidos_pelo_novo_filtro = []

    for nome_cenario, cenario in CENARIOS.items():
        print(f"=== Processando cenario '{nome_cenario}' ===")
        elegiveis = []
        for a in todas:
            ok, motivo = elegivel_cenario(a, cenario)
            if ok:
                elegiveis.append(a)
            elif nome_cenario == "com_filtro_favorito" and motivo and motivo.startswith("dados_cs_suspeitos"):
                excluidos_pelo_novo_filtro.append((a.get("nome_jogo"), a.get("analisado_em"), motivo))

        print(f"  {len(elegiveis)} jogos elegiveis")

        for a in elegiveis:
            nome = a.get("nome_jogo")
            odd_01 = float(a["odd_01"])
            market_id_cs = a.get("market_id_cs")
            runners_cs_map = a.get("runners_cs_map") or {}
            placar, status = buscar_placar_final(market_id_cs, runners_cs_map)
            if not placar:
                continue
            pnl, resultado = calcular_pnl_lay(placar, odd_01)
            if pnl is None:
                continue
            resultados_por_cenario[nome_cenario].append({
                "nome_jogo": nome,
                "resultado": resultado,
                "pnl": pnl,
            })
        print()

    print("\n" + "=" * 70)
    print("RESUMO COMPARATIVO")
    print("=" * 70)
    for nome_cenario in CENARIOS:
        rows = resultados_por_cenario[nome_cenario]
        total = sum(r["pnl"] for r in rows)
        vit = sum(1 for r in rows if r["resultado"] == "VITORIA")
        der = sum(1 for r in rows if r["resultado"] == "PERDA")
        winrate = (vit / len(rows) * 100) if rows else 0
        print(f"\n[{nome_cenario}]")
        print(f"  Jogos liquidados: {len(rows)}")
        print(f"  Vitorias: {vit} | Derrotas: {der} | Win rate: {winrate:.1f}%")
        print(f"  PnL total: {total:+.2f}u")
        if len(rows) > 0:
            print(f"  PnL medio por jogo: {total/len(rows):+.2f}u")

    print("\n" + "=" * 70)
    print(f"Jogos EXCLUIDOS pelo novo filtro (dados CS suspeitos c/ favorito forte): {len(excluidos_pelo_novo_filtro)}")
    print("=" * 70)
    for nome, dt, motivo in excluidos_pelo_novo_filtro:
        print(f"  - {nome} ({dt}): {motivo}")


if __name__ == "__main__":
    main()

