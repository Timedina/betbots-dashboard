#!/usr/bin/env bash
set -e

CONTEXT_FILE="$HOME/bot-prelive-betfair/CONTEXT.md"
DATA=$(date +"%d/%m/%Y %H:%M")

if [ ! -f "$CONTEXT_FILE" ]; then
    echo "ERRO: $CONTEXT_FILE não encontrado. Crie o arquivo base primeiro."
    exit 1
fi

if [ -n "$1" ]; then
    {
        echo ""
        echo "## Atualização $DATA"
        echo "- $1"
    } >> "$CONTEXT_FILE"
    echo "Adicionado ao CONTEXT.md:"
    echo "  ## Atualização $DATA"
    echo "  - $1"
else
    TMP_FILE=$(mktemp)
    echo "## Atualização $DATA" > "$TMP_FILE"
    echo "- " >> "$TMP_FILE"
    ${EDITOR:-nano} "$TMP_FILE"
    echo "" >> "$CONTEXT_FILE"
    cat "$TMP_FILE" >> "$CONTEXT_FILE"
    rm "$TMP_FILE"
    echo "Atualização adicionada ao CONTEXT.md."
fi

echo ""
echo "Últimas linhas do CONTEXT.md agora:"
tail -n 10 "$CONTEXT_FILE"
