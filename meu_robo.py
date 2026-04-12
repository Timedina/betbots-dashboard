from dotenv import load_dotenv
import os, requests, urllib.request, urllib.error, json
from datetime import datetime, timezone

load_dotenv(override=True)
EMAIL = os.getenv('EMAIL')
SENHA = os.getenv('SENHA')
APP_KEY = os.getenv('APP_KEY')
SESSION_TOKEN = None

def session_token():
    global SESSION_TOKEN
    resp = requests.post(
        'https://identitysso-cert.betfair.bet.br/api/certlogin',
        data=f'username={EMAIL}&password={SENHA}',
        cert=('client-2048_1.crt', 'client-2048.KEY'),
        headers={'X-Application': APP_KEY, 'Content-Type': 'application/x-www-form-urlencoded'}
    )
    if resp.status_code == 200:
        SESSION_TOKEN = resp.json()['sessionToken']
        print('Login OK!')
        return SESSION_TOKEN
    print('Falha:', resp.text)
    return None

def callAping(rpc):
    url = 'https://api.betfair.bet.br/exchange/betting/json-rpc/v1'
    headers = {'X-Application': APP_KEY, 'X-Authentication': SESSION_TOKEN, 'content-type': 'application/json'}
    try:
        req = urllib.request.Request(url, rpc.encode('utf-8'), headers)
        return urllib.request.urlopen(req).read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print('HTTPError:', e.code, e.read().decode('utf-8'))
        return None
    except Exception as e:
        print('Erro:', str(e))
        return None

def listar_jogos(event_type_id='1'):
    agora = datetime.now(timezone.utc)
    fim = agora.replace(hour=23, minute=59, second=59)
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listEvents',
        'params': {'filter': {'eventTypeIds': [event_type_id],
            'marketStartTime': {'from': agora.strftime('%Y-%m-%dT%H:%M:%SZ'), 'to': fim.strftime('%Y-%m-%dT%H:%M:%SZ')}}},
        'id': 1
    })
    raw = callAping(rpc)
    if not raw:
        return []
    return json.loads(raw).get('result', [])

def inspecionar_jogo(event_id):
    print(f'\n{"="*60}')
    print(f'INSPECIONANDO EVENTO: {event_id}')
    print(f'{"="*60}')

    # 1. Catalogo completo do evento
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listMarketCatalogue',
        'params': {
            'filter': {'eventIds': [event_id]},
            'maxResults': '100',
            'marketProjection': ['COMPETITION', 'EVENT', 'EVENT_TYPE', 'RUNNER_DESCRIPTION', 'RUNNER_METADATA', 'MARKET_START_TIME']
        }, 'id': 1
    })
    raw = callAping(rpc)
    if not raw:
        return
    catalogo = json.loads(raw).get('result', [])

    print(f'\nTotal de mercados disponíveis: {len(catalogo)}\n')
    print(f'{"MARKET ID":<20} {"NOME DO MERCADO":<40} {"RUNNERS"}')
    print('-' * 80)
    for m in catalogo:
        runners = [r['runnerName'] for r in m.get('runners', [])]
        print(f"{m['marketId']:<20} {m['marketName']:<40} {', '.join(runners[:3])}")

    # 2. Busca odds do Match Odds
    match_odds = next((m for m in catalogo if m['marketName'] == 'Match Odds'), None)
    if not match_odds:
        print('\nSem Match Odds.')
        return

    market_id = match_odds['marketId']
    runners_info = {r['selectionId']: r['runnerName'] for r in match_odds.get('runners', [])}

    rpc2 = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listMarketBook',
        'params': {
            'marketIds': [market_id],
            'priceProjection': {'priceData': ['EX_BEST_OFFERS', 'EX_TRADED'], 'virtualise': 'true'}
        }, 'id': 1
    })
    raw2 = callAping(rpc2)
    if not raw2:
        return
    book = json.loads(raw2).get('result', [{}])[0]

    print(f'\n--- MATCH ODDS ---')
    print(f"Status: {book.get('status')}")
    print(f"Ao vivo: {book.get('inplay')}")
    print(f"Total apostado: £{book.get('totalMatched', 0):,.2f}")
    print(f"Total disponível: £{book.get('totalAvailable', 0):,.2f}")
    print(f"Delay: {book.get('betDelay')} segundos")
    print()

    for runner in book.get('runners', []):
        nome = runners_info.get(runner['selectionId'], str(runner['selectionId']))
        last = runner.get('lastPriceTraded', '-')
        total = runner.get('totalMatched', 0)
        back_offers = runner.get('ex', {}).get('availableToBack', [])
        lay_offers = runner.get('ex', {}).get('availableToLay', [])

        print(f'  {nome}')
        print(f'    Ultima odd: {last} | Total apostado: £{total:,.2f}')
        if back_offers:
            print(f'    BACK: ' + ' | '.join([f"{o['price']} (£{o['size']:.0f})" for o in back_offers[:3]]))
        if lay_offers:
            print(f'    LAY:  ' + ' | '.join([f"{o['price']} (£{o['size']:.0f})" for o in lay_offers[:3]]))
        print()

if __name__ == '__main__':
    print('Iniciando o robo Betfair...')
    if not session_token():
        exit()

    jogos = listar_jogos('1')
    print(f'\nTotal de jogos hoje: {len(jogos)}')

    # Inspeciona o primeiro jogo brasileiro
    jogos_br = [j for j in jogos if j['event'].get('countryCode') == 'BR']
    print(f'Jogos brasileiros hoje: {len(jogos_br)}')

    if jogos_br:
        primeiro = jogos_br[0]
        print(f'\nInspecionando: {primeiro["event"]["name"]}')
        inspecionar_jogo(primeiro['event']['id'])