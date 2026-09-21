@echo off
cd /d C:\net_monitor

powershell -Command ^
    "$SaveDB = 'C:\net_monitor\SaveDB';" ^
    "$dbPath = 'C:\net_monitor\db\traffic.db';" ^
    "if (-not (Test-Path $SaveDB)) { New-Item -ItemType Directory -Path $SaveDB };" ^
    "if (-not (Test-Path 'C:\net_monitor\db')) { New-Item -ItemType Directory -Path 'C:\net_monitor\db' };" ^
    "if (Test-Path $dbPath) { $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'; Move-Item $dbPath ($SaveDB + '\traffic_' + $stamp + '.db') }"

start "NetMonitor" /MIN cmd /c "python C:\net_monitor\main.py monitor -u moaba -d IT -s ""Mohammadamin's S21 FE"" >> C:\net_monitor\monitor.log 2>&1"

echo مانیتور شروع شد
timeout /t 3 