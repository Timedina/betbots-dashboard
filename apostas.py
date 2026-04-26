"""
apostas.py
Modulo de apostas automaticas na Betfair
Estrategia: LAY no runner de odd mais alta (1-0 ou 0-1)
Stake minimo: £2.00

MODO_SIMULACAO = True  → apenas loga, nao aposta de verdade
MODO_SIMULACAO = False → aposta real
"""

import json
import urllib.request
import logging
from datetime import datetime, timezone, timedelta

import betfair_client as bf

FUSO_BRASILIA  = timezone(timedelta(hours=-3))
STAKE_LAY      = 2.0   # £ minimo Betfair
MODO_SIMULACAO = True  # ← mude para False quando quiser apostar de verdade

log = logging.getLogger('bot')


def place_lay(market_id: str, selection_id: int, odd: float, stake: float = STAKE_LAY) -> dict:
    if MODO_SIMULACAO:
        log.info(f'  [Aposta-SIM] LAY simulado | market={market_id} | sel={selection_id} | odd={odd} | stake=£{stake}')
        return {
            'status':      'SUCCESS',
            'betId':       'SIMULADO',
            'sizeMatched': 0,
            'avgPrice':    0,
            'simulado':    True,
        }

    rpc = json.dumps({
        'jsonrpc': '2.0',
        'method': 'SportsAPING/v1.0/placeOrders',
        'params': {
            'marketId': market_id,
            'instructions': [{
                'selectionId': str(selection_id),
                'handicap': '0',
                'side': 'LAY',
                'orderType': 'LIMIT',
                'limitOrder': {
                    'size': str(stake),
                    'price': str(odd),
                    'persistenceType': 'LAPSE'
                }
            }]
        },
        'id': 1
    })

    url     = 'https://api.betfair.bet.br/exchange/betting/json-rpc/v1'
    headers = {
        'X-Application':   bf.APP_KEY,
        'X-Authentication': bf.SESSION_TOKEN,
        'content-type':    'application/json'
    }

    try:
        req = urllib.request.Request(url, rpc.encode('utf-8'), headers)
        raw = urllib.request.urlopen(req).read().decode('utf-8')
        res = json.loads(raw)

        if 'error' in res:
            erro = res['error'].get('data', {}).get('APINGException', {}).get('errorCode', 'UNKNOWN')
            log.error(f'  [Aposta] Erro Betfair: {erro}')
            return {'status': 'ERRO', 'motivo': erro}

        report = res.get('result', {})
        if report.get('status') == 'SUCCESS':
            inst         = report.get('instructionReports', [{}])[0]
            bet_id       = inst.get('betId', '?')
            size_matched = inst.get('sizeMatched', 0)
            avg_price    = inst.get('averagePriceMatched', 0)
            log.info(f'  [Aposta] ✅ betId={bet_id} | matched={size_matched} @ {avg_price}')
            return {'status': 'SUCCESS', 'betId': bet_id, 'sizeMatched': size_matched, 'avgPrice': avg_price}
        else:
            log.error(f'  [Aposta] Falha: {report}')
            return {'status': 'ERRO', 'motivo': str(report)}

    except Exception as e:
        log.error(f'  [Aposta] Excecao: {e}')
        return {'status': 'ERRO', 'motivo': str(e)}


def apostar_jogo_aprovado(info: dict) -> dict:
    odd_10 = float(info.get('odd_10') or 0)
    odd_01 = float(info.get('odd_01') or 0)

    if odd_10 >= odd_01:
        placar_lay  = '1-0'
        odd_lay     = odd_10
        nome_runner = '1 - 0'
    else:
        placar_lay  = '0-1'
        odd_lay     = odd_01
        nome_runner = '0 - 1'

    runners_map  = info.get('runners_cs_map', {})
    selection_id = None
    for sid, nome in runners_map.items():
        if nome == nome_runner:
            selection_id = int(sid)
            break

    if not selection_id:
        log.error(f'  [Aposta] selectionId nao encontrado para {nome_runner}')
        return {'status': 'ERRO', 'motivo': f'selectionId nao encontrado para {nome_runner}'}

    market_id = info.get('market_id_cs')
    if not market_id:
        return {'status': 'ERRO', 'motivo': 'market_id_cs ausente'}

    modo = 'SIMULACAO' if MODO_SIMULACAO else 'REAL'
    log.info(f'  [Aposta-{modo}] LAY {placar_lay} @ {odd_lay} | sel={selection_id} | market={market_id}')

    resultado = place_lay(market_id, selection_id, odd_lay, STAKE_LAY)
    resultado['placar_lay']   = placar_lay
    resultado['odd_lay']      = odd_lay
    resultado['selection_id'] = selection_id
    resultado['nome_jogo']    = info.get('nome_jogo', '')
    resultado['apostado_em']  = datetime.now(FUSO_BRASILIA).strftime('%H:%M:%S')
    resultado['simulado']     = MODO_SIMULACAO
    return resultado
