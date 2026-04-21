import requests
import urllib.request
import urllib.error
import json
import os
import base64
import tempfile
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(override=True)

EMAIL   = os.getenv("EMAIL")
SENHA   = os.getenv("SENHA")
APP_KEY = os.getenv("APP_KEY")

SESSION_TOKEN = None
ULTIMO_LOGIN  = None

_cert_path: str | None = None
_key_path:  str | None = None

def _preparar_certificado() -> tuple[str, str]:
    global _cert_path, _key_path
    if _cert_path and _key_path:
        return _cert_path, _key_path
    cert_env = os.getenv("BETFAIR_CERT")
    key_env  = os.getenv("BETFAIR_KEY")
    if cert_env and key_env:
        tmp_dir = tempfile.gettempdir()
        _cert_path = os.path.join(tmp_dir, "betfair.crt")
        _key_path  = os.path.join(tmp_dir, "betfair.key")
        with open(_cert_path, "wb") as f:
            f.write(base64.b64decode(cert_env))
        with open(_key_path, "wb") as f:
            f.write(base64.b64decode(key_env))
        print("[Betfair] Certificado carregado via variáveis de ambiente.")
    else:
        _cert_path = "client-2048_1.crt"
        _key_path  = "client-2048.KEY"
        print("[Betfair] Certificado carregado via arquivos locais.")
    return _cert_path, _key_path

def login() -> bool:
    global SESSION_TOKEN, ULTIMO_LOGIN
    cert_path, key_path = _preparar_certificado()
    try:
        resp = requests.post(
            "https://identitysso-cert.betfair.bet.br/api/certlogin",
            data=f"username={EMAIL}&password={SENHA}",
            cert=(cert_path, key_path),
            headers={"X-Application": APP_KEY, "Content-Type": "application/x-www-form-urlencoded"},
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("loginStatus") == "SUCCESS":
            SESSION_TOKEN = data["sessionToken"]
            ULTIMO_LOGIN  = datetime.now(timezone.utc)
            print("[Betfair] Login OK!")
            return True
        print(f"[Betfair] Falha no login: {resp.text}")
    except Exception as e:
        print(f"[Betfair] Erro no login: {e}")
    return False

def renovar_token_se_necessario() -> bool:
    if ULTIMO_LOGIN is None:
        return login()
    horas = (datetime.now(timezone.utc) - ULTIMO_LOGIN).total_seconds() / 3600
    if horas >= 6:
        print("[Betfair] Renovando token...")
        return login()
    return True

def chamar_api(rpc: str) -> list:
    renovar_token_se_necessario()
    url = "https://api.betfair.bet.br/exchange/betting/json-rpc/v1"
    headers = {"X-Application": APP_KEY, "X-Authentication": SESSION_TOKEN, "content-type": "application/json"}
    try:
        req = urllib.request.Request(url, rpc.encode("utf-8"), headers)
        raw = urllib.request.urlopen(req).read().decode("utf-8")
        return json.loads(raw).get("result", [])
    except urllib.error.HTTPError as e:
        print(f"[Betfair] HTTPError: {e.code} {e.read().decode()}")
    except Exception as e:
        print(f"[Betfair] Erro: {e}")
    return []

def listar_mercados(event_id: str, tipos: list = None) -> list:
    filtro = {"eventIds": [event_id]}
    if tipos:
        filtro["marketTypeCodes"] = tipos
    rpc = json.dumps({"jsonrpc": "2.0", "method": "SportsAPING/v1.0/listMarketCatalogue",
        "params": {"filter": filtro, "maxResults": "200",
            "marketProjection": ["COMPETITION","EVENT","EVENT_TYPE","RUNNER_DESCRIPTION","MARKET_START_TIME"]}, "id": 1})
    return chamar_api(rpc)

def listar_odds(market_ids: list, dados: list = None) -> list:
    if dados is None:
        dados = ["EX_BEST_OFFERS"]
    rpc = json.dumps({"jsonrpc": "2.0", "method": "SportsAPING/v1.0/listMarketBook",
        "params": {"marketIds": market_ids, "priceProjection": {"priceData": dados, "virtualise": "true"}}, "id": 1})
    return chamar_api(rpc)

def get_back(runner: dict, posicao: int = 0) -> float | None:
    offers = runner.get("ex", {}).get("availableToBack", [])
    return offers[posicao]["price"] if len(offers) > posicao else None

def get_lay(runner: dict, posicao: int = 0) -> float | None:
    offers = runner.get("ex", {}).get("availableToLay", [])
    return offers[posicao]["price"] if len(offers) > posicao else None
