"""
resultado_jogos.py
Busca o resultado final dos jogos aprovados via Betfair API
Logica: entra sempre no LAY com odd mais alta (mais improvavel)
"""

import json
import os
from datetime import datetime, timezone, timedelta
import betfair_client as bf

FUSO_BRASILIA = timezone(timedelta(hours=-3))
PASTA_DADOS   = 'dados_bot'

# Mapeamento fixo de selectionId para placar CS na Betfair
CS_MAP = {
    1:  '0-0',  2:  '1-0',  3:  '2-0',  4:  '0-1',  5:  '1-1',
    6:  '2-1',  7:  '3-0',  8:  '0-2',  9:  '1-2',  10: '3-1',
    11: '2-2',  12: '3-2',  13: '4-0',  14: '0-3',  15: '1-3',
    16: '2-3',  17: '4-1',  18: '3-3',  19: '4-2',
    9063254: 'Outro Casa',
    9063255: 'Outro Empate',
    9063256: 'Outro Fora',
}


def arquivo_do_dia(data_str=None) -> str:
    if not data_str:
        data_str = datetime.now(FUSO_BRASILIA).strftime('%Y-%m-%d')
    return os.path.join(PASTA_DADOS, f'aprovados_{data_str}.json')


def carregar_aprovados(data_str=None) -> dict:
    path = arquivo_do_dia(data_str)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def salvar_aprovados(dados: dict, data_str=None):
    path = arquivo_do_dia(data_str)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def buscar_resultado_mercado(market_id: str) -> dict:
    rpc = json.dumps({
        'jsonrpc': '2.0',
        'method': 'SportsAPING/v1.0/listMarketBook',
        'params': {
            'marketIds': [market_id],
            'priceProjection': {'priceData': ['EX_BEST_OFFERS']},
        },
        'id': 1
    })

    resultado = bf.chamar_api(rpc)
    if not resultado:
        return {'status': 'erro', 'placar': None, 'runner_id': None}

    book   = resultado[0] if isinstance(resultado, list) else resultado
    status = book.get('status', '')

    if status in ('CLOSED', 'SETTLED'):
        for r in book.get('runners', []):
            if r.get('status') == 'WINNER':
                runner_id = r.get('selectionId')
                placar    = CS_MAP.get(runner_id, 'ID:' + str(runner_id))
                return {'status': 'encerrado', 'runner_id': runner_id, 'placar': placar}
        return {'status': 'encerrado_sem_vencedor', 'placar': None, 'runner_id': None}

    elif status == 'OPEN':
        return {'status': 'ao_vivo' if book.get('inplay') else 'aberto', 'placar': None, 'runner_id': None}

    return {'status': status.lower(), 'placar': None, 'runner_id': None}


def determinar_resultado_lay(placar_final: str, info_jogo: dict) -> dict:
    """
    Logica correta:
    - Entra sempre no LAY com odd MAIS ALTA (mais improvavel)
    - Se odd_10 > odd_01 → LAY 1-0
    - Se odd_01 > odd_10 → LAY 0-1
    - Ganha se o jogo NAO terminar nesse placar
    - Perde se terminar exatamente nesse placar
    """
    resultado = {
        'placar_final':    placar_final,
        'placar_lay':      None,
        'odd_lay':         None,
        'resultado_geral': None,
        'pnl_estimado':    None,
    }

    if not placar_final:
        return resultado

    odd_10 = float(info_jogo.get('odd_10') or 0)
    odd_01 = float(info_jogo.get('odd_01') or 0)
    stake  = 10
    comissao = 0.05

    # Determina qual LAY entrou (odd mais alta)
    if odd_10 >= odd_01:
        placar_lay = '1-0'
        odd_lay    = odd_10
    else:
        placar_lay = '0-1'
        odd_lay    = odd_01

    resultado['placar_lay'] = placar_lay
    resultado['odd_lay']    = odd_lay

    placar = placar_final.replace(' ', '')

    if placar == placar_lay:
        # Terminou exatamente no placar do LAY — PERDA
        pnl = -stake * (odd_lay - 1)
        resultado['resultado_geral'] = 'PERDA'
    else:
        # Terminou diferente — GANHO
        pnl = stake * (1 - comissao)
        resultado['resultado_geral'] = 'VITORIA'

    resultado['pnl_estimado'] = round(pnl, 2)
    return resultado


