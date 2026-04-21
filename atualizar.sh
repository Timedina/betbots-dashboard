#!/bin/bash
echo "================================"
echo "  ATUALIZANDO BOT BETFAIR..."
echo "================================"

cd ~/bot-prelive-betfair

echo "📥 Baixando atualizações..."
git pull

echo "🔄 Reiniciando bot..."
sudo systemctl restart bot-betfair

echo "================================"
echo "  ✅ BOT ATUALIZADO E RODANDO!"
echo "================================"

sudo systemctl status bot-betfair --no-pager
