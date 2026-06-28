"""
bot_under25.py
Motor para estrategia BACK Under 2.5 gols.
Configurado via Supabase (BOT_ID via variavel de ambiente UNDER25_BOT_ID).
Reusa betfair_client, telegram_client, supabase_integration e apostas.py.
"""
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

import betfair_client as bf
from telegram_client import enviar_mensagem
import supabase_integration as sb

# ============================================================
# CONFIGURACAO
# ============================================================
BOT_ID = os.getenv("UNDER25_BOT_ID", "4101d27c-2130-4517-b596-3969cf06f049")

FUSO_BRASILIA = timezone(timedelta(hours=-3))

# Valores padrao (sobrescritos pelo Supabase)
ENTRADA_MINUTOS_MAX = 10   # entrar somente ate X min de jogo
ODD_MINIMA          = 1.10
ODD_MAXIMA          = 1.90
LIQUIDEZ_MINIMA     = 150
SAIDA_TIPO          = "MINUTOS_OU_LUCRO"
SAIDA_MINUTOS       = 10
SAIDA_LUCRO_PCT     = 10
STAKE_FIXO          = 50.0
MODO_SIMULACAO      = True

INTERVALO_LOOP      = 60   # segundos entre cada varredura
INTERVALO_MONITOR   = 30   # segundos entre checks de saida
MAX_ERROS           = 5

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("under25")

# ============================================================
# CARREGAR CONFIGURACOES DO SUPABASE
# ============================================================
def carregar_config():
    """Carrega os filtros do bot do Supabase e sobrescreve as constantes."""
    global ENTRADA_MINUTOS_MAX, ODD_MINIMA, ODD_MAXIMA, LIQUIDEZ_MINIMA
    global SAIDA_TIPO, SAIDA_MINUTOS, SAIDA_LUCRO_PCT, STAKE_FIXO, MODO_SIMULACAO

    if not sb.SUPABASE_ATIVO:
        log.warning("Supabase inativo — usando configuracoes padrao")
        return

    try:
        rows = sb._client.table("filtros")\
            .select("chave,valor,valor_texto")\
            .eq("bot_id", BOT_ID)\
            .execute()

        f = {}
        for r in rows.data:
            f[r["chave"]] = r["valor_texto"] if r.get("valor_texto") is not None else r["valor"]

        ENTRADA_MINUTOS_MAX = float(f.get("ENTRADA_MINUTOS_MAX", ENTRADA_MINUTOS_MAX))
        ODD_MINIMA          = float(f.get("ODD_MINIMA", ODD_MINIMA))
        ODD_MAXIMA          = float(f.get("ODD_MAXIMA", ODD_MAXIMA))
        LIQUIDEZ_MINIMA     = float(f.get("LIQUIDEZ_MINIMA", LIQUIDEZ_MINIMA))
        SAIDA_TIPO          = str(f.get("SAIDA_TIPO", SAIDA_TIPO))
        SAIDA_MINUTOS       = float(f.get("SAIDA_MINUTOS", SAIDA_MINUTOS))
        SAIDA_LUCRO_PCT     = float(f.get("SAIDA_LUCRO_PCT", SAIDA_LUCRO_PCT))
        STAKE_FIXO          = float(f.get("STAKE_FIXO", STAKE_FIXO))

        log.info(
            f"Config carregada: entrada ate {ENTRADA_MINUTOS_MAX}min | "
            f"odd {ODD_MINIMA}-{ODD_MAXIMA} | stake R${STAKE_FIXO} | "
            f"saida: {SAIDA_TIPO}"
        )
    except Exception as e:
        log.warning(f"Erro ao carregar config do Supabase: {e}")


