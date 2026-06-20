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
STAKE_LAY      = 11.0   # £ minimo Betfair (usado como fallback)
LIABILITY_FIXA = 100.0  # £ perda maxima aceita por aposta (novo modelo de stake)
STAKE_MINIMO   = 2.0    # £ minimo permitido pela Betfair
MODO_SIMULACAO = True  # ← mude para False quando quiser apostar de verdade


def calcular_stake_por_liability(odd: float, liability: float = LIABILITY_FIXA) -> float:
    """
    Calcula o stake necessario para que a perda maxima (liability) seja sempre a mesma,
    independente da odd. Stake = liability / (odd - 1).
    Isso evita que apostas em odds altas gerem prejuizo desproporcional.
    """
    if odd <= 1:
        return STAKE_MINIMO
    stake = liability / (odd - 1)
    return max(stake, STAKE_MINIMO)

log = logging.getLogger('bot')


def place_lay(market_id: str, selection_id: int, odd: float, stake: float = STAKE_LAY) -> dict:
    if MODO_SIMULACAO:
        log.info(f'  [Aposta-SIM] LAY simulado | market={market_id} | sel={selection_id} | odd={odd} | stake=R${stake}')
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

    from bot_prelive import APENAS_LAY_01, APENAS_LAY_10

    if APENAS_LAY_01:
        # Forca LAY 0-1 independente das odds
        placar_lay  = '0-1'
        odd_lay     = odd_01
        nome_runner = '0 - 1'
        log.info('  [Aposta] Filtro APENAS_LAY_01 ativo: forcando LAY 0-1')
    elif APENAS_LAY_10:
        # Forca LAY 1-0 independente das odds
        placar_lay  = '1-0'
        odd_lay     = odd_10
        nome_runner = '1 - 0'
        log.info('  [Aposta] Filtro APENAS_LAY_10 ativo: forcando LAY 1-0')
    elif odd_10 >= odd_01:
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

    stake_calculado = calcular_stake_por_liability(odd_lay)
    log.info(f'  [Aposta] Liability fixa £{LIABILITY_FIXA:.0f} -> stake calculado: £{stake_calculado:.2f} (odd {odd_lay})')
    resultado = place_lay(market_id, selection_id, odd_lay, stake_calculado)
    resultado['placar_lay']   = placar_lay
    resultado['odd_lay']      = odd_lay
    resultado['stake']        = stake_calculado
    resultado['selection_id'] = selection_id
    resultado['nome_jogo']    = info.get('nome_jogo', '')
    resultado['apostado_em']  = datetime.now(FUSO_BRASILIA).strftime('%H:%M:%S')
    resultado['simulado']     = MODO_SIMULACAO
    return resultado
