import betfair_client as bf
import json, urllib.request

bf.login()

rpc = json.dumps({
    'jsonrpc': '2.0',
    'method': 'SportsAPING/v1.0/placeOrders',
    'params': {
        'marketId': '1.000000000',
        'instructions': [{
            'selectionId': '1',
            'handicap': '0',
            'side': 'LAY',
            'orderType': 'LIMIT',
            'limitOrder': {
                'size': '2',
                'price': '3',
                'persistenceType': 'LAPSE'
            }
        }]
    },
    'id': 1
})

url = 'https://api.betfair.bet.br/exchange/betting/json-rpc/v1'
headers = {
    'X-Application': bf.APP_KEY,
    'X-Authentication': bf.SESSION_TOKEN,
    'content-type': 'application/json'
}
req = urllib.request.Request(url, rpc.encode('utf-8'), headers)
raw = urllib.request.urlopen(req).read().decode('utf-8')
print(raw)
