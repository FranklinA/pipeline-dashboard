#!/bin/bash
# Levanta backend y frontend en paralelo

echo "Iniciando backend en http://localhost:8000 ..."
cd backend
python -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Iniciando frontend en http://localhost:5173 ..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Abre http://localhost:5173 en el browser"
echo "Presiona Ctrl+C para detener ambos"

# Al presionar Ctrl+C mata ambos procesos
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
