@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  NeuralQuant - OpenBB + Cloudflare Tunnel
echo ============================================
echo.

REM Kill any existing OpenBB or cloudflared processes
echo [1/5] Cleaning up old processes...
taskkill /F /FI "WINDOWTITLE eq openbb*" >nul 2>&1
powershell -Command "Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue" >nul 2>&1

REM Start OpenBB with FRED_API_KEY
echo [2/5] Starting OpenBB Platform API on port 6900...
set FRED_API_KEY=b09c2aae58f65cd63fffd0109aabc2ec
start /b openbb-api --host 127.0.0.1 --port 6900 > openbb_server.log 2>&1

echo Waiting for OpenBB to start...
timeout /t 10 /nobreak > nul

REM Verify OpenBB is running
powershell -Command "if (!(Test-NetConnection -ComputerName 127.0.0.1 -Port 6900 -WarningAction SilentlyContinue).TcpTestSucceeded) { Write-Host 'ERROR: OpenBB not responding on port 6900!'; exit 1 } else { Write-Host 'OpenBB is UP on port 6900' }"
if errorlevel 1 (
    echo.
    echo OpenBB failed to start. Check openbb_server.log
    pause
    exit /b 1
)

REM Test a quick API call
echo.
echo [3/5] Testing OpenBB API...
curl -s "http://127.0.0.1:6900/api/v1/equity/price/quote?provider=yfinance&symbol=AAPL" >nul 2>&1
if errorlevel 1 (
    echo WARNING: OpenBB API not responding to requests yet. May need more warmup time.
) else (
    echo OpenBB API responding OK.
)

REM Start Cloudflare quick tunnel
echo.
echo [4/5] Starting Cloudflare Tunnel...
echo This creates a random public URL that changes each restart.
powershell -Command "& 'C:\Program Files (x86)\cloudflared\cloudflared.exe' tunnel --url http://127.0.0.1:6900 2>&1 | ForEach-Object { $_; if ($_ -match 'https://[a-z0-9-]+\.trycloudflare\.com') { $script:url = $matches[0] } }" > cloudflare_tunnel.log 2>&1 &

echo Waiting for tunnel URL...
timeout /t 15 /nobreak > nul

REM Extract tunnel URL from log
set TUNNEL_URL=
for /f "tokens=*" %%i in ('powershell -Command "(Select-String -Path cloudflare_tunnel.log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1).Line"') do set TUNNEL_URL=%%i

if "%TUNNEL_URL%"=="" (
    REM Try alternate extraction
    for /f "tokens=6 delims=| " %%i in ('findstr "trycloudflare.com" cloudflare_tunnel.log 2^>nul') do set TUNNEL_URL=%%i
)

echo.
echo ============================================
echo  OpenBB is running!
echo ============================================
echo  Local:    http://127.0.0.1:6900
echo  Docs:     http://127.0.0.1:6900/docs
echo.
if not "%TUNNEL_URL%"=="" (
    echo  Public:   %TUNNEL_URL%
    echo.
    echo  ============================================
    echo  ACTION REQUIRED: Update Render env vars
    echo  ============================================
    echo  Go to: https://dashboard.render.com
    echo  Select: nq-api web service
    echo  Settings ^> Environment Variables:
    echo.
    echo    OPENBB_API_URL = %TUNNEL_URL%
    echo    OPENBB_ENABLED = true
    echo.
    echo  Then click "Save Changes" to trigger redeploy.
    echo  ============================================
) else (
    echo  WARNING: Could not extract tunnel URL from logs.
    echo  Check cloudflare_tunnel.log for the URL.
)
echo.
echo  Press Ctrl+C to stop both OpenBB and tunnel.
echo.
pause