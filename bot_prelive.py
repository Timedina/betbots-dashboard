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

LIQUIDEZ_MINIMA_CS_DISPONIVEL = 150   # £ disponíveis para lay nos runners 1-0 e 0-1 (soma)
LIQUIDEZ_MINIMA_CS_TOTAL      = 500   # £ totalMatched do mercado CS (usado como info)
LIQUIDEZ_MINIMA_GOALS         = 1000  # reservado para uso futuro

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

# Reconexao automatica
MAX_ERROS_CONSECUTIVOS = 5
ESPERA_APOS_ERRO       = 30

# Tipos de mercado permitidos
MARKET_TYPES_FILTRO = ['MATCH_ODDS', 'CORRECT_SCORE', 'OVER_UNDER_15', 'BOTH_TEAMS_TO_SCORE']

# Melhoria A: Deteccao de movimento de odds
MOVIMENTO_SUBIDA_ALERTA = 0.20   # +20% na odd -> alerta "entrada melhorou"
MOVIMENTO_QUEDA_ALERTA  = 0.15   # -15% na odd -> alerta "mercado indo contra"
INTERVALO_MONITOR_ODDS  = 90     # segundos entre verificacoes pos-aprovacao

# Melhoria B: Monitoramento de saida
QUEDA_SAIDA_PERCENTUAL   = 0.20  # odd cai 20%+ -> alerta de saida
MINUTOS_MONITOR_POS_KICK = 15    # quantos minutos apos o kickoff monitorar

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
# ARQUIVO DE PERSISTENCIA -- aprovados
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
        'nome_jogo':           info['nome_jogo'],
        'competition':         info.get('competition', ''),
        'horario':             info.get('horario', '--:--'),
        'odd_10':              info.get('odd_10'),
        'odd_01':              info.get('odd_01'),
        'odd_over15':          info.get('odd_over15'),
        'odd_btts':            info.get('odd_btts'),
        'odd_favorito':        info.get('odd_favorito'),
        'favorito':            info.get('favorito', ''),
        'liquidez_disponivel': info.get('liquidez_disponivel', 0),
        'liquidez_total':      info.get('liquidez_total', 0),
        'market_id_cs':        info.get('market_id_cs', ''),
        'salvo_em':            datetime.now(FUSO_BRASILIA).strftime('%H:%M:%S'),
    }
    with open(arquivo_do_dia(), 'w', encoding='utf-8') as f:
        json.dump(aprovados, f, ensure_ascii=False, indent=2)


# ============================================================
# MELHORIA C: LOG PERSISTENTE DE REPROVACOES
# ============================================================

def arquivo_reprovados_do_dia() -> str:
    data = datetime.now(FUSO_BRASILIA).strftime('%Y-%m-%d')
    return os.path.join(PASTA_DADOS, f'reprovados_{data}.json')


def carregar_reprovados_do_dia() -> dict:
    path = arquivo_reprovados_do_dia()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log.warning(f'Erro ao carregar reprovados: {e}')
    return {}


def registrar_reprovacao_persistente(event_id: str, nome_jogo: str, competition: str,
                                      horario: str, motivos: list):
    """
    Acumula cada tentativa de reprovacao no JSON do dia.
    Estrutura: { event_id: { nome_jogo, competition, horario, tentativas: [{hora, motivos}] } }
    """
    reprovados = carregar_reprovados_do_dia()
    agora_str  = datetime.now(FUSO_BRASILIA).strftime('%H:%M:%S')

    if event_id not in reprovados:
        reprovados[event_id] = {
            'nome_jogo':   nome_jogo,
            'competition': competition,
            'horario':     horario,
            'tentativas':  [],
        }

    reprovados[event_id]['tentativas'].append({
        'hora':    agora_str,
        'motivos': motivos,
    })

    try:
        with open(arquivo_reprovados_do_dia(), 'w', encoding='utf-8') as f:
            json.dump(reprovados, f, ensure_ascii=False, indent=2)
        log.info(f'  📝 Reprovacao salva: {nome_jogo} | {motivos}')
    except Exception as e:
        log.warning(f'Erro ao salvar reprovado: {e}')
        log.warning(f'  Caminho: {arquivo_reprovados_do_dia()}')


