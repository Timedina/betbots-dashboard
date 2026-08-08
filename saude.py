import json, os
from datetime import datetime, timezone

ARQUIVO_SAUDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_bot", "saude.json")

def registrar(integracao, ok, detalhe=""):
    try:
        os.makedirs(os.path.dirname(ARQUIVO_SAUDE), exist_ok=True)
        dados = {}
        if os.path.exists(ARQUIVO_SAUDE):
            with open(ARQUIVO_SAUDE) as f:
                dados = json.load(f)
        agora = datetime.now(timezone.utc).isoformat()
        item = dados.get(integracao, {"ok_streak": 0, "fail_streak": 0})
        if ok:
            item["ultimo_ok"] = agora
            item["ok_streak"] = item.get("ok_streak", 0) + 1
            item["fail_streak"] = 0
        else:
            item["ultimo_erro"] = agora
            item["ultimo_erro_detalhe"] = str(detalhe)[:200]
            item["fail_streak"] = item.get("fail_streak", 0) + 1
            item["ok_streak"] = 0
        dados[integracao] = item
        tmp = ARQUIVO_SAUDE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(dados, f)
        os.replace(tmp, ARQUIVO_SAUDE)
    except Exception:
        pass
