import betfair_client as bf
import json

bf.login()

jogos = {
    'Rangers v Motherwell':  {'cs': '1.257154140'},
    'Torino v Inter':        {'cs': '1.256718893'},
    'Marseille v Nice':      {'cs': '1.256730107'},
    'Cruz Azul v Necaxa':   {'cs': '1.257219432'},
}

# Busca Match Odds tambem
rpc = json.dumps({
    'jsonrpc': '2.0',
    'method': 'SportsAPING/v1.0/listMarketCatalogue',
    'params': {
        'filter': {
            'marketIds': list(m['cs'] for m in jogos.values()),
        },
        'maxResults': '10',
        'marketProjection': ['RUNNER_DESCRIPTION'],
    },
    'id': 1
})

catalogos = bf.chamar_api(rpc)
for c in catalogos:
    mid = c['marketId']
    nome = next((n for n, v in jogos.items() if v['cs'] == mid), mid)
    print('=' * 40)
    print(nome)
    for r in c.get('runners', []):
        print('  ID:', r['selectionId'], '|', r['runnerName'])
    print()
