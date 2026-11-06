# Guitar Chord Studio Local Launcher
$ErrorActionPreference = "Continue"

Write-Host "`n[1/3] 기존 서버 프로세스 정리 중..." -ForegroundColor Cyan
Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*GUITAR*" } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$PythonExe = Join-Path $ScriptDir ".venv-audio-model\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

Write-Host "[2/3] Chord Studio v2 고성능 AI 서버 시작 중..." -ForegroundColor Cyan
$serverJob = Start-Process -FilePath $PythonExe -ArgumentList "chord_studio_v2/server_v2.py --port 8766 --host 0.0.0.0 --public" -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 2

Write-Host "[3/3] 외부 공개 터널(guitarlab & Cloudflare) 연결 중..." -ForegroundColor Cyan
$logFile = Join-Path $ScriptDir "chord_studio_v2\runs\tunnel.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $logFile) | Out-Null
if (Test-Path $logFile) { Remove-Item $logFile -Force }

$cfExe = Join-Path $ScriptDir "bin\cloudflared.exe"
$cfJob = $null
if (Test-Path $cfExe) {
    $cfJob = Start-Process -FilePath $cfExe -ArgumentList "tunnel --url http://127.0.0.1:8766" -RedirectStandardError $logFile -PassThru -WindowStyle Hidden
}

# Wait up to 6 seconds for Cloudflare URL
$cfUrl = "준비 중..."
for ($i = 0; $i -lt 12; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Path $logFile) {
        $content = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
        if ($content -match "https://[a-zA-Z0-9-]+\.trycloudflare\.com") {
            $cfUrl = $matches[0]
            break
        }
    }
}

Clear-Host
Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host "             🎸 Guitar Chord Studio 로컬 서버 가동 완료!               " -ForegroundColor Green
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host ""
Write-Host " [★] 커뮤니티 공유용 고정 영문 주소:" -ForegroundColor Yellow
Write-Host "      👉 https://guitarlab.loca.lt" -ForegroundColor Cyan
Write-Host ""
Write-Host " [★] 초고속 다이렉트 주소 (보안 경고 없음):" -ForegroundColor Yellow
Write-Host "      👉 $cfUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host " [★] 내 컴퓨터에서 접속:" -ForegroundColor Gray
Write-Host "      👉 http://127.0.0.1:8766" -ForegroundColor Gray
Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host " * 모니터만 끄고 주무셔도 컴퓨터 본체가 켜져 있는 동안 계속 접속됩니다!" -ForegroundColor White
Write-Host " * 방문자가 분석한 지판 4점 데이터는 'chord_studio_v2/fretboard_data/'에 자동 저장됩니다." -ForegroundColor White
Write-Host " * 브라우저별 기록 격리가 적용되어 다른 사람은 내 분석 기록을 볼 수 없습니다." -ForegroundColor White
Write-Host " * 서버를 끄시려면 이 창을 닫으시거나 [스튜디오_종료.bat]을 실행하세요." -ForegroundColor Magenta
Write-Host "=======================================================================" -ForegroundColor Green
Write-Host ""

Start-Process "http://127.0.0.1:8766"

# Start localtunnel with subdomain in foreground to keep script alive and maintain guitarlab.loca.lt
npx --yes localtunnel --port 8766 --subdomain guitarlab
