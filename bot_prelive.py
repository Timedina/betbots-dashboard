import os
import time
import json
import logging
import betfair_client as bf
from telegram_client import enviar_mensagem
from datetime import datetime, timezone, timedelta


# ============================================================
# CONFIGURACOES DO BOT PRE-LIVE
# ============================================================

LIQUIDEZ_MINIMA_CS    = 500
LIQUIDEZ_MINIMA_GOALS = 1000  # reservado para uso futuro

# Fuso horario
FUSO_BRASILIA = timezone(timedelta(hours=-3))

# Agendamento
MINUTOS_ANTES_INICIO    = 5
MINUTOS_APOS_INICIO     = 10
INTERVALO_VERIFICACAO   = 5      # minutos na janela de entrada
INTERVALO_LONGE         = 15     # minutos para jogos > 30 min antes
LIMIAR_JANELA_ENTRADA   = 30     # minutos: abaixo disso usa intervalo curto
INTERVALO_RECARGA_HORAS = 1

# Filtros Correct Score
ODD_10_MINIMA = 0
ODD_10_MAXIMA = 22.0
ODD_01_MINIMA = 0
ODD_01_MAXIMA = 22.0

# Filtros Match Odds
ODD_FAVORITO_MAX = 2.0

# Filtros Over 1.5
ODD_OVER15_MINIMA = 1.15
ODD_OVER15_MAXIMA = 1.35

# Filtros Ambas Marcam (BTTS)
ODD_BTTS_MINIMA = 1.55
ODD_BTTS_MAXIMA = 2.30

# Reconexão automática
MAX_ERROS_CONSECUTIVOS = 5
ESPERA_APOS_ERRO       = 30

# Tipos de mercado permitidos (melhoria #5)
MARKET_TYPES_FILTRO = ['MATCH_ODDS', 'CORRECT_SCORE', 'OVER_UNDER_15', 'BOTH_TEAMS_TO_SCORE']

# ============================================================
# LIGAS PERMITIDAS
# ============================================================
LIGAS_PERMITIDAS = []

# ============================================================
# PASTAS E LOGS
# ============================================================
PASTA_DADOS = 'dados_bot'
PASTA_LOGS  = 'logs'
os.makedirs(PASTA_DADOS, exist_ok=True)
os.makedirs(PASTA_LOGS,  exist_ok=True)


