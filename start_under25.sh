#!/bin/bash
cd /home/ubuntu/bot-prelive-betfair
set -a
source .env
set +a
export SUPABASE_BOT_ID=4101d27c-2130-4517-b596-3969cf06f049
python3 bot_under25.py