# ============================================================
# BUSCAR JOGOS DO DIA
# ============================================================
def buscar_jogos_do_dia() -> list:
    """Retorna todos os eventos de futebol do dia via Betfair."""
    try:
        agora_utc  = datetime.now(timezone.utc)
        fim_dia    = agora_utc.replace(hour=23, minute=59, second=59)
        rpc = __import__("json").dumps({
            "jsonrpc": "2.0",
            "method": "SportsAPING/v1.0/listEvents",
            "params": {
                "filter": {
                    "eventTypeIds": ["1"],
                    "marketStartTime": {
                        "from": agora_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "to":   fim_dia.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    },
                    "marketCountries": [],
                },
                "maxResults": "500",
            },
            "id": 1,
        })
        eventos = bf.chamar_api(rpc)
        return eventos or []
    except Exception as e:
        log.warning(f"Erro ao buscar jogos do dia: {e}")
        return []


# ============================================================
# ANALISAR JOGO
# ============================================================
def analisar_jogo(event_id: str, nome_jogo: str, minutos_de_jogo: float) -> dict | None:
    """
    Busca o mercado Over/Under 2.5 para o evento e verifica se atende os filtros.
    Retorna dict com dados do mercado se aprovado, None se reprovado.
    """
    if minutos_de_jogo > ENTRADA_MINUTOS_MAX:
        return None

    try:
        mercados = bf.listar_mercados(event_id, tipos=["OVER_UNDER_25"])
        if not mercados:
            log.info(f"  {nome_jogo}: sem mercado Over/Under 2.5 disponivel")
            return None

        market_id = mercados[0]["marketId"]
        books = bf.listar_odds([market_id], ["EX_BEST_OFFERS"])
        if not books:
            return None

        book     = books[0]
        runners  = book.get("runners", [])
        total_matched = book.get("totalMatched", 0)

        runner_under = None
        for r in runners:
            nome = r.get("runnerName", "")
            if "Under" in nome and "2.5" in nome:
                runner_under = r
                break

        if not runner_under:
            log.info(f"  {nome_jogo}: runner Under 2.5 nao encontrado")
            return None

        odd_back = bf.get_back(runner_under)
        if odd_back is None:
            log.info(f"  {nome_jogo}: sem odd BACK disponivel")
            return None

        # Filtros
        if odd_back < ODD_MINIMA:
            log.info(f"  {nome_jogo}: odd {odd_back} abaixo do minimo {ODD_MINIMA}")
            return None
        if odd_back > ODD_MAXIMA:
            log.info(f"  {nome_jogo}: odd {odd_back} acima do maximo {ODD_MAXIMA}")
            return None
        if total_matched < LIQUIDEZ_MINIMA:
            log.info(f"  {nome_jogo}: liquidez £{total_matched:.0f} insuficiente (min £{LIQUIDEZ_MINIMA})")
            return None

        log.info(
            f"  ✅ {nome_jogo}: APROVADO | "
            f"BACK Under 2.5 @ {odd_back} | "
            f"liquidez £{total_matched:.0f} | "
            f"{minutos_de_jogo:.0f}min de jogo"
        )
        return {
            "event_id":    event_id,
            "nome_jogo":   nome_jogo,
            "market_id":   market_id,
            "odd_back":    odd_back,
            "liquidez":    total_matched,
            "minutos":     minutos_de_jogo,
            "runner_id":   runner_under.get("selectionId"),
        }
    except Exception as e:
        log.warning(f"  {nome_jogo}: erro ao analisar — {e}")
        return None