def configurar_log():
    data_hoje = datetime.now(FUSO_BRASILIA).strftime('%Y-%m-%d')
    log_file  = os.path.join(PASTA_LOGS, f'bot_{data_hoje}.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('bot')

log = configurar_log()


# ============================================================
# ARQUIVO DE PERSISTENCIA
# ============================================================

def arquivo_do_dia() -> str:
    data = datetime.now(FUSO_BRASILIA).strftime('%Y-%m-%d')
    return os.path.join(PASTA_DADOS, f'aprovados_{data}.json')


def carregar_aprovados_do_dia() -> dict:
    path = arquivo_do_dia()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.warning(f'Erro ao carregar aprovados: {e}')
    return {}


def salvar_aprovado(info: dict):
    aprovados = carregar_aprovados_do_dia()
    aprovados[info['event_id']] = {
        'nome_jogo':    info['nome_jogo'],
        'competition':  info.get('competition', ''),
        'horario':      info.get('horario', '--:--'),
        'odd_10':       info.get('odd_10'),
        'odd_01':       info.get('odd_01'),
        'odd_over15':   info.get('odd_over15'),
        'odd_btts':     info.get('odd_btts'),
        'odd_favorito': info.get('odd_favorito'),
        'favorito':     info.get('favorito', ''),
        'liquidez_cs':  info.get('liquidez_cs', 0),
        'market_id_cs': info.get('market_id_cs', ''),
        'salvo_em':     datetime.now(FUSO_BRASILIA).strftime('%H:%M:%S'),
    }
    with open(arquivo_do_dia(), 'w', encoding='utf-8') as f:
        json.dump(aprovados, f, ensure_ascii=False, indent=2)


# ============================================================
# ESTATISTICAS DA SESSAO
# ============================================================

class Estatisticas:
    def __init__(self):
        self.jogos_analisados    = 0
        self.jogos_aprovados     = 0
        self.jogos_pulados_cache = 0    # melhoria #1
        self.chamadas_api        = 0    # rastrear economia de chamadas
        self.motivos_reprovacao: dict = {}
        self.erros_consecutivos  = 0
        self.inicio_sessao       = datetime.now(FUSO_BRASILIA)

    def registrar_reprovacao(self, motivos: list):
        self.jogos_analisados += 1
        for motivo in motivos:
            chave = motivo.split(':')[0].strip()
            self.motivos_reprovacao[chave] = self.motivos_reprovacao.get(chave, 0) + 1

    def registrar_aprovacao(self):
        self.jogos_analisados  += 1
        self.jogos_aprovados   += 1
        self.erros_consecutivos = 0

    def registrar_pulado(self):
        self.jogos_pulados_cache += 1

    def registrar_chamada_api(self, n: int = 1):
        self.chamadas_api += n

    def registrar_erro(self):
        self.erros_consecutivos += 1

    def registrar_sucesso(self):
        self.erros_consecutivos = 0

    def resumo_telegram(self) -> str:
        uptime  = datetime.now(FUSO_BRASILIA) - self.inicio_sessao
        horas   = int(uptime.total_seconds() // 3600)
        minutos = int((uptime.total_seconds() % 3600) // 60)
        reprovados  = self.jogos_analisados - self.jogos_aprovados
        top_motivos = sorted(self.motivos_reprovacao.items(), key=lambda x: x[1], reverse=True)[:3]
        motivos_str = ' | '.join([f'{m}: {n}x' for m, n in top_motivos]) or 'Nenhum'
        return (
            f'📊 *Estatísticas da Sessão*\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'⏱ Uptime: {horas}h {minutos}min\n'
            f'🔍 Analisados: {self.jogos_analisados}\n'
            f'✅ Aprovados: {self.jogos_aprovados}\n'
            f'⛔ Reprovados: {reprovados}\n'
            f'⏭ Pulados (cache): {self.jogos_pulados_cache}\n'
            f'📡 Chamadas API: {self.chamadas_api}\n'
            f'📋 Top motivos: {motivos_str}'
        )

stats = Estatisticas()


# ============================================================
# CACHE DE JOGOS DESCARTAVEIS (Melhoria #1)
# ============================================================

# Motivos que não mudam com o tempo — inutile reanalizar
MOTIVOS_PERMANENTES = {
    'Liga nao permitida',
    'Sem Correct Score',
    'Sem Match Odds',
}

class CacheEventos:
    """
    Armazena event_ids que foram reprovados por motivos permanentes.
    Esses jogos são pulados em todos os ciclos futuros do dia.
    """
    def __init__(self):
        self._pulados: dict = {}  # event_id -> motivo

    def deve_pular(self, event_id: str) -> bool:
        return event_id in self._pulados

    def registrar(self, event_id: str, motivo: str):
        self._pulados[event_id] = motivo
        log.debug(f'  Cache: {event_id} bloqueado — {motivo}')

    def total(self) -> int:
        return len(self._pulados)

cache_eventos = CacheEventos()


# ============================================================
# SAUDE E ALERTAS
# ============================================================

def verificar_telegram() -> bool:
    try:
        enviar_mensagem('🔧 _Verificação de saúde — Telegram OK_')
        return True
    except Exception as e:
        log.error(f'Telegram não está funcionando: {e}')
        return False


def alerta_bot_caiu(motivo: str):
    try:
        enviar_mensagem(
            f'🚨 *BOT PARADO*\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'❌ Motivo: {motivo}\n'
            f'🕐 Horário: {datetime.now(FUSO_BRASILIA).strftime("%H:%M:%S")}\n'
            f'⚠️ _Reinicie o bot manualmente na VM._'
        )
    except:
        pass


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

def utc_para_brasilia(open_date_str: str) -> str:
    try:
        inicio = datetime.fromisoformat(open_date_str.replace('Z', '+00:00'))
        return inicio.astimezone(FUSO_BRASILIA).strftime('%H:%M')
    except:
        return '--:--'


def tempo_para_inicio(open_date_str: str) -> float:
    try:
        inicio = datetime.fromisoformat(open_date_str.replace('Z', '+00:00'))
        return (inicio - datetime.now(timezone.utc)).total_seconds() / 60
    except:
        return 999


def buscar_todos_jogos_do_dia() -> list:
    agora_brasilia      = datetime.now(FUSO_BRASILIA)
    inicio_dia_brasilia = agora_brasilia.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia_brasilia    = agora_brasilia.replace(hour=23, minute=59, second=59, microsecond=0)
    inicio_utc = inicio_dia_brasilia.astimezone(timezone.utc)
    fim_utc    = fim_dia_brasilia.astimezone(timezone.utc)
    rpc = json.dumps({
        'jsonrpc': '2.0', 'method': 'SportsAPING/v1.0/listEvents',
        'params': {'filter': {'eventTypeIds': ['1'],
            'marketStartTime': {
                'from': inicio_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'to':   fim_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
            }}},
        'id': 1
    })
    stats.registrar_chamada_api()
    return bf.chamar_api(rpc) or []


def get_odd_runner(book_runners, runners_map, nome):
    for runner in book_runners:
        if runners_map.get(runner['selectionId'], '') == nome:
            return bf.get_lay(runner)
    return None


def get_odd_back_runner(book_runners, runners_map, nome):
    for runner in book_runners:
        if runners_map.get(runner['selectionId'], '') == nome:
            return bf.get_back(runner)
    return None


# ============================================================
# MELHORIA #5: listar_mercados com filtro de marketType
# ============================================================

def listar_mercados_filtrado(event_id: str) -> list:
    """
    Chama listMarketCatalogue filtrando pelos tipos de mercado
    que realmente usamos, evitando escanteios, cartões etc.
    """
    stats.registrar_chamada_api()
    return bf.listar_mercados(event_id, market_types=MARKET_TYPES_FILTRO)


# ============================================================
# MELHORIA #3: verificacao em cascata — apenas Match Odds
# ============================================================

def verificar_favorito_rapido(event_id: str, mercados: list) -> tuple:
    """
    Verifica APENAS o Match Odds para checar o favorito.
    Retorna (aprovado: bool, odd_favorito: float|None, nome_favorito: str|None, book_mo: dict|None)
    """
    mo_mercado = next((m for m in mercados if m['marketName'] == 'Match Odds'), None)
    if not mo_mercado:
        return False, None, None, None

    stats.registrar_chamada_api()
    books = bf.listar_odds([mo_mercado['marketId']], ['EX_BEST_OFFERS'])
    if not books:
        return False, None, None, None

    book_mo         = books[0]
    runners_mo_map  = {r['selectionId']: r['runnerName'] for r in mo_mercado.get('runners', [])}
    runners_mo_book = book_mo.get('runners', [])

    odd_favorito  = None
    nome_favorito = None
    for runner in runners_mo_book:
        back   = bf.get_back(runner)
        nome_r = runners_mo_map.get(runner['selectionId'], '')
        if nome_r == 'The Draw':
            continue
        if back and (odd_favorito is None or back < odd_favorito):
            odd_favorito  = back
            nome_favorito = nome_r

    if not odd_favorito or odd_favorito > ODD_FAVORITO_MAX:
        return False, odd_favorito, nome_favorito, None

    return True, odd_favorito, nome_favorito, book_mo


# ============================================================
# MELHORIA #2: batch de mercados restantes
# ============================================================

def buscar_mercados_restantes_batch(
    cs_mercado: dict,
    over15_mercado,
    btts_mercado
) -> dict:
    """
    Busca CS + Over1.5 + BTTS em uma única chamada batch.
    Retorna dict {marketId: book}
    """
    ids = [cs_mercado['marketId']]
    if over15_mercado:
        ids.append(over15_mercado['marketId'])
    if btts_mercado:
        ids.append(btts_mercado['marketId'])

    stats.registrar_chamada_api()
    books = bf.listar_odds(ids, ['EX_BEST_OFFERS'])
    if not books:
        return {}
    return {b['marketId']: b for b in books}


# ============================================================
# ANALISE PRINCIPAL (refatorada com melhorias #1, #2, #3, #5)
# ============================================================

def analisar_jogo(event_id: str, nome_jogo: str, minutos: float) -> dict:
    resultado = {
        'aprovado': False,
        'motivo_reprovacao': [],
        'nome_jogo': nome_jogo,
        'minutos': int(minutos),
        'event_id': event_id,
    }

    # Melhoria #1: checar cache antes de qualquer chamada de API
    if cache_eventos.deve_pular(event_id):
        resultado['motivo_reprovacao'].append('Cache: reprovado permanente')
        stats.registrar_pulado()
        return resultado

    # Melhoria #5: busca mercados já filtrados por tipo
    mercados = listar_mercados_filtrado(event_id)
    if not mercados:
        resultado['motivo_reprovacao'].append('Sem mercados')
        return resultado

    cs_mercado     = next((m for m in mercados if m['marketName'] == 'Correct Score'), None)
    mo_mercado     = next((m for m in mercados if m['marketName'] == 'Match Odds'), None)
    over15_mercado = next((m for m in mercados if m['marketName'] == 'Over/Under 1.5 Goals'), None)
    btts_mercado   = next((m for m in mercados if m['marketName'] == 'Both teams to Score?'), None)

    if not cs_mercado:
        resultado['motivo_reprovacao'].append('Sem Correct Score')
        cache_eventos.registrar(event_id, 'Sem Correct Score')   # permanente
        return resultado
    if not mo_mercado:
        resultado['motivo_reprovacao'].append('Sem Match Odds')
        cache_eventos.registrar(event_id, 'Sem Match Odds')       # permanente
        return resultado

    competition = cs_mercado.get('competition', {}).get('name', '')
    if LIGAS_PERMITIDAS:
        if not any(liga.lower() in competition.lower() for liga in LIGAS_PERMITIDAS):
            motivo = f'Liga nao permitida: {competition}'
            resultado['motivo_reprovacao'].append(motivo)
            cache_eventos.registrar(event_id, motivo)              # permanente
            return resultado

    resultado['competition'] = competition

    # Melhoria #3: filtro em cascata — verificar favorito ANTES de pedir CS/Over/BTTS
    fav_ok, odd_favorito, nome_favorito, book_mo = verificar_favorito_rapido(event_id, mercados)
    if not fav_ok:
        resultado['motivo_reprovacao'].append(f'Favorito fora faixa: {odd_favorito}')
        # NÃO adiciona ao cache permanente — odd do favorito muda com o tempo
        return resultado

    resultado['favorito']     = nome_favorito
    resultado['odd_favorito'] = odd_favorito

    # Melhoria #2: buscar CS + Over1.5 + BTTS em uma única chamada batch
    books_restantes = buscar_mercados_restantes_batch(cs_mercado, over15_mercado, btts_mercado)
    if not books_restantes:
        resultado['motivo_reprovacao'].append('Sem dados de odds (batch)')
        return resultado

    # ── Correct Score ──
    book_cs = books_restantes.get(cs_mercado['marketId'])
    if not book_cs:
        resultado['motivo_reprovacao'].append('Sem dados CS')
        return resultado

    liquidez_cs = book_cs.get('totalMatched', 0)
    if liquidez_cs < LIQUIDEZ_MINIMA_CS:
        resultado['motivo_reprovacao'].append(f'Liquidez CS baixa: £{liquidez_cs:.0f}')
        return resultado

    runners_cs_map  = {r['selectionId']: r['runnerName'] for r in cs_mercado.get('runners', [])}
    runners_cs_book = book_cs.get('runners', [])

    odd_10 = get_odd_runner(runners_cs_book, runners_cs_map, '1 - 0')
    odd_01 = get_odd_runner(runners_cs_book, runners_cs_map, '0 - 1')

    if not odd_10:
        resultado['motivo_reprovacao'].append('Sem odd 1-0')
        return resultado
    if not odd_01:
        resultado['motivo_reprovacao'].append('Sem odd 0-1')
        return resultado
    if not (ODD_10_MINIMA <= odd_10 <= ODD_10_MAXIMA):
        resultado['motivo_reprovacao'].append(f'Odd 1-0 fora faixa: {odd_10}')
        return resultado
    if not (ODD_01_MINIMA <= odd_01 <= ODD_01_MAXIMA):
        resultado['motivo_reprovacao'].append(f'Odd 0-1 fora faixa: {odd_01}')
        return resultado

    resultado['odd_10']       = odd_10
    resultado['odd_01']       = odd_01
    resultado['liquidez_cs']  = liquidez_cs
    resultado['market_id_cs'] = cs_mercado['marketId']

    # ── Over 1.5 ──
    if over15_mercado:
        book_over15 = books_restantes.get(over15_mercado['marketId'])
        if book_over15:
            runners_over15_map = {r['selectionId']: r['runnerName'] for r in over15_mercado.get('runners', [])}
            odd_over15 = get_odd_back_runner(book_over15.get('runners', []), runners_over15_map, 'Over 1.5 Goals')
            resultado['odd_over15'] = odd_over15
            if odd_over15 and not (ODD_OVER15_MINIMA <= odd_over15 <= ODD_OVER15_MAXIMA):
                resultado['motivo_reprovacao'].append(f'Over 1.5 fora faixa: {odd_over15}')
                return resultado
        else:
            resultado['odd_over15'] = None
    else:
        resultado['odd_over15'] = None

    # ── BTTS ──
    if btts_mercado:
        book_btts = books_restantes.get(btts_mercado['marketId'])
        if book_btts:
            runners_btts_map = {r['selectionId']: r['runnerName'] for r in btts_mercado.get('runners', [])}
            odd_btts = get_odd_back_runner(book_btts.get('runners', []), runners_btts_map, 'Yes')
            resultado['odd_btts'] = odd_btts
            if odd_btts and not (ODD_BTTS_MINIMA <= odd_btts <= ODD_BTTS_MAXIMA):
                resultado['motivo_reprovacao'].append(f'BTTS fora faixa: {odd_btts}')
                return resultado
        else:
            resultado['odd_btts'] = None
    else:
        resultado['odd_btts'] = None

    resultado['aprovado'] = True
    return resultado


# ============================================================
# FORMATACAO
# ============================================================

def formatar_alerta(info: dict) -> str:
    over15_str = f"Over 1.5 @ *{info['odd_over15']:.2f}*" if info.get('odd_over15') else 'Over 1.5: N/A'
    btts_str   = f"Ambas Marcam @ *{info['odd_btts']:.2f}*" if info.get('odd_btts') else 'BTTS: N/A'
    minutos    = info['minutos']
    tempo_str  = f'⏰ *Inicia em:* {minutos} min' if minutos >= 0 else f'🔴 *Ao vivo:* {abs(minutos)} min de jogo'
    return (
        f'🚨 *PRE-LIVE ALERT*\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'🏆 *Liga:* {info.get("competition", "")}\n'
        f'⚽ *Jogo:* {info["nome_jogo"]}\n'
        f'{tempo_str}\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'🎯 *ESTRATEGIA: LAY Correct Score*\n'
        f'🔴 LAY *1-0* @ {info["odd_10"]:.2f}\n'
        f'🔴 LAY *0-1* @ {info["odd_01"]:.2f}\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'📊 *FILTROS CONFIRMADOS*\n'
        f'⭐ Favorito: {info.get("favorito", "")} @ {info.get("odd_favorito", 0):.2f}\n'
        f'📈 {over15_str}\n'
        f'🤝 {btts_str}\n'
        f'💧 Liquidez CS: £{info.get("liquidez_cs", 0):,.0f}\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'🆔 `{info.get("market_id_cs", "")}`\n'
        f'⚠️ _Saida: ao 1o gol ou odds subirem 20%+_'
    )


def gerar_resumo_diario():
    aprovados = carregar_aprovados_do_dia()
    data_hoje = datetime.now(FUSO_BRASILIA).strftime('%d/%m/%Y')
    if not aprovados:
        enviar_mensagem(
            f'📋 *Resumo Diário — {data_hoje}*\n'
            f'━━━━━━━━━━━━━━━━━━━━\n'
            f'_Nenhum jogo aprovado até agora hoje._\n'
            f'_Os alertas serão enviados conforme os jogos forem detectados._'
        )
        return
    lista = sorted(aprovados.values(), key=lambda x: x.get('horario', ''))
    linhas = [
        f'📋 *Resumo Diário — {data_hoje}* (Horário de Brasília)',
        f'━━━━━━━━━━━━━━━━━━━━',
        f'✅ Aprovados hoje: {len(lista)}',
        f'━━━━━━━━━━━━━━━━━━━━',
    ]
    for i, info in enumerate(lista, 1):
        over15_str = f"O1.5 @ {info['odd_over15']:.2f}" if info.get('odd_over15') else 'O1.5: N/A'
        btts_str   = f"BTTS @ {info['odd_btts']:.2f}"   if info.get('odd_btts')   else 'BTTS: N/A'
        linhas += [
            f'\n*{i}. {info["nome_jogo"]}*',
            f'🏆 {info.get("competition", "")} | 🕐 {info["horario"]} | 🔔 Alertado: {info.get("salvo_em", "--")}',
            f'🔴 LAY 1-0 @ *{info["odd_10"]:.2f}* | LAY 0-1 @ *{info["odd_01"]:.2f}*',
            f'⭐ {info.get("favorito", "")} @ {info.get("odd_favorito", 0):.2f} | {over15_str} | {btts_str}',
            f'💧 CS: £{info.get("liquidez_cs", 0):,.0f}',
        ]
    linhas += ['\n━━━━━━━━━━━━━━━━━━━━', '_Odds registradas no momento do alerta pré-jogo._']
    enviar_mensagem('\n'.join(linhas))


# ============================================================
# AGENDADOR
# ============================================================

class AgendadorJogos:
    def __init__(self):
        self.jogos: dict = {}

    def carregar_jogos_do_dia(self):
        log.info('Buscando lista de jogos do dia...')
        jogos_api    = buscar_todos_jogos_do_dia()
        ja_aprovados = set(carregar_aprovados_do_dia().keys())

        if not jogos_api:
            log.warning('Nenhum jogo retornado pela API Betfair!')
            enviar_mensagem('⚠️ *Atenção* — Nenhum jogo encontrado na Betfair para hoje.\n_Pode ser erro de API ou dia sem jogos._')
            return 0

        novos = 0
        for jogo in jogos_api:
            evento    = jogo.get('event', {})
            event_id  = evento.get('id')
            nome_jogo = evento.get('name', '')
            open_date = evento.get('openDate', '')
            if not event_id or not open_date:
                continue
            if event_id in ja_aprovados or event_id in self.jogos:
                continue
            try:
                inicio_utc = datetime.fromisoformat(open_date.replace('Z', '+00:00'))
                proxima    = inicio_utc - timedelta(minutes=MINUTOS_ANTES_INICIO)
            except:
                continue
            limite = inicio_utc + timedelta(minutes=MINUTOS_APOS_INICIO)
            if datetime.now(timezone.utc) > limite:
                continue
            self.jogos[event_id] = {
                'nome_jogo':           nome_jogo,
                'open_date':           open_date,
                'estado':              'aguardando',
                'proxima_verificacao': proxima,
            }
            novos += 1

        log.info(f'Jogos agendados: {novos} novos | Total ativo: {len(self.jogos)}')
        return novos

    def jogos_para_verificar_agora(self) -> list:
        agora = datetime.now(timezone.utc)
        return [(eid, d) for eid, d in self.jogos.items()
                if d['estado'] == 'aguardando' and d['proxima_verificacao'] <= agora]

    def avancar_verificacao(self, event_id: str):
        """
        Melhoria #4: intervalo dinâmico baseado no tempo até o início.
        - Mais de LIMIAR_JANELA_ENTRADA min antes: checar a cada INTERVALO_LONGE min
        - Dentro da janela de entrada: checar a cada INTERVALO_VERIFICACAO min
        """
        dados   = self.jogos[event_id]
        agora   = datetime.now(timezone.utc)
        minutos = tempo_para_inicio(dados['open_date'])

        if minutos > LIMIAR_JANELA_ENTRADA:
            intervalo = INTERVALO_LONGE
        else:
            intervalo = INTERVALO_VERIFICACAO

        try:
            inicio_utc = datetime.fromisoformat(dados['open_date'].replace('Z', '+00:00'))
        except:
            self._descartar(event_id, 'Erro ao parsear data')
            return

        limite  = inicio_utc + timedelta(minutes=MINUTOS_APOS_INICIO)
        proxima = agora + timedelta(minutes=intervalo)

        if proxima > limite:
            self._descartar(event_id, f'Janela encerrada (+{MINUTOS_APOS_INICIO} min)')
        else:
            dados['proxima_verificacao'] = proxima
            log.info(f'    → Próxima: {proxima.astimezone(FUSO_BRASILIA).strftime("%H:%M")} '
                     f'(intervalo {intervalo} min — {int(minutos)} min p/ início)')

    def marcar_aprovado(self, event_id: str):
        self.jogos[event_id]['estado'] = 'aprovado'

    def _descartar(self, event_id: str, motivo: str):
        self.jogos[event_id]['estado'] = 'descartado'
        log.info(f'    ❌ Descartado: {self.jogos[event_id]["nome_jogo"]} — {motivo}')

    def limpar_encerrados(self):
        antes = len(self.jogos)
        self.jogos = {eid: d for eid, d in self.jogos.items() if d['estado'] == 'aguardando'}
        removidos = antes - len(self.jogos)
        if removidos:
            log.info(f'  Agendador: {removidos} jogos removidos da fila')

    def status(self) -> str:
        aguardando = sum(1 for d in self.jogos.values() if d['estado'] == 'aguardando')
        return f'Fila: {aguardando} aguardando | Cache: {cache_eventos.total()} bloqueados'


def imprimir_agenda_do_dia(agendador: AgendadorJogos):
    jogos = sorted(agendador.jogos.values(), key=lambda x: x['open_date'])
    log.info('=' * 55)
    log.info(f'   AGENDA DO DIA — {datetime.now(FUSO_BRASILIA).strftime("%d/%m/%Y")} | {len(jogos)} jogos')
    log.info('=' * 55)
    hora_atual = None
    for dados in jogos:
        horario = utc_para_brasilia(dados['open_date'])
        if horario[:2] != hora_atual:
            hora_atual = horario[:2]
            log.info(f'  {hora_atual}h')
        log.info(f'    {horario}  {dados["nome_jogo"]}')


# ============================================================
# LOOP PRINCIPAL
# ============================================================

def rodar_bot():
    log.info('=' * 55)
    log.info('   BOT PRE-LIVE LAY 0x1 / 1x0')
    log.info('=' * 55)

    if not bf.login():
        alerta_bot_caiu('Falha no login Betfair')
        return

    if not verificar_telegram():
        log.error('Telegram não está respondendo. Verifique o token.')
        return

    agendador = AgendadorJogos()
    agendador.carregar_jogos_do_dia()
    imprimir_agenda_do_dia(agendador)

    ligas_msg = '\n'.join(f'  • {l}' for l in LIGAS_PERMITIDAS) if LIGAS_PERMITIDAS else '  • Todas as ligas'
    enviar_mensagem(
        f'🤖 *Bot Pre-Live LAY 0x1/1x0 iniciado!*\n'
        f'🏆 *Ligas:* {ligas_msg}\n'
        f'📅 *Jogos hoje:* {len(agendador.jogos)}\n'
        f'⏱ Janela: {MINUTOS_ANTES_INICIO} min antes até {MINUTOS_APOS_INICIO} min após início\n'
        f'🔄 Intervalo dinâmico: {INTERVALO_LONGE}min (longe) / {INTERVALO_VERIFICACAO}min (janela)'
    )
    gerar_resumo_diario()

    ultima_recarga = datetime.now(timezone.utc)

    while True:
        try:
            log.info(f'{agendador.status()} | ✅ {stats.jogos_aprovados} aprovados | '
                     f'🔍 {stats.jogos_analisados} analisados | 📡 {stats.chamadas_api} chamadas API')

            agora_utc = datetime.now(timezone.utc)
            if (agora_utc - ultima_recarga).total_seconds() >= INTERVALO_RECARGA_HORAS * 3600:
                novos = agendador.carregar_jogos_do_dia()
                ultima_recarga = agora_utc
                if novos > 0:
                    imprimir_agenda_do_dia(agendador)

            para_verificar = agendador.jogos_para_verificar_agora()

            if not para_verificar:
                proximas = [d['proxima_verificacao'] for d in agendador.jogos.values() if d['estado'] == 'aguardando']
                if proximas:
                    prox   = min(proximas)
                    espera = max(10, min(300, (prox - datetime.now(timezone.utc)).total_seconds()))
                    log.info(f'  Próxima: {prox.astimezone(FUSO_BRASILIA).strftime("%H:%M")} — aguardando {int(espera)}s')
                    time.sleep(espera)
                else:
                    log.info('  Sem jogos na fila. Aguardando 5 min...')
                    time.sleep(300)
                continue

            for event_id, dados in para_verificar:
                nome_jogo = dados['nome_jogo']
                minutos   = tempo_para_inicio(dados['open_date'])
                horario   = utc_para_brasilia(dados['open_date'])

                log.info(f'  🔍 {nome_jogo} ({horario}) | {int(minutos):+d} min')
                info = analisar_jogo(event_id, nome_jogo, minutos)

                if info['aprovado']:
                    info['horario'] = horario
                    log.info(f'  ✅ APROVADO! 1-0@{info["odd_10"]:.2f} | 0-1@{info["odd_01"]:.2f} | Fav@{info["odd_favorito"]:.2f}')
                    enviar_mensagem(formatar_alerta(info))
                    salvar_aprovado(info)
                    agendador.marcar_aprovado(event_id)
                    stats.registrar_aprovacao()
                else:
                    motivos = info['motivo_reprovacao']
                    log.info(f'  ⛔ {" | ".join(motivos)}')
                    if not any('Cache' in m for m in motivos):
                        agendador.avancar_verificacao(event_id)
                    stats.registrar_reprovacao(motivos)

            agendador.limpar_encerrados()
            stats.registrar_sucesso()

        except KeyboardInterrupt:
            log.info('Bot encerrado pelo usuário.')
            enviar_mensagem(f'🛑 *Bot encerrado.*\n{stats.resumo_telegram()}')
            break

        except Exception as e:
            stats.registrar_erro()
            log.error(f'Erro ({stats.erros_consecutivos}/{MAX_ERROS_CONSECUTIVOS}): {e}')
            if stats.erros_consecutivos >= MAX_ERROS_CONSECUTIVOS:
                alerta_bot_caiu(f'Muitos erros seguidos: {e}')
                break
            time.sleep(ESPERA_APOS_ERRO)
            bf.login()


if __name__ == '__main__':
    rodar_bot()
