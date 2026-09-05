param(
    [string]$AdbSerial = "",
    [int]$Seconds = 60,
    [string]$OutputRoot = "captures\logcat"
)

$ErrorActionPreference = "Stop"
$PackageName = "com.chamberlain.android.liftmaster.myq"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }

$pidText = (& adb -s $AdbSerial shell pidof $PackageName).Trim()
if (-not $pidText) {
    & adb -s $AdbSerial shell monkey -p $PackageName -c android.intent.category.LAUNCHER 1 | Out-Null
    Start-Sleep -Seconds 2
    $pidText = (& adb -s $AdbSerial shell pidof $PackageName).Trim()
}
if (-not $pidText) { throw "$PackageName is not running" }
$pidValue = ($pidText -split "\s+")[0]

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $OutputRoot $stamp
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$raw = Join-Path $outDir "myq-raw.log"
$sanitized = Join-Path $outDir "myq-sanitized.log"

& adb -s $AdbSerial logcat -c
Write-Host "Capturing PID $pidValue for $Seconds seconds. Exercise only the myQ action you intend to observe."
$job = Start-Job -ScriptBlock {
    param($adbSerial, $pidArg, $path)
    & adb -s $adbSerial logcat --pid=$pidArg -v threadtime 2>&1 | Out-File -Encoding utf8 $path
} -ArgumentList $AdbSerial, $pidValue, $raw

Start-Sleep -Seconds $Seconds
Stop-Job $job -ErrorAction SilentlyContinue
Receive-Job $job -ErrorAction SilentlyContinue | Out-Null
Remove-Job $job -Force -ErrorAction SilentlyContinue

$text = Get-Content $raw -Raw
$text = $text -replace '(?i)(authorization\s*[:=]\s*bearer\s+)[A-Za-z0-9._~+/-]+=*', '$1<REDACTED>'
$text = $text -replace '(?i)(access_token|refresh_token|id_token|auth_token)(["''\s:=]+)[A-Za-z0-9._~+/-]+=*', '$1$2<REDACTED>'
$text = $text -replace '(?i)(cookie|set-cookie)(\s*[:=]\s*)[^\r\n]+', '$1$2<REDACTED>'
$text | Out-File -Encoding utf8 $sanitized

Write-Host "Raw capture (ignored): $raw"
Write-Host "Sanitized working copy (also ignored until manually reviewed): $sanitized"
Write-Output (Resolve-Path $outDir).Path
