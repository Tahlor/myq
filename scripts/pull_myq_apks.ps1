param(
    [string]$AdbSerial = "",
    [string]$OutputRoot = "captures\apk"
)

$ErrorActionPreference = "Stop"
$PackageName = "com.chamberlain.android.liftmaster.myq"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $OutputRoot $stamp
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$paths = @(& adb -s $AdbSerial shell pm path $PackageName) |
    ForEach-Object { ($_ -replace "^package:", "").Trim() } |
    Where-Object { $_ }
if ($paths.Count -eq 0) { throw "$PackageName is not installed" }

$index = 0
foreach ($remotePath in $paths) {
    $leaf = Split-Path $remotePath -Leaf
    $localName = "{0:D2}-{1}" -f $index, $leaf
    & adb -s $AdbSerial pull $remotePath (Join-Path $outDir $localName)
    if ($LASTEXITCODE -ne 0) { throw "Failed to pull $remotePath" }
    $index++
}

& adb -s $AdbSerial shell dumpsys package $PackageName |
    Out-File -Encoding utf8 (Join-Path $outDir "package.txt")

Write-Output (Resolve-Path $outDir).Path
