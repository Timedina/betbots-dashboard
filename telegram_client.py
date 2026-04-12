import requests
from dotenv import load_dotenv
import os

load_dotenv(override=True)

TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


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