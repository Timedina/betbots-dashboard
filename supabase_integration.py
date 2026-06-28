# ============================================================
# INTEGRACAO SUPABASE (opcional, nao quebra o bot se falhar)
# ============================================================
import os
import logging

log = logging.getLogger('bot')

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
SUPABASE_BOT_ID = os.getenv('SUPABASE_BOT_ID', '')

_client = None
SUPABASE_ATIVO = False

if SUPABASE_URL and SUPABASE_KEY and SUPABASE_BOT_ID:
    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        SUPABASE_ATIVO = True
    except Exception as e:
        logging.getLogger('bot').warning(f'  Supabase indisponivel (rodando so com JSON local): {e}')
else:
    logging.getLogger('bot').info('  Supabase nao configurado no .env - rodando so com JSON local')


def registrar_analise_supabase(info: dict, aprovado: bool, motivos: list = None):
    """Espelha o que salvar_historico_completo grava localmente, na tabela `analises`."""
    if not SUPABASE_ATIVO:
        return
    try:
        _client.table('analises').insert({
            'bot_id':              SUPABASE_BOT_ID,
            'event_id':            info.get('event_id', ''),
            'nome_jogo':           info.get('nome_jogo', ''),
            'competition':         info.get('competition', ''),
            'horario':             info.get('horario', '--:--'),
            'aprovado':            aprovado,
            'motivos':             motivos or [],
            'odd_favorito':        info.get('odd_favorito'),
            'nome_favorito':       info.get('favorito', ''),
            'odd_01':              info.get('odd_01'),
            'odd_10':              info.get('odd_10'),
            'odd_over15':          info.get('odd_over15'),
            'odd_btts':            info.get('odd_btts'),
            'liquidez_disponivel': info.get('liquidez_disponivel', 0),
            'liquidez_total':      info.get('liquidez_total', 0),
            'minuto':              info.get('minuto') or info.get('minutos'),
            'ia_motivo':           info.get('ia_motivo', ''),
        }).execute()
    except Exception as e:
        log.warning(f'  Erro ao gravar analise no Supabase: {e}')


def registrar_aposta_supabase(info: dict, res_aposta: dict):
    """Registra a aposta REAL colocada (com stake, liability, betId) na tabela `apostas`."""
    if not SUPABASE_ATIVO:
        return
    try:
        odd_lay = res_aposta.get('odd_lay') or 0
        stake = res_aposta.get('stake', 0) or 0
        liability = round(stake * (odd_lay - 1), 2) if odd_lay > 1 else 0
        _client.table('apostas').insert({
            'bot_id':       SUPABASE_BOT_ID,
            'event_id':     info.get('event_id', ''),
            'nome_jogo':    info.get('nome_jogo', ''),
            'competition':  info.get('competition', ''),
            'placar_lay':   res_aposta.get('placar_lay'),
            'odd_lay':      odd_lay,
            'stake':        stake,
            'liability':    liability,
            'market_id':    info.get('market_id_cs', ''),
            'bet_id':       str(res_aposta.get('betId', '')),
            'simulado':     res_aposta.get('simulado', True),
            'status':       'PENDENTE',
        }).execute()
    except Exception as e:
        log.warning(f'  Erro ao gravar aposta no Supabase: {e}')


def atualizar_resultado_aposta_supabase(event_id: str, resultado_geral: str, placar_final: str, pnl: float):
    """Atualiza uma aposta existente com o resultado final (VITORIA/PERDA) e o PnL."""
    if not SUPABASE_ATIVO:
        return
    try:
        status = 'VITORIA' if resultado_geral == 'VITORIA' else 'PERDA'
        _client.table('apostas').update({
            'status':       status,
            'placar_final': placar_final,
            'pnl':          pnl,
            'resolvido_em': 'now()',
        }).eq('bot_id', SUPABASE_BOT_ID).eq('event_id', str(event_id)).eq('status', 'PENDENTE').execute()
    except Exception as e:
        log.warning(f'  Erro ao atualizar resultado no Supabase: {e}')
# ============================================================
# FILTROS DINAMICOS (lidos do Supabase, editaveis pelo dashboard)
# ============================================================
import time

_filtros_cache = {}
_filtros_cache_em = 0
FILTROS_TTL_SEGUNDOS = 300  # recarrega no maximo a cada 5 minutos


def carregar_filtros() -> dict:
    """Busca os filtros configurados na tabela `filtros` do Supabase, com cache de 5 min.
    Retorna dict tipo {'ODD_01_MAXIMA': 18.0, 'ODD_FAVORITO_MAX_COPA': 2.5, ...}.
    Se o Supabase estiver fora do ar, retorna o que tiver em cache (ou {} se nunca carregou)."""
    global _filtros_cache, _filtros_cache_em
    agora = time.time()
    if _filtros_cache and (agora - _filtros_cache_em) < FILTROS_TTL_SEGUNDOS:
        return _filtros_cache
    if not SUPABASE_ATIVO:
        return _filtros_cache
    try:
        bot_id_atual = os.getenv('SUPABASE_BOT_ID_OVERRIDE', os.getenv('SUPABASE_BOT_ID', SUPABASE_BOT_ID))
        resp = (
            _client.table('filtros')
            .select('chave,valor,valor_copa,valor_texto')
            .eq('bot_id', bot_id_atual)
            .execute()
        )
        novo = {}
        for row in resp.data:
            if row.get("valor") is not None:
                novo[row["chave"]] = float(row["valor"])
            elif row.get("valor_texto") is not None:
                novo[row["chave"]] = row["valor_texto"]
            if row.get('valor_copa') is not None:
                novo[row['chave'] + '_COPA'] = float(row['valor_copa'])
        _filtros_cache = novo
        _filtros_cache_em = agora
    except Exception as e:
        log.warning(f'  Erro ao carregar filtros do Supabase (mantendo valores atuais): {e}')
    return _filtros_cache
