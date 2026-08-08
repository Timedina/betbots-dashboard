#!/usr/bin/env python3
"""
Coleta odds historicas da OddsPapi (Betfair Exchange) para uma lista de fixtures
e grava na tabela historical_odds do Supabase.
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()
import json
import time
import argparse
import requests
from datetime import datetime, timedelta

ODDSPAPI_BASE = "https://api.oddspapi.io/v4"
BOOKMAKERS = "betfair-ex"

MARKET_CORRECT_SCORE = "10336"
OUTCOME_1_0 = "10337"
OUTCOME_0_1 = "10344"

ODD_01_MAXIMA = 20.0
RAZAO_ODD_MAXIMA = 1.8


def passa_filtro_lay(odd_10, odd_01):
    if odd_01 is None or odd_10 is None or odd_01 <= 0:
        return False
    if odd_01 > ODD_01_MAXIMA:
        return False
    razao = odd_10 / odd_01
    return razao <= RAZAO_ODD_MAXIMA


def extract_1x0_0x1_prices(fixture, bookmaker_slug=BOOKMAKERS):
    bm = fixture.get("bookmakerOdds", {}).get(bookmaker_slug, {})
    market = bm.get("markets", {}).get(MARKET_CORRECT_SCORE, {})
    outcomes = market.get("outcomes", {})

    def get_price(outcome_id):
        outcome = outcomes.get(outcome_id, {})
        players = outcome.get("players", {})
        first = players.get("0", {})
        return first.get("price")

    return get_price(OUTCOME_1_0), get_price(OUTCOME_0_1)


def fetch_fixtures_by_tournaments(tournament_ids, api_key):
    url = f"{ODDSPAPI_BASE}/odds-by-tournaments"
    params = {"bookmaker": BOOKMAKERS, "tournamentIds": tournament_ids, "apiKey": api_key}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def chunk_list(items, chunk_size=3):
    for i in range(0, len(items), chunk_size):
        yield items[i:i + chunk_size]


def load_all_tournament_ids(tournaments_json_path, chunk_size=3):
    with open(tournaments_json_path, encoding="utf-8") as f:
        tournaments = json.load(f)
    ids = [str(t["tournamentId"]) for t in tournaments]
    for i in range(0, len(ids), chunk_size):
        yield ids[i:i + chunk_size]


def get_env(name):
    val = os.environ.get(name)
    if not val:
        print(f"ERRO: variavel de ambiente {name} nao definida.", file=sys.stderr)
        sys.exit(1)
    return val


def fetch_historical_odds(fixture_id, outcome_id, api_key):
    url = f"{ODDSPAPI_BASE}/historical-odds"
    params = {"fixtureId": fixture_id, "bookmakers": BOOKMAKERS, "outcomeId": outcome_id, "apiKey": api_key}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_finished_fixtures(tournament_id, date_from, date_to, api_key):
    url = f"{ODDSPAPI_BASE}/fixtures"
    params = {"tournamentId": tournament_id, "from": date_from, "to": date_to, "apiKey": api_key}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    fixtures = resp.json()
    return [fx for fx in fixtures if fx.get("statusId") == 2]


def flatten_response(fixture_id, payload):
    rows = []
    bookmakers = payload.get("bookmakers", payload)
    for bookmaker_slug, bm_data in bookmakers.items():
        markets = bm_data.get("markets", {})
        for market_id, market_data in markets.items():
            outcomes = market_data.get("outcomes", {})
            for outcome_id, outcome_data in outcomes.items():
                players = outcome_data.get("players", {})
                for player_id, records in players.items():
                    record_list = records if isinstance(records, list) else [records]
                    for rec in record_list:
                        exch = rec.get("exchangeMeta") or {}
                        rows.append({
                            "fixture_id": fixture_id,
                            "bookmaker_slug": bookmaker_slug,
                            "market_id": str(market_id),
                            "outcome_id": str(outcome_id),
                            "player_id": str(player_id),
                            "odds_record_id": rec.get("id"),
                            "price": rec.get("price"),
                            "bet_limit": rec.get("limit"),
                            "active": rec.get("active"),
                            "exchange_back": exch.get("back"),
                            "exchange_lay": exch.get("lay"),
                            "odds_created_at": rec.get("createdAt"),
                            "raw_payload": rec,
                        })
    return rows


def upsert_to_supabase(rows, supabase_url, service_key):
    if not rows:
        return
    url = f"{supabase_url}/rest/v1/historical_odds"
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    resp = requests.post(url, headers=headers, json=rows, timeout=30)
    if resp.status_code >= 300:
        print(f"ERRO ao gravar no Supabase: {resp.status_code} - {resp.text}", file=sys.stderr)
    else:
        print(f"OK: {len(rows)} registros enviados para historical_odds.")


def get_fixture_ids_from_table(supabase_url, service_key, table, column, since_hours):
    since = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat()
    url = f"{supabase_url}/rest/v1/{table}"
    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
    params = {"select": column, "created_at": f"gte.{since}"}
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return sorted({row[column] for row in resp.json() if row.get(column)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-ids")
    parser.add_argument("--from-table")
    parser.add_argument("--fixture-column", default="fixture_id")
    parser.add_argument("--since-hours", type=int, default=24)
    parser.add_argument("--tournament-ids")
    parser.add_argument("--all-tournaments")
    parser.add_argument("--finished-tournament")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    args = parser.parse_args()

    api_key = get_env("ODDSPAPI_API_KEY")
    supabase_url = get_env("SUPABASE_URL")
    service_key = get_env("SUPABASE_SERVICE_KEY")

    if args.finished_tournament:
        print(f"Buscando jogos finalizados do torneio {args.finished_tournament} ({args.date_from} a {args.date_to})...")
        fixtures = fetch_finished_fixtures(args.finished_tournament, args.date_from, args.date_to, api_key)
        print(f"{len(fixtures)} jogo(s) finalizado(s) encontrado(s).")
        for fx in fixtures:
            print(f"  {fx['fixtureId']}: {fx.get('participant1Name')} {fx.get('participant2Name')} ({fx.get('startTime')})")

        for fx in fixtures:
            fixture_id = fx["fixtureId"]
            odd_10 = odd_01 = None
            for outcome_id, label in [(OUTCOME_1_0, "1:0"), (OUTCOME_0_1, "0:1")]:
                try:
                    payload = fetch_historical_odds(fixture_id, outcome_id, api_key)
                    rows = flatten_response(fixture_id, payload)
                    upsert_to_supabase(rows, supabase_url, service_key)
                    if rows:
                        last_price = rows[-1]["price"]
                        if outcome_id == OUTCOME_1_0:
                            odd_10 = last_price
                        else:
                            odd_01 = last_price
                except requests.HTTPError as e:
                    print(f"    Falha em {fixture_id} outcome {label}: {e}", file=sys.stderr)
                time.sleep(args.sleep_seconds)
            passou = passa_filtro_lay(odd_10, odd_01)
            print(f"  {fixture_id}: odd_10(final)={odd_10} odd_01(final)={odd_01} -> {'PASSARIA no filtro' if passou else 'nao passaria'}")
        return
    elif args.all_tournaments:
        fixtures = []
        for i, chunk in enumerate(load_all_tournament_ids(args.all_tournaments)):
            ids_str = ",".join(chunk)
            print(f"Lote {i+1}: buscando {len(chunk)} torneio(s)...")
            try:
                chunk_fixtures = fetch_fixtures_by_tournaments(ids_str, api_key)
                fixtures.extend(chunk_fixtures)
            except requests.HTTPError as e:
                print(f"  Falha no lote {i+1}: {e}", file=sys.stderr)
        fixture_ids = []
        for fx in fixtures:
            odd_10, odd_01 = extract_1x0_0x1_prices(fx)
            if passa_filtro_lay(odd_10, odd_01):
                fixture_ids.append(fx["fixtureId"])
    elif args.tournament_ids:
        all_ids = [t.strip() for t in args.tournament_ids.split(",") if t.strip()]
        fixtures = []
        for i, chunk in enumerate(chunk_list(all_ids, 3)):
            ids_str = ",".join(chunk)
            try:
                chunk_fixtures = fetch_fixtures_by_tournaments(ids_str, api_key)
                fixtures.extend(chunk_fixtures)
            except requests.HTTPError as e:
                print(f"Falha no lote: {e}", file=sys.stderr)
        fixture_ids = []
        for fx in fixtures:
            odd_10, odd_01 = extract_1x0_0x1_prices(fx)
            if passa_filtro_lay(odd_10, odd_01):
                fixture_ids.append(fx["fixtureId"])
    elif args.fixture_ids:
        fixture_ids = [f.strip() for f in args.fixture_ids.split(",") if f.strip()]
    elif args.from_table:
        fixture_ids = get_fixture_ids_from_table(
            supabase_url, service_key, args.from_table, args.fixture_column, args.since_hours
        )
    else:
        print("Erro: forneca --finished-tournament, --all-tournaments, --tournament-ids, --fixture-ids ou --from-table", file=sys.stderr)
        sys.exit(1)

    if not fixture_ids:
        print("Nenhuma fixture para processar. Encerrando.")
        return

    print(f"Buscando historico de odds para {len(fixture_ids)} fixture(s)...")
    for fixture_id in fixture_ids:
        for outcome_id, label in [(OUTCOME_1_0, "1:0"), (OUTCOME_0_1, "0:1")]:
            try:
                payload = fetch_historical_odds(fixture_id, outcome_id, api_key)
                rows = flatten_response(fixture_id, payload)
                upsert_to_supabase(rows, supabase_url, service_key)
            except requests.HTTPError as e:
                print(f"Falha na fixture {fixture_id} outcome {label}: {e}", file=sys.stderr)
            time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
