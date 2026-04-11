# Startup Script for Ave Monitoring System
Write-Host "Starting Ave Monitoring System..." -ForegroundColor Green

# Load environment
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

$pythonPath = "C:\Users\Zacky Mrf\AppData\Local\Programs\Python\Python312\python.exe"
$processes = @()

# Start Backend
Write-Host "Starting Backend..." -ForegroundColor Cyan
$backend = Start-Process $pythonPath -ArgumentList "-m uvicorn api_server:app --host 0.0.0.0 --port 8000" -NoNewWindow -PassThru
$processes += $backend
Start-Sleep -Seconds 2

# Start Bot
Write-Host "Starting Telegram Bot..." -ForegroundColor Cyan
$bot = Start-Process $pythonPath -ArgumentList "telegram_bot_advanced.py" -NoNewWindow -PassThru
$processes += $bot
Start-Sleep -Seconds 2

# Start Frontend
Write-Host "Starting Frontend..." -ForegroundColor Cyan
Push-Location "frontend"
$frontend = Start-Process "npm.cmd" -ArgumentList "run dev" -NoNewWindow -PassThru
Pop-Location
$processes += $frontend
Start-Sleep -Seconds 3

Write-Host "All services running!" -ForegroundColor Green
Write-Host "Web: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API: http://localhost:8000" -ForegroundColor Cyan

# Wait
try {
    $processes | ForEach-Object { Wait-Process -Id $_.Id }
}
catch {
    $processes | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}