def resumo_reprovados_telegram():
    """Envia um resumo analitico dos motivos de reprovacao do dia."""
    reprovados = carregar_reprovados_do_dia()
    data_hoje  = datetime.now(FUSO_BRASILIA).strftime('%d/%m/%Y')

    if not reprovados:
        enviar_mensagem(
            f'📋 *Reprovações — {data_hoje}*\n'
            f'_Nenhuma reprovação registrada hoje._'
        )
        return

    contagem: dict = {}
    total_tentativas = 0
    for dados in reprovados.values():
        for tent in dados['tentativas']:
            total_tentativas += 1
            for motivo in tent['motivos']:
                chave = motivo.split(':')[0].strip()
                contagem[chave] = contagem.get(chave, 0) + 1

    top = sorted(contagem.items(), key=lambda x: x[1], reverse=True)[:8]
    linhas = [
        f'📋 *Reprovações do Dia — {data_hoje}*',
        f'━━━━━━━━━━━━━━━━━━━━',
        f'🔍 Jogos únicos reprovados: {len(reprovados)}',
        f'🔁 Total de tentativas: {total_tentativas}',
        f'━━━━━━━━━━━━━━━━━━━━',
        f'*Top motivos:*',
    ]
    for motivo, n in top:
        barra = '\u2593' * min(10, n) + '\u2591' * max(0, 10 - n)
        linhas.append(f'`{barra}` {motivo}: *{n}x*')

    linhas += [
        f'━━━━━━━━━━━━━━━━━━━━',
        f'_Arquivo: reprovados_{datetime.now(FUSO_BRASILIA).strftime("%Y-%m-%d")}.json_',
    ]
    enviar_mensagem('\n'.join(linhas))


# ============================================================
# ESTATISTICAS DA SESSAO
# ============================================================

class Estatisticas:
    def __init__(self):
        self.jogos_analisados    = 0
        self.jogos_aprovados     = 0
        self.jogos_pulados_cache = 0
        self.chamadas_api        = 0
        self.alertas_movimento   = 0
        self.alertas_saida       = 0
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
            f'💹 Alertas movimento: {self.alertas_movimento}\n'
            f'🚪 Alertas saída: {self.alertas_saida}\n'
            f'📋 Top motivos: {motivos_str}'
        )

stats = Estatisticas()


# ============================================================
# CACHE DE JOGOS DESCARTAVEIS
# ============================================================

class CacheEventos:
    def __init__(self):
        self._pulados: dict = {}

    def deve_pular(self, event_id: str) -> bool:
        return event_id in self._pulados

    def registrar(self, event_id: str, motivo: str):
        self._pulados[event_id] = motivo
        log.debug(f'  Cache: {event_id} bloqueado — {motivo}')

    def total(self) -> int:
        return len(self._pulados)

cache_eventos = CacheEventos()


# ============================================================
# MELHORIA A: MONITOR DE MOVIMENTO DE ODDS
# ============================================================

