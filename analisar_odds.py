import betfair_client as bf
bf.login()
mercados = {'1.257154140': 'Rangers v Motherwell', '1.256718893': 'Torino v Inter', '1.256730107': 'Marseille v Nice', '1.257219432': 'Cruz Azul v Necaxa'}
books = bf.listar_odds(list(mercados.keys()), ['EX_BEST_OFFERS'])
for book in books:
    mid = book['marketId']
    runners = book.get('runners', [])
    nome = mercados.get(mid, mid)
    odd_10 = None
    odd_01 = None
    for r in runners:
        sid = r.get('selectionId')
        if sid == 2: odd_10 = bf.get_lay(r)
        if sid == 4: odd_01 = bf.get_lay(r)
    print(nome)
    print('  LAY 1-0 @ ' + str(odd_10))
    print('  LAY 0-1 @ ' + str(odd_01))
    if odd_10 and odd_01:
        melhor = '1-0' if odd_10 >= odd_01 else '0-1'
        print('  >> Entrar: LAY ' + melhor + ' @ ' + str(max(odd_10, odd_01)))
    print()
