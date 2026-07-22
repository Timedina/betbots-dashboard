import time
import requests
from dotenv import load_dotenv
import os

load_dotenv(override=True)

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


_alertas_enviados = {}
_rate_limit_alertas = 600

def enviar_mensagem(texto: str, chat_id: str = None):
    """Envia mensagem para o Telegram"""
    cid = chat_id or CHAT_ID
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    try:
        resp = requests.post(url, json={
            'chat_id': cid,
            'text': texto,
            'parse_mode': 'Markdown'
        })
        if resp.status_code == 200:
            print(f'[Telegram] Mensagem enviada!')
        else:
            print(f'[Telegram] Erro: {resp.text}')
    except Exception as e:
        print(f'[Telegram] Erro: {str(e)}')


def alerta_oportunidade(jogo: str, mercado: str, odd: float, tipo: str, detalhes: str = ''):
    """Formata e envia alerta de oportunidade"""
    emoji = '🟢' if tipo == 'BACK' else '🔴'
    msg = (
        f'🚀 *ALERTA BETFAIR*\n'
        f'⚽ *Jogo:* {jogo}\n'
        f'📊 *Mercado:* {mercado}\n'
        f'{emoji} *Tipo:* {tipo}\n'
        f'💎 *Odd:* {odd}\n'
    )
    if detalhes:
        msg += f'📝 *Info:* {detalhes}\n'
    enviar_mensagem(msg)

def alerta_erro_supabase(operacao: str, tabela: str, erro_dict: dict, detalhes: str = ''):
    """Alerta de erro ao gravar no Supabase — para nao perder dados silenciosamente."""
    global _alertas_enviados
    try:
        msg_code = erro_dict.get('code', 'UNKNOWN')
        chave = (operacao, tabela, msg_code)
        agora = time.time()
        if chave in _alertas_enviados and (agora - _alertas_enviados[chave]) < _rate_limit_alertas:
            return  # Já alertamos recentemente, ignora pra não spammar
        _alertas_enviados[chave] = agora
        msg_text = erro_dict.get('message', str(erro_dict))
        
        # Prioridade do alerta baseada no tipo de erro
        if msg_code == 'PGRST204':
            emoji = '🔴🔴🔴'  # CRÍTICO — schema desincronizado
            nivel = 'CRÍTICO'
        elif 'connection' in msg_text.lower() or 'timeout' in msg_text.lower():
            emoji = '🟠'  # MODERADO — problema de rede (pode passar)
            nivel = 'REDE'
        elif msg_code == '23502':  # NOT NULL violation
            emoji = '🟡'  # WARNING — problema nos dados
            nivel = 'DADOS'
        else:
            emoji = '🟠'  # MODERADO — genérico
            nivel = 'ERRO'
        
        msg = (
            f'{emoji} *ERRO SUPABASE — {nivel}*\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'📋 Operação: {operacao}\n'
            f'🗂️  Tabela: {tabela}\n'
            f'🔧 Código: {msg_code}\n'
            f'💬 Mensagem: {msg_text}\n'
        )
        if detalhes:
            msg += f'📝 Detalhes: {detalhes}\n'
        msg += f'━━━━━━━━━━━━━━━━━━━━\n'
        
        enviar_mensagem(msg)
    except Exception as e:
        print(f'[Telegram Alerta Erro] Falha ao enviar: {e}')