# ============================================================
# COLOCAR APOSTA
# ============================================================
def colocar_aposta(dados: dict) -> dict:
    """Coloca o BACK Under 2.5. Em modo simulacao, apenas loga."""
    sim = MODO_SIMULACAO

    if sim:
        log.info(
            f"  [SIMULACAO] BACK Under 2.5 @ {dados['odd_back']} | "
            f"stake R${STAKE_FIXO} | {dados['nome_jogo']}"
        )
        enviar_mensagem(
            f"🎰 *APOSTA COLOCADA (SIMULACAO)*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚽ {dados['nome_jogo']}\n"
            f"📈 BACK Under 2.5 @ {dados['odd_back']}\n"
            f"💰 Stake: R${STAKE_FIXO:.2f}\n"
            f"⏱ {dados['minutos']:.0f}min de jogo"
        )
        return {
            "status":    "SUCCESS",
            "simulado":  True,
            "odd_back":  dados["odd_back"],
            "stake":     STAKE_FIXO,
            "betId":     "SIM",
        }

    # Aposta real via API Betfair
    try:
        import json as _json
        instrucoes = [{"selectionId": dados["runner_id"], "handicap": 0,
                       "side": "BACK", "orderType": "LIMIT",
                       "limitOrder": {"size": STAKE_FIXO, "price": dados["odd_back"],
                                      "persistenceType": "LAPSE"}}]
        rpc = _json.dumps({
            "jsonrpc": "2.0", "method": "SportsAPING/v1.0/placeOrders",
            "params": {"marketId": dados["market_id"], "instructions": instrucoes}, "id": 1,
        })
        resultado = bf.chamar_api(rpc)
        if resultado and resultado[0].get("status") == "SUCCESS":
            report = resultado[0]["instructionReports"][0]
            bet_id = report.get("betId", "?")
            odd_real = report.get("averagePriceMatched", dados["odd_back"])
            size_real = report.get("sizeMatched", STAKE_FIXO)
            enviar_mensagem(
                f"🎰 *APOSTA COLOCADA*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚽ {dados['nome_jogo']}\n"
                f"📈 BACK Under 2.5 @ {odd_real}\n"
                f"💰 Stake: R${size_real:.2f}\n"
                f"🆔 betId: `{bet_id}`\n"
                f"⏱ {dados['minutos']:.0f}min de jogo"
            )
            return {"status": "SUCCESS", "simulado": False,
                    "odd_back": odd_real, "stake": size_real, "betId": bet_id}
        else:
            motivo = resultado[0].get("errorCode", "?") if resultado else "sem resposta"
            log.warning(f"  Aposta falhou: {motivo}")
            enviar_mensagem(
                f"⚠️ *APOSTA FALHOU*\n"
                f"⚽ {dados['nome_jogo']}\n"
                f"❌ {motivo}"
            )
            return {"status": "FAIL", "motivo": motivo}
    except Exception as e:
        log.error(f"  Erro ao colocar aposta real: {e}")
        return {"status": "FAIL", "motivo": str(e)}