class MonitorOdds:
    """
    Apos um jogo ser aprovado, rastreia as odds de 1-0 e 0-1.
    - Subida >= MOVIMENTO_SUBIDA_ALERTA: avisa que entrada melhorou
    - Queda >= MOVIMENTO_QUEDA_ALERTA: avisa que mercado esta indo contra
    """
    def __init__(self):
        self._monitorados: dict = {}

    def adicionar(self, info: dict):
        self._monitorados[info['event_id']] = {
            'nome_jogo':             info['nome_jogo'],
            'odd_10_ref':            info['odd_10'],
            'odd_01_ref':            info['odd_01'],
            'market_id_cs':          info['market_id_cs'],
            'open_date':             info.get('open_date', ''),
            'ultimo_check':          datetime.now(timezone.utc),
            'alerta_subida_enviado': False,
            'alerta_queda_enviado':  False,
        }
        log.info(f'  📡 Monitor de odds iniciado: {info["nome_jogo"]}')

    def remover(self, event_id: str):
        self._monitorados.pop(event_id, None)

    def total(self) -> int:
        return len(self._monitorados)

    def verificar_todos(self):
        agora      = datetime.now(timezone.utc)
        encerrados = []

        for event_id, dados in self._monitorados.items():
            try:
                inicio_utc = datetime.fromisoformat(dados['open_date'].replace('Z', '+00:00'))
                limite     = inicio_utc + timedelta(minutes=MINUTOS_MONITOR_POS_KICK)
                if agora > limite:
                    encerrados.append(event_id)
                    log.info(f'  📡 Monitor encerrado (tempo): {dados["nome_jogo"]}')
                    continue
            except:
                pass

            if (agora - dados['ultimo_check']).total_seconds() < INTERVALO_MONITOR_ODDS:
                continue

            try:
                stats.registrar_chamada_api()
                books = bf.listar_odds([dados['market_id_cs']], ['EX_BEST_OFFERS'])
                if not books:
                    continue

                runners = books[0].get('runners', [])
                dados['ultimo_check'] = agora

                def odd_lay_por_nome(nome_alvo):
                    for r in runners:
                        if r.get('runnerName', '') == nome_alvo:
                            return bf.get_lay(r)
                    return None

                odd_10_atual = odd_lay_por_nome('1 - 0')
                odd_01_atual = odd_lay_por_nome('0 - 1')
                if odd_10_atual is None or odd_01_atual is None:
                    continue

                ref_10 = dados['odd_10_ref']
                ref_01 = dados['odd_01_ref']

                # Subida: entrada melhorou
                if not dados['alerta_subida_enviado']:
                    subiu_10 = (odd_10_atual - ref_10) / ref_10 >= MOVIMENTO_SUBIDA_ALERTA
                    subiu_01 = (odd_01_atual - ref_01) / ref_01 >= MOVIMENTO_SUBIDA_ALERTA
                    if subiu_10 or subiu_01:
                        dados['alerta_subida_enviado'] = True
                        stats.alertas_movimento += 1
                        partes = []
                        if subiu_10:
                            partes.append(f'1-0: {ref_10:.2f} -> *{odd_10_atual:.2f}* '
                                          f'(+{(odd_10_atual/ref_10 - 1)*100:.0f}%)')
                        if subiu_01:
                            partes.append(f'0-1: {ref_01:.2f} -> *{odd_01_atual:.2f}* '
                                          f'(+{(odd_01_atual/ref_01 - 1)*100:.0f}%)')
                        enviar_mensagem(
                            f'💹 *ODDS EM MOVIMENTO — entrada melhorou*\n'
                            f'━━━━━━━━━━━━━━━━━━━━\n'
                            f'⚽ {dados["nome_jogo"]}\n'
                            f'📈 ' + '\n'.join(partes) + '\n'
                            f'✅ _Odd mais alta = lay mais lucrativo_'
                        )
                        log.info(f'  💹 Alerta subida: {dados["nome_jogo"]}')

                # Queda: mercado indo contra
                if not dados['alerta_queda_enviado']:
                    caiu_10 = (ref_10 - odd_10_atual) / ref_10 >= MOVIMENTO_QUEDA_ALERTA
                    caiu_01 = (ref_01 - odd_01_atual) / ref_01 >= MOVIMENTO_QUEDA_ALERTA
                    if caiu_10 or caiu_01:
                        dados['alerta_queda_enviado'] = True
                        stats.alertas_movimento += 1
                        partes = []
                        if caiu_10:
                            partes.append(f'1-0: {ref_10:.2f} -> *{odd_10_atual:.2f}* '
                                          f'(-{(1 - odd_10_atual/ref_10)*100:.0f}%)')
                        if caiu_01:
                            partes.append(f'0-1: {ref_01:.2f} -> *{odd_01_atual:.2f}* '
                                          f'(-{(1 - odd_01_atual/ref_01)*100:.0f}%)')
                        enviar_mensagem(
                            f'⚠️ *ODDS EM QUEDA — mercado indo contra*\n'
                            f'━━━━━━━━━━━━━━━━━━━━\n'
                            f'⚽ {dados["nome_jogo"]}\n'
                            f'📉 ' + '\n'.join(partes) + '\n'
                            f'🔎 _Acompanhe. Se continuar caindo, considere saída._'
                        )
                        log.info(f'  ⚠️ Alerta queda: {dados["nome_jogo"]}')

            except Exception as e:
                log.warning(f'  Monitor odds erro ({dados["nome_jogo"]}): {e}')

        for eid in encerrados:
            self.remover(eid)

