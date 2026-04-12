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

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$pythonPath = if (Test-Path $venvPython) { $venvPython } else { "C:\Users\Zacky Mrf\AppData\Local\Programs\Python\Python312\python.exe" }
$processes = @()

function Stop-ListenerOnPort {
    param([int]$Port)
    try {
        $listeners = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        if (-not $listeners) { return }

        $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $pids) {
            if ($procId -and $procId -ne $PID) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped stale process on port $Port (PID=$procId)" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host "Could not inspect port $Port listeners" -ForegroundColor DarkYellow
    }
}

# Clean old listeners so startup always serves fresh code.
Stop-ListenerOnPort -Port 8000
Stop-ListenerOnPort -Port 5173

# Start Backend
Write-Host "Starting Backend..." -ForegroundColor Cyan
$backendArgs = @("-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000")
$backend = Start-Process $pythonPath -ArgumentList $backendArgs -NoNewWindow -PassThru
Start-Sleep -Seconds 2
if (Get-Process -Id $backend.Id -ErrorAction SilentlyContinue) {
    $processes += $backend
} else {
    Write-Host "Backend process exited early. Check port 8000 usage or backend logs." -ForegroundColor Red
    exit 1
}

# Start Bot
Write-Host "Starting Telegram Bot..." -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($env:TELEGRAM_BOT_TOKEN)) {
    Write-Host "TELEGRAM_BOT_TOKEN missing, bot skipped." -ForegroundColor DarkYellow
} else {
    $bot = Start-Process $pythonPath -ArgumentList @("telegram_bot_advanced.py") -NoNewWindow -PassThru
    Start-Sleep -Seconds 2
    if (Get-Process -Id $bot.Id -ErrorAction SilentlyContinue) {
        $processes += $bot
    } else {
        Write-Host "Telegram bot exited early." -ForegroundColor DarkYellow
    }
}

# Start Frontend
Write-Host "Starting Frontend..." -ForegroundColor Cyan
Push-Location "frontend"
$frontend = Start-Process "npm.cmd" -ArgumentList @("run", "dev", "--", "--host", "0.0.0.0", "--port", "5173") -NoNewWindow -PassThru
Pop-Location
Start-Sleep -Seconds 3
if (Get-Process -Id $frontend.Id -ErrorAction SilentlyContinue) {
    $processes += $frontend
} else {
    Write-Host "Frontend dev server exited early." -ForegroundColor DarkYellow
}

Write-Host "All services running!" -ForegroundColor Green
Write-Host "Web: http://localhost:5173" -ForegroundColor Cyan
Write-Host "API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "WS : ws://localhost:8000/ws/live-buysell" -ForegroundColor Cyan

# Wait
try {
    $processes | ForEach-Object {
        if (Get-Process -Id $_.Id -ErrorAction SilentlyContinue) {
            Wait-Process -Id $_.Id -ErrorAction SilentlyContinue
        }
    }
}
catch {
    $processes | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}