def atualizar_resultados_do_dia(data_str=None, verbose=True):
    aprovados = carregar_aprovados(data_str)
    if not aprovados:
        if verbose:
            print('Nenhum jogo aprovado encontrado.')
        return

    atualizados = 0

    for event_id, info in aprovados.items():
        market_id = info.get('market_id_cs')
        if not market_id:
            continue

        if info.get('placar_final') and info.get('resultado_geral') and info.get('placar_final') != 'Indisponivel':
            if verbose:
                print('  ' + info['nome_jogo'] + ': ja tem resultado (' + str(info['placar_final']) + ')')
            continue

        if verbose:
            print('  Buscando resultado: ' + info['nome_jogo'] + '...')

        res = buscar_resultado_mercado(market_id)

        if res['status'] not in ('encerrado', 'encerrado_sem_vencedor'):
            if verbose:
                print('    Status: ' + res['status'] + ' - ainda nao encerrado')
            continue

        placar_final  = res.get('placar')
        resultado_lay = determinar_resultado_lay(placar_final, info)

        info['placar_final']     = placar_final or 'Indisponivel'
        info['placar_lay']       = resultado_lay['placar_lay']
        info['odd_lay']          = resultado_lay['odd_lay']
        info['resultado_geral']  = resultado_lay['resultado_geral']
        info['pnl_estimado']     = resultado_lay['pnl_estimado']
        info['resultado_em']     = datetime.now(FUSO_BRASILIA).strftime('%H:%M:%S')
        atualizados += 1

        if verbose:
            pnl_val = resultado_lay.get('pnl_estimado') or 0
            result  = resultado_lay.get('resultado_geral') or 'Pendente'
            emoji   = '✅' if result == 'VITORIA' else '❌'
            odd_lay = resultado_lay.get('odd_lay') or 0
            placar_lay = resultado_lay.get('placar_lay') or ''
            print('    ' + emoji + ' Placar: ' + str(placar_final) +
                  ' | LAY ' + placar_lay + ' @ ' + str(odd_lay) +
                  ' | ' + result + ' | PnL: ' + str(pnl_val) + 'u')

    if atualizados > 0:
        salvar_aprovados(aprovados, data_str)
        if verbose:
            print('\n  ' + str(atualizados) + ' resultado(s) atualizados!')
    else:
        if verbose:
            print('  Nenhum resultado novo encontrado.')

    return aprovados


def resumo_resultados(data_str=None) -> str:
    aprovados = carregar_aprovados(data_str)
    data = data_str or datetime.now(FUSO_BRASILIA).strftime('%d/%m/%Y')

    if not aprovados:
        return '📋 Sem jogos aprovados em ' + data

    vitorias = derrotas = pendentes = 0
    pnl_total = 0.0
    linhas = ['📊 *Resultados — ' + data + '*', '━━━━━━━━━━━━━━━━━━━━']

    for info in sorted(aprovados.values(), key=lambda x: x.get('horario', '')):
        nome       = info.get('nome_jogo', '')
        horario    = info.get('horario', '--:--')
        placar     = info.get('placar_final', '')
        placar_lay = info.get('placar_lay', '')
        odd_lay    = info.get('odd_lay', 0)
        result     = info.get('resultado_geral', '')
        pnl        = info.get('pnl_estimado', 0) or 0

        if result == 'VITORIA':
            emoji = '✅'; vitorias += 1; pnl_total += pnl
        elif result == 'PERDA':
            emoji = '❌'; derrotas += 1; pnl_total += pnl
        else:
            emoji = '⏳'; pendentes += 1

        lay_str    = ' LAY ' + str(placar_lay) + ' @' + str(odd_lay) if placar_lay else ''
        placar_str = ' | ' + placar if placar and placar != 'Indisponivel' else ''
        pnl_str    = ' | PnL: ' + ('+' if pnl >= 0 else '') + str(pnl) + 'u' if result else ''
        linhas.append(emoji + ' ' + horario + ' ' + nome + lay_str + placar_str + pnl_str)

    linhas += [
        '━━━━━━━━━━━━━━━━━━━━',
        '✅ Vitorias: ' + str(vitorias) + ' | ❌ Perdas: ' + str(derrotas) + ' | ⏳ Pendentes: ' + str(pendentes),
        '💰 PnL Total: ' + ('+' if pnl_total >= 0 else '') + str(round(pnl_total, 1)) + ' unidades (stake 10/LAY)',
    ]
    return '\n'.join(linhas)


if __name__ == '__main__':
    print('Atualizando resultados do dia...')
    bf.login()
    atualizar_resultados_do_dia(verbose=True)
    print()
    print(resumo_resultados())
