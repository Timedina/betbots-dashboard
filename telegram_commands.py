"""
telegram_commands.py
Listener de comandos do Telegram para controle do bot
Comandos: /resultado /jogos /status /aprovados /filtros
"""

import requests
import json
import os
import threading
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

TOKEN  = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

_ultimo_update_id = 0
_lock = threading.Lock()
_inicializado = False


def get_updates():
    global _ultimo_update_id, _inicializado
    try:
        url  = f'https://api.telegram.org/bot{TOKEN}/getUpdates'

        # Na primeira chamada, descarta updates antigos
        if not _inicializado:
            resp = requests.get(url, params={'offset': -1, 'timeout': 1}, timeout=5)
            if resp.status_code == 200:
                results = resp.json().get('result', [])
                if results:
                    _ultimo_update_id = results[-1]['update_id']
            _inicializado = True
            return []

        resp = requests.get(url, params={'offset': _ultimo_update_id + 1, 'timeout': 5}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get('result', [])
    except:
        pass
    return []


def responder(chat_id, texto):
    try:
        url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
        requests.post(url, json={
            'chat_id': chat_id,
            'text': texto,
            'parse_mode': 'Markdown'
        }, timeout=10)
    except Exception as e:
        print(f'[Telegram] Erro ao responder comando: {e}')


def processar_comandos(agendador, stats, resultado_jogos, carregar_aprovados_do_dia,
                        carregar_reprovados_do_dia, FUSO_BRASILIA,
                        ODD_10_MINIMA, ODD_10_MAXIMA, ODD_01_MINIMA, ODD_01_MAXIMA,
                        ODD_FAVORITO_MAX, ODD_OVER15_MINIMA, ODD_OVER15_MAXIMA,
                        ODD_BTTS_MINIMA, ODD_BTTS_MAXIMA,
                        LIQUIDEZ_MINIMA_CS_DISPONIVEL, LIQUIDEZ_MINIMA_CS_TOTAL):
    global _ultimo_update_id

    updates = get_updates()
    if not updates:
        return

    for update in updates:
        _ultimo_update_id = update['update_id']
        msg = update.get('message', {})
        chat_id = str(msg.get('chat', {}).get('id', ''))
        texto   = msg.get('text', '').strip().lower()

        # Seguranca: so responde ao chat autorizado
        if chat_id != str(CHAT_ID):
            continue

        agora_br  = datetime.now(FUSO_BRASILIA)
        data_hoje = agora_br.strftime('%d/%m/%Y')

        # ── /resultado ────────────────────────────────────────────
        if texto == '/resultado':
            try:
                resultado_jogos.atualizar_resultados_do_dia(verbose=False)
                resumo = resultado_jogos.resumo_resultados()
                responder(chat_id, resumo)
            except Exception as e:
                responder(chat_id, f'❌ Erro ao buscar resultado: {e}')

        # ── /jogos ────────────────────────────────────────────────
        elif texto == '/jogos':
            aguardando = [(eid, d) for eid, d in agendador.jogos.items()
                          if d['estado'] == 'aguardando']
            if not aguardando:
                responder(chat_id, '📋 *Fila vazia* — nenhum jogo aguardando análise.')
            else:
                linhas = [f'📋 *Fila de jogos — {data_hoje}*',
                          f'━━━━━━━━━━━━━━━━━━━━',
                          f'Total: {len(aguardando)} jogo(s)\n']
                for eid, d in sorted(aguardando, key=lambda x: x[1]['open_date']):
                    try:
                        inicio = datetime.fromisoformat(d['open_date'].replace('Z', '+00:00'))
                        horario = inicio.astimezone(FUSO_BRASILIA).strftime('%H:%M')
                        mins = int((inicio - datetime.now(timezone.utc)).total_seconds() / 60)
                        tempo = f'+{mins}min' if mins >= 0 else f'{abs(mins)}min atrás'
                    except:
                        horario = '--:--'
                        tempo   = '?'
                    linhas.append(f'⏰ {horario} ({tempo}) — {d["nome_jogo"]}')
                responder(chat_id, '\n'.join(linhas))

        # ── /status ───────────────────────────────────────────────
        elif texto == '/status':
            uptime   = datetime.now(FUSO_BRASILIA) - stats.inicio_sessao
            horas    = int(uptime.total_seconds() // 3600)
            minutos  = int((uptime.total_seconds() % 3600) // 60)
            aguardando = sum(1 for d in agendador.jogos.values() if d['estado'] == 'aguardando')
            reprovados = stats.jogos_analisados - stats.jogos_aprovados
            responder(chat_id,
                f'🤖 *Status do Bot*\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'✅ Online há: *{horas}h {minutos}min*\n'
                f'📋 Fila: *{aguardando}* jogos aguardando\n'
                f'🔍 Analisados: *{stats.jogos_analisados}*\n'
                f'✅ Aprovados: *{stats.jogos_aprovados}*\n'
                f'⛔ Reprovados: *{reprovados}*\n'
                f'📡 Chamadas API: *{stats.chamadas_api}*\n'
                f'💹 Alertas movimento: *{stats.alertas_movimento}*\n'
                f'🕐 {agora_br.strftime("%d/%m/%Y %H:%M:%S")}'
            )

        # ── /aprovados ────────────────────────────────────────────
        elif texto == '/aprovados':
            aprovados = carregar_aprovados_do_dia()
            if not aprovados:
                responder(chat_id, f'📋 Nenhum jogo aprovado hoje ({data_hoje}).')
            else:
                linhas = [f'✅ *Aprovados hoje — {data_hoje}*',
                          f'━━━━━━━━━━━━━━━━━━━━']
                for info in sorted(aprovados.values(), key=lambda x: x.get('horario', '')):
                    result  = info.get('resultado_geral', '')
                    emoji   = '✅' if result == 'VITORIA' else ('❌' if result == 'PERDA' else '⏳')
                    placar  = f' | {info["placar_final"]}' if info.get('placar_final') else ''
                    pnl     = f' | PnL: {info["pnl_estimado"]}u' if info.get('pnl_estimado') else ''
                    linhas.append(
                        f'{emoji} {info["horario"]} {info["nome_jogo"]}\n'
                        f'   LAY 1-0@{info["odd_10"]} | 0-1@{info["odd_01"]}'
                        f'{placar}{pnl}'
                    )
                responder(chat_id, '\n'.join(linhas))

        # ── /filtros ──────────────────────────────────────────────
        elif texto == '/filtros':
            responder(chat_id,
                f'⚙️ *Filtros Ativos*\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'🎯 *Correct Score LAY*\n'
                f'  1-0: {ODD_10_MINIMA} — {ODD_10_MAXIMA}\n'
                f'  0-1: {ODD_01_MINIMA} — {ODD_01_MAXIMA}\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'⭐ *Favorito (Match Odds)*\n'
                f'  Máximo: {ODD_FAVORITO_MAX}\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'📈 *Over 1.5*\n'
                f'  Faixa: {ODD_OVER15_MINIMA} — {ODD_OVER15_MAXIMA}\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'🤝 *BTTS (Ambas Marcam)*\n'
                f'  Faixa: {ODD_BTTS_MINIMA} — {ODD_BTTS_MAXIMA}\n'
                f'━━━━━━━━━━━━━━━━━━━━\n'
                f'💧 *Liquidez CS*\n'
                f'  Disponível mín: £{LIQUIDEZ_MINIMA_CS_DISPONIVEL}\n'
                f'  Total mín: £{LIQUIDEZ_MINIMA_CS_TOTAL}'
            )

        # ── /reprovados ───────────────────────────────────────────
        elif texto == '/reprovados':
            reprovados = carregar_reprovados_do_dia()
            if not reprovados:
                responder(chat_id, f'📋 Nenhuma reprovação registrada hoje.')
            else:
                contagem = {}
                for dados in reprovados.values():
                    for tent in dados['tentativas']:
                        for motivo in tent['motivos']:
                            chave = motivo.split(':')[0].strip()
                            contagem[chave] = contagem.get(chave, 0) + 1
                top = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:8]
                linhas = [f'⛔ *Reprovações — {data_hoje}*',
                          f'Jogos únicos: {len(reprovados)}\n',
                          '*Top motivos:*']
                for motivo, n in top:
                    linhas.append(f'  • {motivo}: *{n}x*')
                responder(chat_id, '\n'.join(linhas))

        # ── /historico ───────────────────────────────────────────
        elif texto == '/historico':
            try:
                import os, json as _json
                fuso = FUSO_BRASILIA
                pasta = 'dados_bot'
                arquivos = sorted([f for f in os.listdir(pasta) if f.startswith('aprovados_')])
                if not arquivos:
                    responder(chat_id, 'Nenhum historico encontrado.')
                else:
                    linhas_msg = ['📋 *Histórico de Jogos*', '━━━━━━━━━━━━━━━━━━━━']
                    total_v = total_d = total_p = 0
                    pnl_geral = 0.0
                    for arq in arquivos:
                        data_str = arq.replace('aprovados_', '').replace('.json', '')
                        with open(os.path.join(pasta, arq)) as ff:
                            jogos = _json.load(ff)
                        if not jogos: continue
                        v = sum(1 for j in jogos.values() if j.get('resultado_geral') == 'VITORIA')
                        d = sum(1 for j in jogos.values() if j.get('resultado_geral') == 'PERDA')
                        p = sum(1 for j in jogos.values() if not j.get('resultado_geral'))
                        pnl = sum(j.get('pnl_estimado', 0) or 0 for j in jogos.values())
                        total_v += v; total_d += d; total_p += p; pnl_geral += pnl
                        sinal = '+' if pnl >= 0 else ''
                        linhas_msg.append(f'📅 *{data_str}* | {len(jogos)} jogos | {v}V/{d}D/{p}P | PnL: {sinal}{round(pnl,1)}u')
                    linhas_msg.append('━━━━━━━━━━━━━━━━━━━━')
                    sinal_g = '+' if pnl_geral >= 0 else ''
                    linhas_msg.append(f'📊 *Total:* {total_v}V/{total_d}D/{total_p}P | PnL: *{sinal_g}{round(pnl_geral,1)}u*')
                    responder(chat_id, '\n'.join(linhas_msg))
            except Exception as e:
                responder(chat_id, 'Erro: ' + str(e))

        # ── /simulacoes ──────────────────────────────────────────────
        elif texto == '/simulacoes':
            try:
                import os, json as _json
                pasta = 'dados_bot'
                arquivos = sorted([f for f in os.listdir(pasta) if f.startswith('aprovados_')])
                linhas_msg = ['🎰 *Simulações de Apostas*', '━━━━━━━━━━━━━━━━━━━━']
                total_sim = 0
                pnl_sim = 0.0
                for arq in arquivos:
                    data_str = arq.replace('aprovados_', '').replace('.json', '')
                    with open(os.path.join(pasta, arq)) as ff:
                        jogos = _json.load(ff)
                    for info in jogos.values():
                        if not info.get('placar_lay'): continue
                        total_sim += 1
                        pnl = info.get('pnl_estimado', 0) or 0
                        pnl_sim += pnl
                        result = info.get('resultado_geral', 'Pendente')
                        emoji = '✅' if result == 'VITORIA' else ('❌' if result == 'PERDA' else '⏳')
                        placar = info.get('placar_final', '?')
                        lay = info.get('placar_lay', '')
                        odd = info.get('odd_lay', 0)
                        sinal = '+' if pnl >= 0 else ''
                        linhas_msg.append(f'{emoji} {data_str} | {info["nome_jogo"]}')
                        linhas_msg.append(f'   LAY {lay}@{odd} | Placar: {placar} | PnL: {sinal}{pnl}u')
                if total_sim == 0:
                    responder(chat_id, 'Nenhuma simulacao encontrada ainda.')
                else:
                    linhas_msg.append('━━━━━━━━━━━━━━━━━━━━')
                    sinal_t = '+' if pnl_sim >= 0 else ''
                    linhas_msg.append(f'💰 *PnL Total Simulado: {sinal_t}{round(pnl_sim,1)}u* ({total_sim} jogos)')
                    responder(chat_id, '\n'.join(linhas_msg))
            except Exception as e:
                responder(chat_id, 'Erro: ' + str(e))

        # ── /odds ────────────────────────────────────────────────
        elif texto.startswith('/odds'):
            partes = texto.replace('/odds', '').strip()
            if not partes:
                responder(chat_id, '/odds Rangers Torino\n_Separe os times por espaco_')
            else:
                times = [t.strip() for t in partes.split() if t.strip()]
                responder(chat_id, 'Buscando odds para: ' + ', '.join(times) + '...')
                try:
                    resultado = buscar_odds_por_times(times)
                    responder(chat_id, resultado)
                except Exception as e:
                    responder(chat_id, 'Erro: ' + str(e))

        # ── comando desconhecido ──────────────────────────────────
        elif texto.startswith('/'):
            responder(chat_id,
                '❓ *Comandos disponíveis:*\n'
                '/resultado — PnL e resultados do dia\n'
                '/jogos — fila de jogos aguardando\n'
                '/status — status e uptime do bot\n'
                '/aprovados — jogos aprovados hoje\n'
                '/filtros — filtros ativos\n'
                '/reprovados — motivos de reprovação\n'
                '/historico — historico de todos os dias\n'
                '/simulacoes — apostas simuladas\n'
                '/odds [times] — odds LAY dos times'
            )


def buscar_odds_por_times(nomes_times: list) -> str:
    import betfair_client as bf
    import json

    # Busca mercados CS do dia e amanha
    rpc = json.dumps({
        'jsonrpc': '2.0',
        'method': 'SportsAPING/v1.0/listMarketCatalogue',
        'params': {
            'filter': {
                'eventTypeIds': ['1'],
                'marketTypeCodes': ['CORRECT_SCORE'],
            },
            'maxResults': '1000',
            'marketProjection': ['EVENT', 'MARKET_START_TIME'],
        },
        'id': 1
    })

    mercados = bf.chamar_api(rpc) or []

    # Filtra jogos que contem algum dos times
    encontrados = {}
    for m in mercados:
        nome_jogo = m.get('event', {}).get('name', '')
        if any(t.lower() in nome_jogo.lower() for t in nomes_times):
            encontrados[m['marketId']] = {
                'nome': nome_jogo,
                'horario': m.get('marketStartTime', ''),
            }

    if not encontrados:
        return '❌ Nenhum jogo encontrado para: ' + ', '.join(nomes_times)

    # Busca odds
    books = bf.listar_odds(list(encontrados.keys()), ['EX_BEST_OFFERS'])

    linhas = ['📊 *Odds LAY — Correct Score*', '━━━━━━━━━━━━━━━━━━━━']

    for book in books:
        mid     = book['marketId']
        runners = book.get('runners', [])
        info    = encontrados.get(mid, {})
        nome    = info.get('nome', mid)

        try:
            from datetime import datetime, timezone, timedelta
            fuso    = timezone(timedelta(hours=-3))
            dt      = datetime.fromisoformat(info['horario'].replace('Z', '+00:00'))
            horario = dt.astimezone(fuso).strftime('%d/%m %H:%M')
        except:
            horario = '?'

        odd_10 = None
        odd_01 = None
        for r in runners:
            sid = r.get('selectionId')
            if sid == 2: odd_10 = bf.get_lay(r)
            if sid == 4: odd_01 = bf.get_lay(r)

        linhas.append(f'\n⚽ *{nome}* — {horario}')

        if odd_10 and odd_01:
            melhor    = '1-0' if odd_10 >= odd_01 else '0-1'
            melhor_odd = max(odd_10, odd_01)
            ok_10  = '✅' if 10 <= (odd_10 or 0) <= 22 else '❌'
            ok_01  = '✅' if 10 <= (odd_01 or 0) <= 22 else '❌'
            linhas.append(f'{ok_10} LAY 1-0 @ *{odd_10}*')
            linhas.append(f'{ok_01} LAY 0-1 @ *{odd_01}*')
            linhas.append(f'🎯 Entrar: LAY *{melhor}* @ *{melhor_odd}*')
        else:
            linhas.append('⏳ Odds ainda não disponíveis')

    linhas.append('\n✅ = dentro do filtro (10-22) | ❌ = fora')
    return '\n'.join(linhas)
