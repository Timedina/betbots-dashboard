from dotenv import load_dotenv
import os
import betfairlightweight
from betfairlightweight.filters import market_filter, time_range, price_projection
from datetime import datetime, timezone

load_dotenv()

EMAIL = os.getenv('EMAIL')
SENHA = os.getenv('SENHA')
APP_KEY = os.getenv('APP_KEY')

cliente = betfairlightweight.APIClient(
    username=EMAIL,
    password=SENHA,
    app_key=APP_KEY,
    certs=r'C:\Users\TIAGO\Documents\ProjetoBetfair',
    locale='brazil'
)

try:
    cliente.login()
    print("Login OK!")
except Exception as e:
    print("Erro no login:", str(e))
    exit()


def listar_esportes():
    print("\nESPORTES DISPONIVEIS\n" + "-" * 40)
    esportes = cliente.betting.list_event_types()
    esportes = sorted(esportes, key=lambda x: x.market_count, reverse=True)
    for e in esportes:
        print(f"ID: {e.event_type.id:<12} {e.event_type.name:<25} ({e.market_count} mercados)")
    return esportes


def listar_jogos():
    print("\nFUTEBOL DE HOJE\n" + "-" * 60)
    agora = datetime.now(timezone.utc)
    fim = agora.replace(hour=23, minute=59, second=59)

    filtro = market_filter(
        event_type_ids=['1'],
        market_start_time=time_range(
            from_=agora.strftime("%Y-%m-%dT%H:%M:%SZ"),
            to=fim.strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    )

    jogos = cliente.betting.list_events(filter=filtro)
    jogos = sorted(jogos, key=lambda x: x.event.open_date)

    if not jogos:
        print("Nenhum jogo encontrado para hoje.")
    for j in jogos:
        nome = j.event.name
        pais = j.event.country_code or '??'
        inicio = str(j.event.open_date)[:16]
        eid = j.event.id
        mercados = j.market_count
        print(f"ID {eid} | {pais} | {inicio} | {nome} ({mercados} mercados)")
    return jogos


def ver_odds(event_id):
    print(f"\nODDS - Evento {event_id}\n" + "-" * 50)

    catalogo = cliente.betting.list_market_