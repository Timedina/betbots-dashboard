#!/bin/bash

echo "================================"
echo "  ATUALIZANDO BOT BETFAIR..."
echo "================================"

# Entra na pasta do bot
cd ~/bot-prelive-betfair

# Baixa as atualizações do GitHub
echo "📥 Baixando atualizações..."
git pull

# Mata o screen antigo se existir
echo "🛑 Parando bot antigo..."
screen -S bot -X quit 2>/dev/null

# Aguarda 2 segundos
sleep 2

# Inicia o bot em novo screen
echo "🚀 Iniciando bot..."
screen -dmS bot python3 bot_prelive.py

echo "================================"
echo "  ✅ BOT ATUALIZADO E RODANDO!"
echo "================================"
echo ""
echo "Para ver o bot:    screen -r bot"
echo "Para sair:         Ctrl+A → D"
