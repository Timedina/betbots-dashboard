#!/bin/bash
# Valida se todas as env vars esperadas pelos bots existem no .env
# Uso: ./validar_env.sh   (roda antes de qualquer restart de serviço)

ENV_FILE="/home/ubuntu/bot-prelive-betfair/.env"
ERROS=0

VARS_ESPERADAS=(
  "BETFAIR_USERNAME"
  "BETFAIR_PASSWORD"
  "BETFAIR_APP_KEY"
  "SUPABASE_URL"
  "SUPABASE_SERVICE_KEY"
  "SUPABASE_BOT_ID"
  "TELEGRAM_TOKEN"
  "TELEGRAM_CHAT_ID"
  "ODDSPAPI_API_KEY"
)

echo "=== Validando $ENV_FILE ==="

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ ERRO: $ENV_FILE nao existe!"
  exit 1
fi

for VAR in "${VARS_ESPERADAS[@]}"; do
  LINHA=$(grep -E "^${VAR}=" "$ENV_FILE")
  if [ -z "$LINHA" ]; then
    echo "❌ FALTANDO: $VAR"
    ERROS=$((ERROS + 1))
  else
    VALOR="${LINHA#*=}"
    TAMANHO=${#VALOR}
    if [ "$TAMANHO" -eq 0 ]; then
      echo "⚠️  VAZIO: $VAR (existe mas sem valor)"
      ERROS=$((ERROS + 1))
    else
      echo "✅ OK: $VAR (tamanho: $TAMANHO)"
    fi
  fi
done

# Checagem cruzada: garante que os nomes ANTIGOS/errados nao existem mais
# (evita reintroducao dos bugs de nomenclatura ja corrigidos)
VARS_PROIBIDAS=("EMAIL" "SENHA" "APP_KEY" "SUPABASE_KEY")
for VAR in "${VARS_PROIBIDAS[@]}"; do
  if grep -qE "^${VAR}=" "$ENV_FILE"; then
    echo "⚠️  AVISO: variavel antiga '$VAR' ainda presente no .env (nome legado, confirme que nao e usada por engano)"
  fi
done

echo "=========================="
if [ "$ERROS" -eq 0 ]; then
  echo "✅ Tudo OK — seguro reiniciar os servicos."
  exit 0
else
  echo "❌ $ERROS problema(s) encontrado(s) — corrija antes de reiniciar os servicos!"
  exit 1
fi
