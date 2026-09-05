param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [string]$AdbSerial = ""
)

$ErrorActionPreference = "Stop"
$PackageName = "com.tahlor.myqbridge"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }
$config = Resolve-Path $ConfigPath

# Launch once so Android creates the app-specific external-files directory.
& adb -s $AdbSerial shell am start -n "$PackageName/.MainActivity" | Out-Null
Start-Sleep -Milliseconds 700
$remoteDir = "/sdcard/Android/data/$PackageName/files"
& adb -s $AdbSerial shell mkdir -p $remoteDir
& adb -s $AdbSerial push $config.Path "$remoteDir/doors.json"
if ($LASTEXITCODE -ne 0) { throw "Failed to push door selector configuration" }

Write-Host "Updated $remoteDir/doors.json. The bridge reloads it on every request; no restart is required."
