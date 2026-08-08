#!/usr/bin/env python3
"""
Backtest do bot LAY Correct Score.

Le as analises reprovadas no Supabase (que tem odd_01, odd_10, liquidez salvos),
simula filtros alternativos (ex: razao maxima diferente, faixa de odd_01 diferente)
e, para os jogos que passariam a ser aprovados, busca o placar final na Betfair
para calcular o PnL que teria ocorrido.

Uso:
    python3 backtest_lay.py
"""
import os
import sys
import json

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


def buscar_placar_final(event_id: str):
    mercados = bf.listar_mercados(event_id, tipos=["CORRECT_SCORE"])
    if not mercados:
        return None, "sem_mercado_cs"
    market_id = mercados[0]["marketId"]
    runners_map = {r["selectionId"]: r["runnerName"] for r in mercados[0].get("runners", [])}
    rpc = json.dumps({
        "jsonrpc": "2.0",
        "method": "SportsAPING/v1.0/listMarketBook",
        "params": {"marketIds": [market_id], "priceProjection": {"priceData": []}},
        "id": 1,
    })
    livros = bf.chamar_api(rpc) or []
    if not livros:
        return None, "sem_book"
    book = livros[0]
    if book.get("status") not in ("CLOSED",):
        return None, f"status={book.get('status')}"
    for r in book.get("runners", []):
        if r.get("status") == "WINNER":
            placar = runners_map.get(r.get("selectionId"), f"ID:{r.get('selectionId')}")
            return placar, "ok"
    return None, "sem_vencedor"


def calcular_pnl_lay(placar_final: str, odd_01: float, odd_10: float, liability=100.0, comissao=0.0636):
    if odd_10 and odd_10 > odd_01:
        return None, "filtro_ja_bloquearia_1x0_maior"
    placar_lay = "0 - 1"
    odd_lay = odd_01
    stake = liability / (odd_lay - 1) if odd_lay > 1 else 0
    if placar_final == placar_lay:
        pnl = -liability
        resultado = "PERDA"
    else:
        pnl = round(stake * (1 - comissao), 2)
        resultado = "VITORIA"
    return pnl, resultado


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERRO: SUPABASE_URL/SUPABASE_KEY nao encontrados no .env")
        return

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Buscando analises reprovadas com filtro de razao (via SQL direto no servidor)...")
    resp = sb.table("analises").select("*").eq("bot_id", BOT_ID_LAY).eq("aprovado", False).ilike("motivos", "%Razao odd_01%").execute()
    candidatos_razao_raw = resp.data
    print(f"Reprovacoes com motivo de razao encontradas: {len(candidatos_razao_raw)}")

    candidatos_razao = []
    for a in candidatos_razao_raw:
        if a.get("odd_01") and a.get("odd_10"):
            odd_01 = float(a["odd_01"])
            odd_10 = float(a["odd_10"])
            razao = round(odd_01 / odd_10, 2) if odd_10 else None
            if razao and razao <= 2.2:
                candidatos_razao.append(a)

    print(f"\n=== CENARIO 1: RAZAO_ODD_MAXIMA = 2.2 (atual: 1.8) ===")
    print(f"Jogos que teriam sido aprovados a mais: {len(candidatos_razao)}")

    resultados = []
    for a in candidatos_razao:
        event_id = a.get("event_id")
        nome = a.get("nome_jogo")
        odd_01 = float(a["odd_01"])
        odd_10 = float(a["odd_10"])
        placar, status = buscar_placar_final(event_id)
        if not placar:
            print(f"  [SKIP] {nome} - {status}")
            continue
        pnl, resultado = calcular_pnl_lay(placar, odd_01, odd_10)
        if pnl is None:
            print(f"  [SKIP] {nome} - {resultado}")
            continue
        print(f"  {nome} | odd_01={odd_01} odd_10={odd_10} | placar_final={placar} | {resultado} | pnl={pnl:+.2f}u")
        resultados.append(pnl)

    if resultados:
        total = sum(resultados)
        vitorias = sum(1 for p in resultados if p > 0)
        derrotas = sum(1 for p in resultados if p < 0)
        print(f"\nResumo cenario 1: {len(resultados)} jogos simulados | {vitorias}V/{derrotas}D | PnL total: {total:+.2f}u")
    else:
        print("\nNenhum resultado conclusivo (jogos ainda nao encerrados ou sem mercado disponivel).")


if __name__ == "__main__":
    main()