# ============================================================
# MONITOR DE SAIDA
# ============================================================
class MonitorSaidaUnder:
    """Monitora apostas abertas e decide quando sair."""

    def __init__(self):
        self._apostas: dict = {}

    def adicionar(self, dados_jogo: dict, res_aposta: dict, entrada_em: datetime):
        eid = dados_jogo["event_id"]
        self._apostas[eid] = {
            "nome_jogo":   dados_jogo["nome_jogo"],
            "market_id":   dados_jogo["market_id"],
            "runner_id":   dados_jogo["runner_id"],
            "odd_entrada": res_aposta["odd_back"],
            "stake":       res_aposta["stake"],
            "entrada_em":  entrada_em,
            "alerta_enviado": False,
        }
        log.info(f"  Monitor de saida iniciado: {dados_jogo['nome_jogo']}")

    def total(self) -> int:
        return len(self._apostas)

    def verificar_todos(self):
        agora = datetime.now(timezone.utc)
        encerrados = []

        for eid, dados in self._apostas.items():
            if dados["alerta_enviado"]:
                encerrados.append(eid)
                continue

            minutos_desde_entrada = (agora - dados["entrada_em"]).total_seconds() / 60

            # Regra 1: tempo maximo
            sair_por_tempo = (
                SAIDA_TIPO in ("MINUTOS", "MINUTOS_OU_LUCRO") and
                minutos_desde_entrada >= SAIDA_MINUTOS
            )

            # Regra 2: lucro percentual (checar odd atual)
            sair_por_lucro = False
            odd_atual = None
            if SAIDA_TIPO in ("LUCRO_PCT", "MINUTOS_OU_LUCRO"):
                try:
                    books = bf.listar_odds([dados["market_id"]], ["EX_BEST_OFFERS"])
                    if books:
                        runners = books[0].get("runners", [])
                        for r in runners:
                            if r.get("selectionId") == dados["runner_id"]:
                                odd_atual = bf.get_back(r)
                                break
                    if odd_atual and dados["odd_entrada"]:
                        lucro_pct = ((dados["odd_entrada"] - odd_atual) / (dados["odd_entrada"] - 1)) * 100
                        if lucro_pct >= SAIDA_LUCRO_PCT:
                            sair_por_lucro = True
                            log.info(
                                f"  {dados['nome_jogo']}: lucro {lucro_pct:.1f}% "
                                f"(odd entrou {dados['odd_entrada']} -> atual {odd_atual})"
                            )
                except Exception as e:
                    log.warning(f"  Erro ao checar odd de saida: {e}")

            if sair_por_tempo or sair_por_lucro:
                dados["alerta_enviado"] = True
                encerrados.append(eid)
                razao = []
                if sair_por_tempo:
                    razao.append(f"{minutos_desde_entrada:.0f}min desde a entrada")
                if sair_por_lucro and odd_atual:
                    lucro_pct_fmt = ((dados["odd_entrada"] - odd_atual) / (dados["odd_entrada"] - 1)) * 100
                    razao.append(f"+{lucro_pct_fmt:.1f}% de lucro (odd {odd_atual})")

                enviar_mensagem(
                    f"🚪 *SINAL DE SAIDA — Under 2.5*\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚽ {dados['nome_jogo']}\n"
                    f"📤 Motivo: {' | '.join(razao)}\n"
                    f"📈 Odd entrada: {dados['odd_entrada']}"
                    + (f" → atual: {odd_atual}" if odd_atual else "") + "\n"
                    f"_Considere fechar a posicao manualmente na Betfair._"
                )
                log.info(f"  🚪 Saida: {dados['nome_jogo']} | {' | '.join(razao)}")

        for eid in encerrados:
            self._apostas.pop(eid, None)


