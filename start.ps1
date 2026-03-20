# Levanta backend y frontend en ventanas separadas de PowerShell

Write-Host "Iniciando backend en http://localhost:8000 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; python -m uvicorn app.main:app --reload --port 8000"

Write-Host "Iniciando frontend en http://localhost:5173 ..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Abre http://localhost:5173 en el browser"
Write-Host "Cierra las ventanas de PowerShell para detener los servidores"
