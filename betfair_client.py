import requests
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
import os

load_dotenv(override=True)

EMAIL = os.getenv('EMAIL')
SENHA = os.getenv('SENHA')
APP_KEY = os.getenv('APP_KEY')

SESSION_TOKEN = None
ULTIMO_LOGIN = None


def login():
    global SESSION_TOKEN, ULTIMO_LOGIN
    resp = requests.post(
        'https://identitysso-cert.betfair.bet.br/api/certlogin',
        data=f'username={EMAIL}&password={SENHA}',
        cert=('client-2048_1.crt', 'client-2048.KEY'),
        headers={'X-Application': APP_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
    )
    if resp.status_code == 200 and resp.json().get('loginStatus') == 'SUCCESS':
        SESSION_TOKEN = resp.json()['sessionToken']
        ULTIMO_LOGIN = datetime.now(timezone.utc)
        print(f'[Betfair] Login OK!')
        return True
    print(f'[Betfair] Falha no login: {resp.text}')
    return False


def renovar_token_se_necessario():
    """Renova o token a cada 6 horas automaticamente"""
    global ULTIMO_LOGIN
    if ULTIMO_LOGIN is None:
        return login()
    diff = (datetime.now(timezone.utc) - ULTIMO_LOGIN).seconds / 3600
    if diff >= 6:
        print('[Betfair] Renovando token...')
        return login()
    return True


def chamar_api(rpc: str) -> dict:
    renovar_token_se_necessario()
    url = 'https://api.betfair.bet.br/exchange/betting/json-rpc/v1'
    headers = {
        'X-Application': APP_KEY,
        'X-Authentication': SESSION_TOKEN,
        'content-type': 'application/json'
    }
    try:
        req = urllib.request.Request(url, rpc.encode('utf-8'), headers)
        raw = urllib.request.urlopen(req).read().decode('utf-8')
        return json.loads(raw).get('result', [])
    except urllib.error.HTTPError as e:
        print(f'[Betfair] HTTPError: {e.code} {e.read().decode()}')
        return []
    except Exception as e:
        print(f'[Betfair] Erro: {str(e)}')
        return []


def listar_jogos_ao_vivo(event_type_id='1'):
    """Lista jogos ao vivo de um esporte"""
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listEvents',
        'params': {'filter': {'eventTypeIds': [event_type_id], 'inPlayOnly': True}},
        'id': 1
    })
    return chamar_api(rpc)


def listar_jogos_hoje(event_type_id='1'):
    """Lista jogos do dia"""
    agora = datetime.now(timezone.utc)
    fim = agora.replace(hour=23, minute=59, second=59)
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listEvents',
        'params': {'filter': {'eventTypeIds': [event_type_id],
            'marketStartTime': {'from': agora.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                'to': fim.strftime('%Y-%m-%dT%H:%M:%SZ')}}},
        'id': 1
    })
    return chamar_api(rpc)


def listar_mercados(event_id: str, tipos: list = None):
    """Lista mercados de um evento"""
    filtro = {'eventIds': [event_id]}
    if tipos:
        filtro['marketTypeCodes'] = tipos
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listMarketCatalogue',
        'params': {'filter': filtro, 'maxResults': '200',
            'marketProjection': ['COMPETITION', 'EVENT', 'EVENT_TYPE', 'RUNNER_DESCRIPTION', 'MARKET_START_TIME']},
        'id': 1
    })
    return chamar_api(rpc)


def listar_odds(market_ids: list, dados: list = None):
    """Lista odds de mercados"""
    if dados is None:
        dados = ['EX_BEST_OFFERS']
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listMarketBook',
        'params': {'marketIds': market_ids,
            'priceProjection': {'priceData': dados, 'virtualise': 'true'}},
        'id': 1
    })
    return chamar_api(rpc)


def get_back(runner: dict, posicao: int = 0) -> float:
    """Retorna odd de back de um runner"""
    offers = runner.get('ex', {}).get('availableToBack', [])
    return offers[posicao]['price'] if len(offers) > posicao else None


def get_lay(runner: dict, posicao: int = 0) -> float:
    """Retorna odd de lay de um runner"""
    offers = runner.get('ex', {}).get('availableToLay', [])
    return offers[posicao]['price'] if len(offers) > posicao else None