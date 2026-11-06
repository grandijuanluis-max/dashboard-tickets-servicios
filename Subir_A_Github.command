#!/bin/bash
cd "$(dirname "$0")"
echo "========================================================"
echo "  🚀 SUBIENDO CAMBIOS A GITHUB (dashboard-tickets-servicios)"
echo "========================================================"
git push origin main
echo ""
echo "========================================================"
echo "  ✅ Proceso terminado. Presioná una tecla para salir..."
echo "========================================================"
read -n 1
