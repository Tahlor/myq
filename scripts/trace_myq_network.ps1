param(
    [string]$AdbSerial = "",
    [string]$OutputRoot = "captures\frida",
    [switch]$InstallFridaServer
)

$ErrorActionPreference = "Stop"
$PackageName = "com.chamberlain.android.liftmaster.myq"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }
if (-not (Get-Command frida -ErrorAction SilentlyContinue)) {
    throw "frida-tools is required on the host (pip install frida-tools)"
}

if ($InstallFridaServer) {
    $installer = Resolve-Path "$PSScriptRoot\..\..\superbox\scripts\install_frida_server.ps1" -ErrorAction SilentlyContinue
    if (-not $installer) {
        throw "Expected sibling Tahlor/superbox checkout; run its scripts/install_frida_server.ps1 manually instead"
    }
    & $installer.Path -AdbSerial $AdbSerial
}

& adb -s $AdbSerial forward --remove tcp:27042 2>$null | Out-Null
& adb -s $AdbSerial forward tcp:27042 tcp:27042 | Out-Null

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
$outFile = Join-Path $outDir "network-metadata.jsonl"
$scriptPath = Resolve-Path "$PSScriptRoot\..\reverse\frida\trace_network.js"

Write-Host "Tracing myQ PID $pidValue. Output is metadata-only but remains ignored until reviewed. Ctrl+C to stop."
& frida -H 127.0.0.1:27042 -p $pidValue -l $scriptPath.Path 2>&1 |
    Tee-Object -FilePath $outFile
