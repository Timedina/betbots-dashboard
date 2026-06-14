import json
import betfair_client as bf

bf.login()

jogos_hoje = [
    ('1.251400256', 'Germany v Curacao'),
    ('1.251400112', 'Netherlands v Japan'),
    ('1.251384179', 'Ivory Coast v Ecuador'),
    ('1.256139736', 'Sweden v Tunisia'),
]

ODD_FAVORITO_MAX              = 2.20
ODD_01_MINIMA                 = 0
ODD_01_MAXIMA                 = 20.0
ODD_OVER15_MINIMA             = 1.10
ODD_OVER15_MAXIMA             = 1.35
ODD_OVER15_MAXIMA_COPA        = 1.50  # limite especial Copa
ODD_BTTS_MINIMA               = 1.55
ODD_BTTS_MAXIMA               = 2.30
LIQUIDEZ_MINIMA_CS_DISPONIVEL = 150
RAZAO_ODD_MAXIMA              = 1.8
COMPETITION_COPA              = 'World Cup'  # detecta Copa

for market_id_cs, nome in jogos_hoje:
    print(f'\n{"="*55}')
    print(f'⚽ {nome}')
    print(f'{"="*55}')

    rpc_cat = json.dumps({
        'jsonrpc': '2.0',
        'method': 'SportsAPING/v1.0/listMarketCatalogue',
        'params': {
            'filter': {'marketIds': [market_id_cs]},
            'maxResults': '1',
            'marketProjection': ['EVENT', 'RUNNER_DESCRIPTION', 'COMPETITION'],
        },
        'id': 1
    })
    cat = bf.chamar_api(rpc_cat) or []
    if not cat:
        print('  Mercado CS nao encontrado')
        continue

    event_id       = cat[0].get('event', {}).get('id')
    competition    = cat[0].get('competition', {}).get('name', '')
    runners_cs_map = {r['selectionId']: r['runnerName'] for r in cat[0].get('runners', [])}

    # Limite Over 1.5 dinamico
    over15_max = ODD_OVER15_MAXIMA_COPA if COMPETITION_COPA in competition else ODD_OVER15_MAXIMA
    print(f'  Competição: {competition}')
    print(f'  Limite Over 1.5: {over15_max} {"(Copa)" if COMPETITION_COPA in competition else "(padrão)"}')

    rpc_merc = json.dumps({
        'jsonrpc': '2.0',
        'method': 'SportsAPING/v1.0/listMarketCatalogue',
        'params': {
            'filter': {
                'eventIds': [event_id],
                'marketTypeCodes': ['MATCH_ODDS', 'CORRECT_SCORE', 'OVER_UNDER_15', 'BOTH_TEAMS_TO_SCORE']
            },
            'maxResults': '10',
            'marketProjection': ['RUNNER_DESCRIPTION'],
        },
        'id': 2
    })
    mercados = bf.chamar_api(rpc_merc) or []

    mo_id          = next((m['marketId'] for m in mercados if m['marketName'] == 'Match Odds'), None)
    over15_id      = next((m['marketId'] for m in mercados if m['marketName'] == 'Over/Under 1.5 Goals'), None)
    btts_id        = next((m['marketId'] for m in mercados if m['marketName'] == 'Both teams to Score?'), None)
    mo_runners     = {r['selectionId']: r['runnerName'] for m in mercados if m['marketName'] == 'Match Odds' for r in m.get('runners', [])}
    over15_runners = {r['selectionId']: r['runnerName'] for m in mercados if m['marketName'] == 'Over/Under 1.5 Goals' for r in m.get('runners', [])}
    btts_runners   = {r['selectionId']: r['runnerName'] for m in mercados if m['marketName'] == "Both teams to Score?" for r in m.get('runners', [])}

    ids       = [i for i in [market_id_cs, mo_id, over15_id, btts_id] if i]
    books     = bf.listar_odds(ids, ['EX_BEST_OFFERS']) or []
    books_map = {b['marketId']: b for b in books}

    odd_favorito = None
    nome_favorito = None
    if mo_id and mo_id in books_map:
        for r in books_map[mo_id].get('runners', []):
            nome_r = mo_runners.get(r['selectionId'], '')
            if nome_r == 'The Draw':
                continue
            back = bf.get_back(r)
            if back and (odd_favorito is None or back < odd_favorito):
                odd_favorito  = back
                nome_favorito = nome_r

    odd_10 = odd_01 = None
    liq_disp = liq_total = 0
    if market_id_cs in books_map:
        book_cs   = books_map[market_id_cs]
        liq_total = book_cs.get('totalMatched', 0)
        for r in book_cs.get('runners', []):
            nome_r = runners_cs_map.get(r['selectionId'], '')
            lay    = bf.get_lay(r)
            if nome_r in ['1 - 0', '0 - 1']:
                for ordem in r.get('ex', {}).get('availableToLay', []):
                    liq_disp += ordem.get('size', 0)
            if nome_r == '1 - 0':
                odd_10 = lay
            elif nome_r == '0 - 1':
                odd_01 = lay

    odd_over15 = None
    if over15_id and over15_id in books_map:
        for r in books_map[over15_id].get('runners', []):
            if over15_runners.get(r['selectionId'], '') == 'Over 1.5 Goals':
                odd_over15 = bf.get_back(r)

    odd_btts = None
    if btts_id and btts_id in books_map:
        for r in books_map[btts_id].get('runners', []):
            if btts_runners.get(r['selectionId'], '') == 'Yes':
                odd_btts = bf.get_back(r)

    print(f'  Favorito : {nome_favorito} @ {odd_favorito}')
    print(f'  LAY 1-0  : {odd_10}')
    print(f'  LAY 0-1  : {odd_01}')
    print(f'  Over 1.5 : {odd_over15}')
    print(f'  BTTS     : {odd_btts}')
    print(f'  Liq disp : £{liq_disp:.0f} | Total: £{liq_total:.0f}')
    print(f'  Filtros:')

    motivos = []
    if not odd_favorito or odd_favorito > ODD_FAVORITO_MAX:
        motivos.append(f'    ⛔ Favorito fora faixa: {odd_favorito} (max {ODD_FAVORITO_MAX})')
    else:
        print(f'    ✅ Favorito OK: {odd_favorito:.2f}')

    if liq_disp < LIQUIDEZ_MINIMA_CS_DISPONIVEL:
        motivos.append(f'    ⛔ Liquidez insuf: £{liq_disp:.0f} (min £{LIQUIDEZ_MINIMA_CS_DISPONIVEL})')
    else:
        print(f'    ✅ Liquidez OK: £{liq_disp:.0f}')

    if not odd_01:
        motivos.append(f'    ⛔ Sem odd 0-1')
    elif not (ODD_01_MINIMA <= odd_01 <= ODD_01_MAXIMA):
        motivos.append(f'    ⛔ Odd 0-1 fora faixa: {odd_01}')
    else:
        print(f'    ✅ Odd 0-1 OK: {odd_01:.2f}')

    if odd_10 and odd_01:
        razao = round(odd_01 / odd_10, 2)
        if razao > RAZAO_ODD_MAXIMA:
            motivos.append(f'    ⛔ Razao alta: {razao} (max {RAZAO_ODD_MAXIMA})')
        else:
            print(f'    ✅ Razao OK: {razao}')

    if odd_over15 and not (ODD_OVER15_MINIMA <= odd_over15 <= over15_max):
        motivos.append(f'    ⛔ Over 1.5 fora faixa: {odd_over15} (faixa {ODD_OVER15_MINIMA}-{over15_max})')
    elif odd_over15:
        print(f'    ✅ Over 1.5 OK: {odd_over15:.2f}')

    if odd_btts and not (ODD_BTTS_MINIMA <= odd_btts <= ODD_BTTS_MAXIMA):
        motivos.append(f'    ⛔ BTTS fora faixa: {odd_btts} (faixa {ODD_BTTS_MINIMA}-{ODD_BTTS_MAXIMA})')
    elif odd_btts:
        print(f'    ✅ BTTS OK: {odd_btts:.2f}')

    if motivos:
        for m in motivos:
            print(m)
        print(f'  🔴 REPROVADO')
    else:
        print(f'  🟢 APROVADO')
