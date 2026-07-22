"""
resultado_jogos.py
Busca o resultado final dos jogos aprovados via Betfair API
Logica: entra sempre no LAY com odd mais alta (mais improvavel)
"""

import json
import os
from datetime import datetime, timezone, timedelta
import betfair_client as bf
import supabase_integration as sb

FUSO_BRASILIA = timezone(timedelta(hours=-3))
PASTA_DADOS   = 'dados_bot'

# Mapeamento FALLBACK — usado apenas se runners_cs_map nao estiver salvo
CS_MAP_FALLBACK = {
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


def buscar_resultado_mercado(market_id: str, runners_cs_map: dict = None) -> dict:
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

                # Tenta usar o mapa real salvo no momento da aprovacao
                if runners_cs_map:
                    placar = runners_cs_map.get(str(runner_id), runners_cs_map.get(runner_id))
                    fonte  = 'mapa_real'
                else:
                    placar = None
                    fonte  = 'fallback'

                # Se nao achou no mapa real, usa fallback
                if not placar:
                    placar = CS_MAP_FALLBACK.get(runner_id, 'ID:' + str(runner_id))
                    fonte  = 'fallback'

                return {
                    'status':    'encerrado',
                    'runner_id': runner_id,
                    'placar':    placar,
                    'fonte':     fonte,
                }
        return {'status': 'encerrado_sem_vencedor', 'placar': None, 'runner_id': None}

    elif status == 'OPEN':
        return {'status': 'ao_vivo' if book.get('inplay') else 'aberto', 'placar': None, 'runner_id': None}

    return {'status': status.lower(), 'placar': None, 'runner_id': None}


def determinar_resultado_lay(placar_final: str, info_jogo: dict) -> dict:
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
    # Usa liability fixa se disponivel, senao stake gravado, senao 11 como fallback
    odd_lay_gravada   = float(info_jogo.get('odd_lay') or 0)
    liability_fixa    = float(info_jogo.get('liability') or 0)
    stake_gravado     = float(info_jogo.get('stake') or 0)
    if liability_fixa > 0 and odd_lay_gravada > 1:
        stake = stake_gravado if stake_gravado > 0 else liability_fixa / (odd_lay_gravada - 1)
    elif stake_gravado > 0:
        stake = stake_gravado
    else:
        stake = 11
    comissao = 0.0636

    # Respeita placar_lay ja gravado (APENAS_LAY_01 etc), senao escolhe pela odd
    placar_lay_gravado = info_jogo.get('placar_lay')
    if placar_lay_gravado == '1-0' and odd_10 > 0:
        placar_lay = '1-0'
        odd_lay    = odd_lay_gravada if odd_lay_gravada > 0 else odd_10
    elif placar_lay_gravado == '0-1' and odd_01 > 0:
        placar_lay = '0-1'
        odd_lay    = odd_lay_gravada if odd_lay_gravada > 0 else odd_01
    elif odd_10 >= odd_01:
        placar_lay = '1-0'
        odd_lay    = odd_10
    else:
        placar_lay = '0-1'
        odd_lay    = odd_01

    resultado['placar_lay'] = placar_lay
    resultado['odd_lay']    = odd_lay

    # Normaliza placar para comparacao (ex: "1 - 0" == "1-0")
    placar_norm = placar_final.replace(' ', '').replace('–', '-')

    if placar_norm == placar_lay:
        pnl = -stake * (odd_lay - 1)
        resultado['resultado_geral'] = 'PERDA'
    else:
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

        # Usa o mapa real de runners se disponivel
        runners_cs_map = info.get('runners_cs_map', {})
        if runners_cs_map and verbose:
            print('    Usando mapa real de runners (' + str(len(runners_cs_map)) + ' placares)')
        elif verbose:
            print('    ⚠️  Sem mapa real — usando CS_MAP fallback (pode ser impreciso)')

        res = buscar_resultado_mercado(market_id, runners_cs_map)

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
        info['fonte_placar']     = res.get('fonte', 'desconhecida')
        sb.atualizar_resultado_aposta_supabase(
            event_id,
            resultado_lay['resultado_geral'],
            placar_final or 'Indisponivel',
            resultado_lay.get('pnl_estimado') or 0,
        )
        atualizados += 1

        if verbose:
            pnl_val    = resultado_lay.get('pnl_estimado') or 0
            result     = resultado_lay.get('resultado_geral') or 'Pendente'
            emoji      = '✅' if result == 'VITORIA' else '❌'
            odd_lay    = resultado_lay.get('odd_lay') or 0
            placar_lay = resultado_lay.get('placar_lay') or ''
            fonte      = res.get('fonte', '')
            print('    ' + emoji + ' Placar: ' + str(placar_final) +
                  ' | LAY ' + placar_lay + ' @' + str(odd_lay) +
                  ' | ' + result + ' | PnL: ' + str(pnl_val) + 'u' +
                  (' [' + fonte + ']' if fonte else ''))

    if atualizados > 0:
        salvar_aprovados(aprovados, data_str)
        if verbose:
            print('\n  ' + str(atualizados) + ' resultado(s) atualizados!')
    else:
        if verbose:
            print('  Nenhum resultado novo encontrado.')

    return aprovados


def atualizar_resultados_pendentes(dias_atras: int = 14, verbose: bool = False) -> dict:
    """
    Varre os arquivos aprovados_YYYY-MM-DD.json dos ultimos `dias_atras` dias
    (incluindo hoje) e tenta resolver qualquer aposta ainda sem resultado_geral.

    Diferente de atualizar_resultados_do_dia(), que so olha o dia atual, esta
    funcao evita que apostas de dias anteriores fiquem PENDENTE para sempre
    quando o placar nao estava disponivel na primeira tentativa (jogo adiado,
    API sem dado ainda, etc).

    Retorna um dict {data_str: aprovados_do_dia} apenas para os dias onde
    havia pelo menos uma aposta pendente antes de rodar.
    """
    resultado_por_dia = {}
    hoje = datetime.now(FUSO_BRASILIA).date()

    for i in range(dias_atras):
        data_str = (hoje - timedelta(days=i)).strftime('%Y-%m-%d')
        aprovados_do_dia = carregar_aprovados(data_str)
        if not aprovados_do_dia:
            continue

        tinha_pendente = any(
            not info.get('resultado_geral') for info in aprovados_do_dia.values()
        )
        if not tinha_pendente:
            continue

        if verbose:
            print(f'--- Revisando pendencias de {data_str} ---')
        aprovados_atualizados = atualizar_resultados_do_dia(data_str, verbose=verbose)
        if aprovados_atualizados:
            resultado_por_dia[data_str] = aprovados_atualizados

    return resultado_por_dia


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
        fonte      = info.get('fonte_placar', '')
        aviso      = ' ⚠️' if fonte == 'fallback' else ''

        if result == 'VITORIA':
            emoji = '✅'; vitorias += 1; pnl_total += pnl
        elif result == 'PERDA':
            emoji = '❌'; derrotas += 1; pnl_total += pnl
        else:
            emoji = '⏳'; pendentes += 1

        lay_str    = ' LAY ' + str(placar_lay) + ' @' + str(odd_lay) if placar_lay else ''
        placar_str = ' | ' + placar + aviso if placar and placar != 'Indisponivel' else ''
        pnl_str    = ' | PnL: ' + ('+' if pnl >= 0 else '') + 'R$' + str(abs(round(pnl,2))) if result else ''
        linhas.append(emoji + ' ' + horario + ' ' + nome + lay_str + placar_str + pnl_str)

    linhas += [
        '━━━━━━━━━━━━━━━━━━━━',
        '✅ Vitorias: ' + str(vitorias) + ' | ❌ Perdas: ' + str(derrotas) + ' | ⏳ Pendentes: ' + str(pendentes),
        '💰 PnL Total: ' + ('+' if pnl_total >= 0 else '') + 'R$' + str(abs(round(pnl_total,2))) + ' (stake R$11/LAY)',
    ]
    return '\n'.join(linhas)


if __name__ == '__main__':
    print('Atualizando resultados do dia...')
    bf.login()
    atualizar_resultados_do_dia(verbose=True)
    print()
    print(resumo_resultados())