# ============================================================
# LOOP PRINCIPAL
# ============================================================
def rodar_bot():
    log.info("=" * 55)
    log.info("   BOT UNDER 2.5 — BACK Under 2.5 gols")
    log.info("=" * 55)

    if not bf.login():
        enviar_mensagem("❌ Bot Under 2.5: falha no login Betfair. Verifique as credenciais.")
        return

    carregar_config()

    apostas_abertas: set = set()
    monitor = MonitorSaidaUnder()
    erros_consecutivos = 0
    ultima_recarga_config = datetime.now(timezone.utc)
    ultimo_check_monitor = datetime.now(timezone.utc)

    enviar_mensagem(
        f"🤖 *Bot Under 2.5 iniciado!*\n"
        f"📈 Mercado: BACK Under 2.5 gols\n"
        f"⏱ Entrada: ate {ENTRADA_MINUTOS_MAX:.0f}min de jogo\n"
        f"📊 Odds: {ODD_MINIMA} - {ODD_MAXIMA}\n"
        f"💰 Stake: R${STAKE_FIXO:.2f}\n"
        f"🚪 Saida: {SAIDA_TIPO} "
        + (f"({SAIDA_MINUTOS:.0f}min" if "MINUTOS" in SAIDA_TIPO else "")
        + (f" / +{SAIDA_LUCRO_PCT:.0f}%" if "LUCRO" in SAIDA_TIPO else "")
        + (")" if "MINUTOS" in SAIDA_TIPO or "LUCRO" in SAIDA_TIPO else "") + "\n"
        f"{'🔵 SIMULACAO' if MODO_SIMULACAO else '🔴 REAL'}"
    )

    jogos_cache = []
    ultima_recarga_jogos = datetime.now(timezone.utc) - timedelta(hours=1)

    while True:
        try:
            agora = datetime.now(timezone.utc)

            # Recarregar config a cada 5 minutos
            if (agora - ultima_recarga_config).total_seconds() > 300:
                carregar_config()
                ultima_recarga_config = agora

            # Renovar login Betfair se necessario
            bf.renovar_token_se_necessario()

            # Recarregar lista de jogos so a cada 15 minutos
            if (agora - ultima_recarga_jogos).total_seconds() > 900:
                jogos_cache = buscar_jogos_do_dia()
                ultima_recarga_jogos = agora
                log.info(f'  Lista recarregada: {len(jogos_cache)} jogos no cache')

            jogos = jogos_cache

            for jogo in jogos:
                event = jogo.get("event", {})
                event_id    = str(event.get("id", ""))
                nome_jogo   = event.get("name", "Desconhecido")
                open_date   = event.get("openDate", "")

                if not event_id or not open_date:
                    continue

                # Calcular minutos de jogo
                try:
                    inicio_utc   = datetime.fromisoformat(open_date.replace("Z", "+00:00"))
                    minutos_jogo = (agora - inicio_utc).total_seconds() / 60
                except Exception:
                    continue

                # So analisa jogos ja iniciados e dentro da janela
                if minutos_jogo < 0 or minutos_jogo > ENTRADA_MINUTOS_MAX:
                    continue

                # Pula se ja tem aposta aberta nesse jogo
                if event_id in apostas_abertas:
                    continue

                log.info(f"🔍 {nome_jogo} ({minutos_jogo:.0f}min)")

                dados = analisar_jogo(event_id, nome_jogo, minutos_jogo)
                if not dados:
                    continue

                # Gravar analise no Supabase
                sb.registrar_analise_supabase(
                    {
                        "event_id":   event_id,
                        "nome_jogo":  nome_jogo,
                        "competition": event.get("countryCode", ""),
                        "horario":    inicio_utc.astimezone(FUSO_BRASILIA).strftime("%H:%M"),
                        "aprovado":   True,
                        "odd_favorito": dados["odd_back"],
                        "liquidez_disponivel": dados["liquidez"],
                        "ia_motivo":  f"BACK Under 2.5 @ {dados['odd_back']}",
                    },
                    aprovado=True,
                )

                # Colocar aposta
                res = colocar_aposta(dados)
                apostas_abertas.add(event_id)

                if res.get("status") == "SUCCESS":
                    monitor.adicionar(dados, res, agora)
                    sb.registrar_aposta_supabase(
                        {"event_id": event_id, "nome_jogo": nome_jogo,
                         "competition": "", "market_id_cs": dados["market_id"]},
                        {"placar_lay": "back_under25", "odd_lay": res["odd_back"],
                         "stake": res["stake"], "betId": res.get("betId", ""),
                         "simulado": res.get("simulado", True)}
                    )

            # Monitor de saida
            if (agora - ultimo_check_monitor).total_seconds() >= INTERVALO_MONITOR:
                if monitor.total() > 0:
                    monitor.verificar_todos()
                ultimo_check_monitor = agora

            erros_consecutivos = 0
            time.sleep(INTERVALO_LOOP)

        except KeyboardInterrupt:
            log.info("Bot encerrado manualmente.")
            break
        except Exception as e:
            erros_consecutivos += 1
            log.error(f"Erro no loop principal ({erros_consecutivos}/{MAX_ERROS}): {e}")
            if erros_consecutivos >= MAX_ERROS:
                enviar_mensagem(f"🚨 Bot Under 2.5 parou: {MAX_ERROS} erros consecutivos.\nUltimo: {e}")
                break
            time.sleep(30)


if __name__ == "__main__":
    rodar_bot()
