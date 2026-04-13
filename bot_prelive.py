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
INTERVALO_VERIFICACAO   = 5
INTERVALO_RECARGA_HORAS = 1  # ← agora configurável aqui

# Filtros Correct Score
ODD_10_MINIMA = 3.5
ODD_10_MAXIMA = 14.0
ODD_01_MINIMA = 6.0
ODD_01_MAXIMA = 22.0

# Filtros Match Odds
ODD_FAVORITO_MAX = 2.20

# Filtros Over 1.5
ODD_OVER15_MINIMA = 1.30
ODD_OVER15_MAXIMA = 1.50

# Filtros Ambas Marcam (BTTS)
ODD_BTTS_MINIMA = 1.55
ODD_BTTS_MAXIMA = 2.30

# Reconexão automática
MAX_ERROS_CONSECUTIVOS = 5
ESPERA_APOS_ERRO       = 30

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
        self.jogos_analisados   = 0
        self.jogos_aprovados    = 0
        self.motivos_reprovacao: dict = {}
        self.erros_consecutivos = 0
        self.inicio_sessao      = datetime.now(FUSO_BRASILIA)

    def registrar_reprovacao(self, motivos: list):
        self.jogos_analisados += 1
        for motivo in motivos:
            chave = motivo.split(':')[0].strip()
            self.motivos_reprovacao[chave] = self.motivos_reprovacao.get(chave, 0) + 1

    def registrar_aprovacao(self):
        self.jogos_analisados  += 1
        self.jogos_aprovados   += 1
        self.erros_consecutivos = 0

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
            f'📋 Top motivos: {motivos_str}'
        )

stats = Estatisticas()


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
# ANALISE PRINCIPAL
# ============================================================

def analisar_jogo(event_id: str, nome_jogo: str, minutos: float) -> dict:
    resultado = {
        'aprovado': False,
        'motivo_reprovacao': [],
        'nome_jogo': nome_jogo,
        'minutos': int(minutos),
        'event_id': event_id,
    }

    mercados = bf.listar_mercados(event_id)
    if not mercados:
        resultado['motivo_reprovacao'].append('Sem mercados')
        return resultado

    cs_mercado     = next((m for m in mercados if m['marketName'] == 'Correct Score'), None)
    mo_mercado     = next((m for m in mercados if m['marketName'] == 'Match Odds'), None)
    over15_mercado = next((m for m in mercados if m['marketName'] == 'Over/Under 1.5 Goals'), None)
    btts_mercado   = next((m for m in mercados if m['marketName'] == 'Both teams to Score?'), None)

    if not cs_mercado:
        resultado['motivo_reprovacao'].append('Sem Correct Score')
        return resultado
    if not mo_mercado:
        resultado['motivo_reprovacao'].append('Sem Match Odds')
        return resultado

    competition = cs_mercado.get('competition', {}).get('name', '')
    if LIGAS_PERMITIDAS:
        if not any(liga.lower() in competition.lower() for liga in LIGAS_PERMITIDAS):
            resultado['motivo_reprovacao'].append(f'Liga nao permitida: {competition}')
            return resultado

    resultado['competition'] = competition

    market_ids = [cs_mercado['marketId'], mo_mercado['marketId']]
    if over15_mercado:
        market_ids.append(over15_mercado['marketId'])
    if btts_mercado:
        market_ids.append(btts_mercado['marketId'])

    todos_books = bf.listar_odds(market_ids, ['EX_BEST_OFFERS'])
    if not todos_books:
        resultado['motivo_reprovacao'].append('Sem dados de odds')
        return resultado

    books_por_id = {book['marketId']: book for book in todos_books}

    book_cs = books_por_id.get(cs_mercado['marketId'])
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

    book_mo = books_por_id.get(mo_mercado['marketId'])
    if not book_mo:
        resultado['motivo_reprovacao'].append('Sem dados MO')
        return resultado

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
        resultado['motivo_reprovacao'].append(f'Favorito fora faixa: {odd_favorito}')
        return resultado

    resultado['favorito']     = nome_favorito
    resultado['odd_favorito'] = odd_favorito

    if over15_mercado:
        book_over15 = books_por_id.get(over15_mercado['marketId'])
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

    if btts_mercado:
        book_btts = books_por_id.get(btts_mercado['marketId'])
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
        dados = self.jogos[event_id]
        agora = datetime.now(timezone.utc)
        try:
            inicio_utc = datetime.fromisoformat(dados['open_date'].replace('Z', '+00:00'))
        except:
            self._descartar(event_id, 'Erro ao parsear data')
            return
        limite  = inicio_utc + timedelta(minutes=MINUTOS_APOS_INICIO)
        proxima = agora + timedelta(minutes=INTERVALO_VERIFICACAO)
        if proxima > limite:
            self._descartar(event_id, f'Janela encerrada (+{MINUTOS_APOS_INICIO} min)')
        else:
            dados['proxima_verificacao'] = proxima
            log.info(f'    → Próxima: {proxima.astimezone(FUSO_BRASILIA).strftime("%H:%M")}')

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
        return f'Fila: {aguardando} aguardando'


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
        f'⏱ Janela: {MINUTOS_ANTES_INICIO} min antes até {MINUTOS_APOS_INICIO} min após início'
    )
    gerar_resumo_diario()

    ultima_recarga = datetime.now(timezone.utc)

    while True:
        try:
            log.info(f'{agendador.status()} | ✅ {stats.jogos_aprovados} aprovados | 🔍 {stats.jogos_analisados} analisados')

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
                    log.info(f'  ⛔ {" | ".join(info["motivo_reprovacao"])}')
                    agendador.avancar_verificacao(event_id)
                    stats.registrar_reprovacao(info['motivo_reprovacao'])

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