monitor_odds = MonitorOdds()


# ============================================================
# MELHORIA B: MONITOR DE SAIDA
# ============================================================

class MonitorSaida:
    """
    Monitora jogos aprovados durante os primeiros minutos de jogo.
    Gatilho 1: queda de odds >= QUEDA_SAIDA_PERCENTUAL
    Gatilho 2: volume de totalMatched dobra (indicativo de gol)
    """
    def __init__(self):
        self._monitorados: dict = {}

    def adicionar(self, info: dict):
        self._monitorados[info['event_id']] = {
            'nome_jogo':         info['nome_jogo'],
            'odd_10_ref':        info['odd_10'],
            'odd_01_ref':        info['odd_01'],
            'total_matched_ref': info.get('liquidez_total', 0),
            'market_id_cs':      info['market_id_cs'],
            'open_date':         info.get('open_date', ''),
            'ultimo_check':      datetime.now(timezone.utc),
            'alerta_enviado':    False,
        }
        log.info(f'  🚪 Monitor de saída iniciado: {info["nome_jogo"]}')

    def remover(self, event_id: str):
        self._monitorados.pop(event_id, None)

    def total(self) -> int:
        return len(self._monitorados)

    def verificar_todos(self):
        agora      = datetime.now(timezone.utc)
        encerrados = []

        for event_id, dados in self._monitorados.items():
            if dados['alerta_enviado']:
                encerrados.append(event_id)
                continue

            try:
                inicio_utc   = datetime.fromisoformat(dados['open_date'].replace('Z', '+00:00'))
                minutos_jogo = (agora - inicio_utc).total_seconds() / 60
                if minutos_jogo > MINUTOS_MONITOR_POS_KICK:
                    encerrados.append(event_id)
                    log.info(f'  🚪 Monitor saída encerrado (tempo): {dados["nome_jogo"]}')
                    continue
                if minutos_jogo < 0:
                    continue
            except:
                pass

            if (agora - dados['ultimo_check']).total_seconds() < INTERVALO_MONITOR_ODDS:
                continue

            try:
                stats.registrar_chamada_api()
                books = bf.listar_odds([dados['market_id_cs']], ['EX_BEST_OFFERS'])
                if not books:
                    continue

                book          = books[0]
                runners       = book.get('runners', [])
                total_matched = book.get('totalMatched', 0)
                dados['ultimo_check'] = agora

                def odd_lay_por_nome(nome_alvo):
                    for r in runners:
                        if r.get('runnerName', '') == nome_alvo:
                            return bf.get_lay(r)
                    return None

                odd_10_atual = odd_lay_por_nome('1 - 0')
                odd_01_atual = odd_lay_por_nome('0 - 1')
                if odd_10_atual is None or odd_01_atual is None:
                    continue

                ref_10  = dados['odd_10_ref']
                ref_01  = dados['odd_01_ref']
                ref_vol = dados['total_matched_ref']

                queda_10    = (ref_10 - odd_10_atual) / ref_10 >= QUEDA_SAIDA_PERCENTUAL
                queda_01    = (ref_01 - odd_01_atual) / ref_01 >= QUEDA_SAIDA_PERCENTUAL
                gol_provavel = ref_vol > 0 and total_matched >= ref_vol * 2

                if queda_10 or queda_01 or gol_provavel:
                    dados['alerta_enviado'] = True
                    stats.alertas_saida += 1

                    try:
                        min_jogo = int((agora - inicio_utc).total_seconds() / 60)
                    except:
                        min_jogo = '?'

                    razoes = []
                    if queda_10:
                        razoes.append(f'LAY 1-0 caiu: {ref_10:.2f} -> *{odd_10_atual:.2f}* '
                                      f'(-{(1 - odd_10_atual/ref_10)*100:.0f}%)')
                    if queda_01:
                        razoes.append(f'LAY 0-1 caiu: {ref_01:.2f} -> *{odd_01_atual:.2f}* '
                                      f'(-{(1 - odd_01_atual/ref_01)*100:.0f}%)')
                    if gol_provavel:
                        razoes.append(f'Volume CS explodiu: £{ref_vol:,.0f} -> £{total_matched:,.0f} '
                                      f'(+{(total_matched/ref_vol - 1)*100:.0f}%)')

                    enviar_mensagem(
                        f'🚨 *ALERTA DE SAÍDA*\n'
                        f'━━━━━━━━━━━━━━━━━━━━\n'
                        f'⚽ {dados["nome_jogo"]}\n'
                        f'🕐 ~{min_jogo} min de jogo\n'
                        f'━━━━━━━━━━━━━━━━━━━━\n'
                        f'🔴 ' + '\n'.join(razoes) + '\n'
                        f'━━━━━━━━━━━━━━━━━━━━\n'
                        f'⚠️ _Considere fechar o lay agora._'
                    )
                    log.info(f'  🚨 Alerta saída: {dados["nome_jogo"]} — {" | ".join(razoes)}')
                    encerrados.append(event_id)

            except Exception as e:
                log.warning(f'  Monitor saída erro ({dados["nome_jogo"]}): {e}')

        for eid in encerrados:
            self.remover(eid)

