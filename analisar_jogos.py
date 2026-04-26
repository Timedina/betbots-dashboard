import betfair_client as bf

bf.login()

market_ids = [
    '1.257154140',
    '1.256718893',
    '1.256730107',
    '1.257219432',
]

nomes = {
    '1.257154140': 'Rangers v Motherwell',
    '1.256718893': 'Torino v Inter',
    '1.256730107': 'Marseille v Nice',
    '1.257219432': 'Cruz Azul v Necaxa',
}

books = bf.listar_odds(market_ids, ['EX_BEST_OFFERS'])

for book in books:
    mid = book['marketId']
    runners = book.get('runners', [])
    print('=' * 40)
    print(nomes.get(mid, mid))
    for r in runners:
        nome = r.get('runnerName', '')
        if nome in ['1 - 0', '0 - 1']:
            lay = bf.get_lay(r)
            back = bf.get_back(r)
            print('  ' + nome + ' | LAY: ' + str(lay) + ' | BACK: ' + str(back))
    print()
