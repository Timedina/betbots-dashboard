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


def get_updates():
    global _ultimo_update_id
    try:
        url  = f'https://api.telegram.org/bot{TOKEN}/getUpdates'
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

        # ── comando desconhecido ──────────────────────────────────
        elif texto.startswith('/'):
            responder(chat_id,
                '❓ *Comandos disponíveis:*\n'
                '/resultado — PnL e resultados do dia\n'
                '/jogos — fila de jogos aguardando\n'
                '/status — status e uptime do bot\n'
                '/aprovados — jogos aprovados hoje\n'
                '/filtros — filtros ativos\n'
                '/reprovados — motivos de reprovação'
            )
