#!/usr/bin/env python3
"""
API do Dashboard — Bot Betfair
Roda na VM e serve os dados reais do bot para o painel web
"""

import os 
import json
import subprocess
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

FUSO_BRASILIA = timezone(timedelta(hours=-3))
PASTA_DADOS   = os.path.expanduser('~/bot-prelive-betfair/dados_bot')
PASTA_LOGS    = os.path.expanduser('~/bot-prelive-betfair/logs')
BOT_START_FILE = os.path.expanduser('~/.bot_start_time')


def agora_brasilia():
    return datetime.now(FUSO_BRASILIA)


def carregar_aprovados_do_dia() -> dict:
    data = agora_brasilia().strftime('%Y-%m-%d')
    path = os.path.join(PASTA_DADOS, f'aprovados_{data}.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def bot_esta_rodando() -> bool:
    """Verifica se o bot está rodando via screen"""
    try:
        result = subprocess.run(
            ['screen', '-ls', 'bot'],
            capture_output=True, text=True
        )
        return 'bot' in result.stdout
    except:
        return False


def get_uptime_min() -> int:
    """Retorna uptime do bot em minutos"""
    if not os.path.exists(BOT_START_FILE):
        return 0
    try:
        with open(BOT_START_FILE) as f:
            start_str = f.read().strip()
        start = datetime.fromisoformat(start_str)
        diff  = datetime.now() - start
        return int(diff.total_seconds() / 60)
    except:
        return 0


def ler_logs_recentes(n=15) -> list:
    """Lê as últimas N linhas do log do dia"""
    data   = agora_brasilia().strftime('%Y-%m-%d')
    path   = os.path.join(PASTA_LOGS, f'bot_{data}.log')
    linhas = []

    if not os.path.exists(path):
        return [{'time': '--:--:--', 'tipo': 'info', 'msg': 'Nenhum log hoje ainda'}]

    try:
        with open(path, 'r', encoding='utf-8') as f:
            todas = f.readlines()

        for linha in reversed(todas[-n*2:]):
            linha = linha.strip()
            if not linha:
                continue

            # Parse: "HH:MM:SS [LEVEL] mensagem"
            partes = linha.split(' ', 2)
            if len(partes) >= 3:
                time_str = partes[0]
                msg      = partes[2] if len(partes) > 2 else partes[-1]
            else:
                time_str = '--:--:--'
                msg = linha

            # Tipo baseado no conteúdo
            if '✅' in msg or 'APROVADO' in msg or 'Login OK' in msg:
                tipo = 'ok'
            elif '⛔' in msg or 'Erro' in msg or 'ERROR' in msg or 'Falha' in msg:
                tipo = 'err'
            elif '⚠️' in msg or 'WARNING' in msg:
                tipo = 'warn'
            else:
                tipo = 'info'

            linhas.append({'time': time_str, 'tipo': tipo, 'msg': msg})

            if len(linhas) >= n:
                break

    except Exception as e:
        return [{'time': '--:--:--', 'tipo': 'err', 'msg': f'Erro ao ler logs: {e}'}]

    return linhas


def contar_analisados() -> int:
    """Conta quantas verificações foram feitas hoje pelo log"""
    data = agora_brasilia().strftime('%Y-%m-%d')
    path = os.path.join(PASTA_LOGS, f'bot_{data}.log')
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return sum(1 for l in f if 'Verificando:' in l)
    except:
        return 0


def get_proximo_da_fila() -> dict:
    """Tenta ler o próximo jogo da fila do log"""
    data = agora_brasilia().strftime('%Y-%m-%d')
    path = os.path.join(PASTA_LOGS, f'bot_{data}.log')

    try:
        with open(path, 'r', encoding='utf-8') as f:
            linhas = f.readlines()

        for linha in reversed(linhas):
            if 'Próxima verificação:' in linha or 'Próxima:' in linha:
                # Extrai info da linha
                partes = linha.strip().split()
                for p in partes:
                    if ':' in p and len(p) == 5:
                        return {'hora': p, 'minutos': '?', 'nome': 'Aguardando...'}
    except:
        pass

    return None


# ============================================================
# ROTAS DA API
# ============================================================

@app.route('/')
def index():
    """Serve o painel HTML"""
    dashboard_path = os.path.expanduser('~/bot-prelive-betfair/dashboard.html')
    if os.path.exists(dashboard_path):
        return send_file(dashboard_path, max_age=0)
    return '<h1>Dashboard não encontrado. Coloque o dashboard.html na pasta do bot.</h1>'


@app.route('/api/status')
def status():
    """Retorna todos os dados para o painel"""
    rodando    = bot_esta_rodando()
    aprovados  = carregar_aprovados_do_dia()
    analisados = contar_analisados()
    uptime     = get_uptime_min() if rodando else 0
    logs       = ler_logs_recentes(15)
    proximo    = get_proximo_da_fila()

    # Formata lista de aprovados
    lista_aprovados = []
    for event_id, info in aprovados.items():
        lista_aprovados.append({
            'event_id':    event_id,
            'nome_jogo':   info.get('nome_jogo', ''),
            'competition': info.get('competition', ''),
            'horario':     info.get('horario', '--:--'),
            'odd_10':      info.get('odd_10', 0),
            'odd_01':      info.get('odd_01', 0),
            'odd_over15':  info.get('odd_over15'),
            'odd_btts':    info.get('odd_btts'),
            'odd_favorito':info.get('odd_favorito', 0),
            'favorito':    info.get('favorito', ''),
            'liquidez_cs': info.get('liquidez_cs', 0),
            'salvo_em':    info.get('salvo_em', '--:--'),
        })

    # Ordena por horário
    lista_aprovados.sort(key=lambda x: x['horario'])

    return jsonify({
        'status':     'online' if rodando else 'offline',
        'uptime_min': uptime,
        'aprovados':  lista_aprovados,
        'analisados': analisados,
        'fila':       0,  # será implementado quando bot expor essa info
        'proximo':    proximo,
        'logs':       logs,
        'hora_atual': agora_brasilia().strftime('%H:%M:%S'),
        'data_hoje':  agora_brasilia().strftime('%d/%m/%Y'),
    })


@app.route('/api/aprovados')
def aprovados():
    """Retorna apenas os jogos aprovados do dia"""
    return jsonify(carregar_aprovados_do_dia())


@app.route('/api/logs')
def logs():
    """Retorna os logs recentes"""
    return jsonify(ler_logs_recentes(30))


@app.route('/api/health')
def health():
    """Health check simples"""
    return jsonify({
        'ok':     True,
        'bot':    bot_esta_rodando(),
        'hora':   agora_brasilia().strftime('%H:%M:%S'),
    })


def carregar_reprovados_do_dia():
    data = agora_brasilia().strftime('%Y-%m-%d')
    path = os.path.join(PASTA_DADOS, f'reprovados_{data}.json')
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

@app.route('/api/reprovados')
def reprovados():
    return jsonify(carregar_reprovados_do_dia())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