monitor_saida = MonitorSaida()


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


def calcular_liquidez_disponivel_lay(runners_book: list, runners_map: dict, nomes: list) -> float:
    total = 0.0
    for runner in runners_book:
        if runners_map.get(runner['selectionId'], '') in nomes:
            for ordem in runner.get('ex', {}).get('availableToLay', []):
                total += ordem.get('size', 0)
    return total


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


def listar_mercados_filtrado(event_id: str) -> list:
    stats.registrar_chamada_api()
    return bf.listar_mercados(event_id, market_types=MARKET_TYPES_FILTRO)


def verificar_favorito_rapido(event_id: str, mercados: list) -> tuple:
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


def buscar_mercados_restantes_batch(cs_mercado, over15_mercado, btts_mercado) -> dict:
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
# ANALISE PRINCIPAL
# ============================================================

def analisar_jogo(event_id: str, nome_jogo: str, minutos: float) -> dict:
    resultado = {
        'aprovado': False,
        'motivo_reprovacao': [],
        'nome_jogo': nome_jogo,
        'minutos': int(minutos),
        'event_id': event_id,
        'competition': '',
        'horario': '--:--',
    }

    if cache_eventos.deve_pular(event_id):
        resultado['motivo_reprovacao'].append('Cache: reprovado permanente')
        stats.registrar_pulado()
        return resultado

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
        cache_eventos.registrar(event_id, 'Sem Correct Score')
        return resultado
    if not mo_mercado:
        resultado['motivo_reprovacao'].append('Sem Match Odds')
        cache_eventos.registrar(event_id, 'Sem Match Odds')
        return resultado

    competition = cs_mercado.get('competition', {}).get('name', '')
    resultado['competition'] = competition

    if LIGAS_PERMITIDAS:
        if not any(liga.lower() in competition.lower() for liga in LIGAS_PERMITIDAS):
            motivo = f'Liga nao permitida: {competition}'
            resultado['motivo_reprovacao'].append(motivo)
            cache_eventos.registrar(event_id, motivo)
            return resultado

    fav_ok, odd_favorito, nome_favorito, book_mo = verificar_favorito_rapido(event_id, mercados)
    if not fav_ok:
        resultado['motivo_reprovacao'].append(f'Favorito fora faixa: {odd_favorito}')
        return resultado

    resultado['favorito']     = nome_favorito
    resultado['odd_favorito'] = odd_favorito

    books_restantes = buscar_mercados_restantes_batch(cs_mercado, over15_mercado, btts_mercado)
    if not books_restantes:
        resultado['motivo_reprovacao'].append('Sem dados de odds (batch)')
        return resultado

    book_cs = books_restantes.get(cs_mercado['marketId'])
    if not book_cs:
        resultado['motivo_reprovacao'].append('Sem dados CS')
        return resultado

    runners_cs_map  = {r['selectionId']: r['runnerName'] for r in cs_mercado.get('runners', [])}
    runners_cs_book = book_cs.get('runners', [])

    liquidez_disponivel = calcular_liquidez_disponivel_lay(
        runners_cs_book, runners_cs_map, ['1 - 0', '0 - 1']
    )
    liquidez_total = book_cs.get('totalMatched', 0)

    if liquidez_disponivel < LIQUIDEZ_MINIMA_CS_DISPONIVEL:
        resultado['motivo_reprovacao'].append(
            f'Liquidez CS insuficiente: £{liquidez_disponivel:.0f} disp. '
            f'(historico £{liquidez_total:.0f}, min £{LIQUIDEZ_MINIMA_CS_DISPONIVEL})'
        )
        return resultado

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

    resultado['odd_10']              = odd_10
    resultado['odd_01']              = odd_01
    resultado['liquidez_disponivel'] = liquidez_disponivel
    resultado['liquidez_total']      = liquidez_total
    resultado['market_id_cs']        = cs_mercado['marketId']

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
        f'💧 Liquidez disp: £{info.get("liquidez_disponivel", 0):,.0f} '
        f'| Total: £{info.get("liquidez_total", 0):,.0f}\n'
        f'━━━━━━━━━━━━━━━━━━━━\n'
        f'🆔 `{info.get("market_id_cs", "")}`\n'
        f'📡 _Monitorando odds e saída automaticamente_'
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
            f'💧 CS disp: £{info.get("liquidez_disponivel", 0):,.0f} | total: £{info.get("liquidez_total", 0):,.0f}',
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
        dados     = self.jogos[event_id]
        agora     = datetime.now(timezone.utc)
        minutos   = tempo_para_inicio(dados['open_date'])
        intervalo = INTERVALO_LONGE if minutos > LIMIAR_JANELA_ENTRADA else INTERVALO_VERIFICACAO

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
            log.info(f'    -> Proxima: {proxima.astimezone(FUSO_BRASILIA).strftime("%H:%M")} '
                     f'(intervalo {intervalo} min — {int(minutos)} min p/ inicio)')

    def marcar_aprovado(self, event_id: str):
        self.jogos[event_id]['estado'] = 'aprovado'

    def _descartar(self, event_id: str, motivo: str):
        self.jogos[event_id]['estado'] = 'descartado'
        log.info(f'    Descartado: {self.jogos[event_id]["nome_jogo"]} — {motivo}')

    def limpar_encerrados(self):
        antes = len(self.jogos)
        self.jogos = {eid: d for eid, d in self.jogos.items() if d['estado'] == 'aguardando'}
        removidos = antes - len(self.jogos)
        if removidos:
            log.info(f'  Agendador: {removidos} jogos removidos da fila')

    def status(self) -> str:
        aguardando = sum(1 for d in self.jogos.values() if d['estado'] == 'aguardando')
        return (f'Fila: {aguardando} aguardando | '
                f'Cache: {cache_eventos.total()} bloqueados | '
                f'Monitor odds: {monitor_odds.total()} | '
                f'Monitor saida: {monitor_saida.total()}')


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
        f'🔄 Intervalo dinâmico: {INTERVALO_LONGE}min (longe) / {INTERVALO_VERIFICACAO}min (janela)\n'
        f'📡 Monitor de odds e saída: *ativo*'
    )
    gerar_resumo_diario()

    ultima_recarga        = datetime.now(timezone.utc)
    ultimo_resumo_noturno = None   # controla envio do resumo das 23h

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

            # Resumo noturno automático às 23h (horário de Brasília)
            agora_br   = datetime.now(FUSO_BRASILIA)
            data_hoje  = agora_br.strftime('%Y-%m-%d')
            hora_atual = agora_br.hour
            if hora_atual >= 23 and ultimo_resumo_noturno != data_hoje:
                ultimo_resumo_noturno = data_hoje
                log.info('  📋 Enviando resumo noturno de reprovações...')
                resumo_reprovados_telegram()

            # Melhoria A + B: rodar monitores a cada ciclo
            if monitor_odds.total() > 0:
                monitor_odds.verificar_todos()
            if monitor_saida.total() > 0:
                monitor_saida.verificar_todos()

            para_verificar = agendador.jogos_para_verificar_agora()

            if not para_verificar:
                proximas = [d['proxima_verificacao'] for d in agendador.jogos.values()
                            if d['estado'] == 'aguardando']
                if proximas:
                    prox   = min(proximas)
                    espera = max(10, min(60, (prox - datetime.now(timezone.utc)).total_seconds()))
                    log.info(f'  Proxima: {prox.astimezone(FUSO_BRASILIA).strftime("%H:%M")} — aguardando {int(espera)}s')
                    time.sleep(espera)
                else:
                    log.info('  Sem jogos na fila. Aguardando 60s...')
                    time.sleep(60)
                continue

            for event_id, dados in para_verificar:
                nome_jogo = dados['nome_jogo']
                minutos   = tempo_para_inicio(dados['open_date'])
                horario   = utc_para_brasilia(dados['open_date'])

                log.info(f'  🔍 {nome_jogo} ({horario}) | {int(minutos):+d} min')
                info = analisar_jogo(event_id, nome_jogo, minutos)

                if info['aprovado']:
                    info['horario']   = horario
                    info['open_date'] = dados['open_date']

                    log.info(f'  ✅ APROVADO! 1-0@{info["odd_10"]:.2f} | '
                             f'0-1@{info["odd_01"]:.2f} | Fav@{info["odd_favorito"]:.2f}')

                    enviar_mensagem(formatar_alerta(info))
                    salvar_aprovado(info)
                    agendador.marcar_aprovado(event_id)
                    stats.registrar_aprovacao()

                    # Melhoria A: monitor de movimento de odds
                    monitor_odds.adicionar(info)
                    # Melhoria B: monitor de saida
                    monitor_saida.adicionar(info)

                else:
                    motivos = info['motivo_reprovacao']
                    log.info(f'  ⛔ {" | ".join(motivos)}')

                    if not any('Cache' in m for m in motivos):
                        # Melhoria C: persistir reprovacao no JSON do dia
                        registrar_reprovacao_persistente(
                            event_id=event_id,
                            nome_jogo=nome_jogo,
                            competition=info.get('competition', ''),
                            horario=horario,
                            motivos=motivos,
                        )
                        agendador.avancar_verificacao(event_id)

                    stats.registrar_reprovacao(motivos)

            agendador.limpar_encerrados()
            stats.registrar_sucesso()

        except KeyboardInterrupt:
            log.info('Bot encerrado pelo usuário.')
            resumo_reprovados_telegram()
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
