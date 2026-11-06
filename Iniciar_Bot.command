#!/bin/bash
cd "$(dirname "$0")"
echo "========================================================"
echo "  🤖 INICIANDO ASISTENTE TELEGRAM + CONSULTORA"
echo "========================================================"
source venv/bin/activate
python3 -m src.bot
