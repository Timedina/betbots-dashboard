#!/usr/bin/env python3
"""
Backtest automatizado do bot LAY Correct Score.
Roda diariamente via cron, processa reprovacoes das ultimas 48h,
salva resultados no Supabase (tabela backtest_resultados).
"""
import os
import sys
import json
from datetime import datetime, timedelta, timezone

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

JANELA_HORAS = 48

ATUAL = {
    "RAZAO_ODD_MAXIMA": 1.8,
    "ODD_01_MINIMA": 5.0,
    "ODD_01_MAXIMA": 20.0,
    "LIQUIDEZ_MINIMA_CS_DISPONIVEL": 150.0,
}

CENARIOS = {
    "razao_2.2": {**ATUAL, "RAZAO_ODD_MAXIMA": 2.2},
    "odd01_max_25": {**ATUAL, "ODD_01_MAXIMA": 25.0},
    "liquidez_min_75": {**ATUAL, "LIQUIDEZ_MINIMA_CS_DISPONIVEL": 75.0},
    "odd01_min_3.5": {**ATUAL, "ODD_01_MINIMA": 3.5},
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


def calcular_pnl_lay(placar_final, odd_01, odd_10, liability=100.0, comissao=0.0636):
    if odd_10 and odd_10 > odd_01:
        return None, "bloqueado_por_outro_filtro"
    placar_lay = "0 - 1"
    odd_lay = odd_01
    if odd_lay <= 1:
        return None, "odd_invalida"
    stake = liability / (odd_lay - 1)
    if placar_final == placar_lay:
        return -liability, "PERDA"
    return round(stake * (1 - comissao), 2), "VITORIA"


def elegivel_cenario(a, cenario):
    odd_01 = a.get("odd_01")
    odd_10 = a.get("odd_10")
    liq = a.get("liquidez_disponivel")
    if odd_01 is None:
        return False
    odd_01 = float(odd_01)
    odd_10 = float(odd_10) if odd_10 is not None else 0
    liq = float(liq) if liq is not None else 0

    if not (cenario["ODD_01_MINIMA"] <= odd_01 <= cenario["ODD_01_MAXIMA"]):
        return False
    if odd_10 and odd_10 > odd_01:
        return False
    if liq < cenario["LIQUIDEZ_MINIMA_CS_DISPONIVEL"]:
        return False
    if odd_10 and odd_10 > 0:
        razao = odd_01 / odd_10
        if razao > cenario["RAZAO_ODD_MAXIMA"]:
            return False
    return True


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERRO: SUPABASE_URL/SUPABASE_KEY nao encontrados no .env")
        return

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    limite = (datetime.now(timezone.utc) - timedelta(hours=JANELA_HORAS)).isoformat()
    print(f"[{datetime.now()}] Buscando reprovacoes desde {limite}...")

    reprovadas = []
    pagina = 0
    while True:
        inicio = pagina * 1000
        fim = inicio + 999
        resp = (sb.table("analises")
                .select("*")
                .eq("bot_id", BOT_ID_LAY)
                .eq("aprovado", False)
                .not_.is_("odd_01", "null")
                .gte("analisado_em", limite)
                .range(inicio, fim)
                .execute())
        if not resp.data:
            break
        reprovadas.extend(resp.data)
        if len(resp.data) < 1000:
            break
        pagina += 1

    print(f"Reprovacoes na janela de {JANELA_HORAS}h com odd_01 preenchido: {len(reprovadas)}")
    if not reprovadas:
        print("Nada para processar hoje.")
        return

    ja_processados = set()
    resp_existentes = sb.table("backtest_resultados").select("cenario,event_id").execute()
    for row in resp_existentes.data:
        ja_processados.add((row["cenario"], row["event_id"]))

    total_novos = 0
    for nome_cenario, cenario in CENARIOS.items():
        elegiveis = [a for a in reprovadas if elegivel_cenario(a, cenario)]
        pendentes = [a for a in elegiveis if (nome_cenario, a["event_id"]) not in ja_processados]
        print(f"  Cenario '{nome_cenario}': {len(elegiveis)} elegiveis | {len(pendentes)} novos a processar")

        for a in pendentes:
            event_id = a["event_id"]
            nome = a.get("nome_jogo")
            odd_01 = float(a["odd_01"])
            odd_10 = float(a["odd_10"]) if a.get("odd_10") else 0
            liq = a.get("liquidez_disponivel")
            market_id_cs = a.get("market_id_cs")
            runners_cs_map = a.get("runners_cs_map") or {}
            placar, status = buscar_placar_final(market_id_cs, runners_cs_map)
            if not placar:
                print(f"    [SKIP] {nome} - {status}")
                continue
            pnl, resultado = calcular_pnl_lay(placar, odd_01, odd_10)
            if pnl is None:
                continue
            try:
                sb.table("backtest_resultados").insert({
                    "bot_id": BOT_ID_LAY,
                    "cenario": nome_cenario,
                    "event_id": event_id,
                    "nome_jogo": nome,
                    "odd_01": odd_01,
                    "odd_10": odd_10,
                    "liquidez_disponivel": liq,
                    "placar_final": placar,
                    "resultado": resultado,
                    "pnl": pnl,
                }).execute()
                total_novos += 1
                print(f"    [SALVO] {nome} | {resultado} | pnl={pnl:+.2f}u")
            except Exception as e:
                print(f"    [ERRO ao salvar] {nome}: {e}")

    print(f"\nTotal de novos resultados salvos nesta execucao: {total_novos}")

    print("\n=== RESUMO ACUMULADO POR CENARIO ===")
    resp_resumo = sb.table("backtest_resultados").select("cenario,pnl,resultado").execute()
    from collections import defaultdict
    agregados = defaultdict(list)
    for row in resp_resumo.data:
        agregados[row["cenario"]].append(row)
    for nome_cenario, rows in agregados.items():
        total = sum(float(r["pnl"]) for r in rows)
        vit = sum(1 for r in rows if r["resultado"] == "VITORIA")
        der = sum(1 for r in rows if r["resultado"] == "PERDA")
        print(f"  {nome_cenario}: {len(rows)} jogos | {vit}V/{der}D | PnL acumulado: {total:+.2f}u")


if __name__ == "__main__":
    main()
