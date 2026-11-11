$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskWorkerPython = Join-Path $PSScriptRoot '.venv-audio-separation/Scripts/python.exe'
$taskAppPython = Join-Path $PSScriptRoot '.venv-audio-model/Scripts/python.exe'
$taskStamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$taskStage = Join-Path $PSScriptRoot "build/release_$taskStamp"
New-Item -ItemType Directory -Path $taskStage | Out-Null
& $taskWorkerPython -m PyInstaller --noconfirm --distpath "$taskStage/worker_dist" --workpath "$taskStage/worker_build" GuitarSeparator.spec
if($LASTEXITCODE -ne 0){throw 'Separation worker build failed.'}
& $taskAppPython -m PyInstaller --noconfirm --distpath "$taskStage/app_dist" --workpath "$taskStage/app_build" GuitarChordStudio.spec
if($LASTEXITCODE -ne 0){throw 'Desktop build failed.'}
$taskApp = Join-Path $taskStage 'app_dist/GuitarChordStudio'
New-Item -ItemType Directory -Path "$taskApp/workers" | Out-Null
Copy-Item -LiteralPath "$taskStage/worker_dist/GuitarSeparator" -Destination "$taskApp/workers/GuitarSeparator" -Recurse
Write-Output "STAGED_RELEASE=$taskApp"
Write-Output 'Existing dist and user analyses remain untouched. Validate the staged EXE before distribution.'
