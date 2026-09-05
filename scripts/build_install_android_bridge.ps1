param(
    [string]$AdbSerial = "",
    [string]$ApiKey = "",
    [string]$DoorConfigPath = "",
    [string]$GradleCommand = "gradle",
    [switch]$NoEnableAccessibility
)

$ErrorActionPreference = "Stop"
$PackageName = "com.tahlor.myqbridge"
$ServiceComponent = "com.tahlor.myqbridge/com.tahlor.myqbridge.BridgeAccessibilityService"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }
if (-not $ApiKey) {
    $ApiKey = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
}
if ($ApiKey.Length -lt 16) { throw "ApiKey must be at least 16 characters" }

$gradle = Get-Command $GradleCommand -ErrorAction SilentlyContinue
if (-not $gradle) {
    throw "Gradle was not found. Install Gradle 8.x / use Android Studio, or pass -GradleCommand."
}

$project = Resolve-Path "$PSScriptRoot\..\android_bridge"
& $gradle.Source -p $project.Path :app:assembleDebug
if ($LASTEXITCODE -ne 0) { throw "Android bridge build failed" }

$apk = Join-Path $project.Path "app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path $apk)) { throw "Expected APK not found at $apk" }
& adb -s $AdbSerial install -r $apk
if ($LASTEXITCODE -ne 0) { throw "Android bridge install failed" }

& adb -s $AdbSerial shell am start -n "$PackageName/.MainActivity" --es api_key $ApiKey | Out-Null
Start-Sleep -Seconds 1

if ($DoorConfigPath) {
    & "$PSScriptRoot\push_bridge_config.ps1" -AdbSerial $AdbSerial -ConfigPath $DoorConfigPath | Out-Null
}

if (-not $NoEnableAccessibility) {
    $current = (& adb -s $AdbSerial shell settings get secure enabled_accessibility_services).Trim()
    if ($current -eq "null") { $current = "" }
    $services = @($current -split ':' | Where-Object { $_ })
    if ($services -notcontains $ServiceComponent) {
        $services += $ServiceComponent
        $newValue = $services -join ':'
        & adb -s $AdbSerial shell settings put secure enabled_accessibility_services $newValue
    }
    & adb -s $AdbSerial shell settings put secure accessibility_enabled 1
}

$route = (& adb -s $AdbSerial shell ip route get 1.1.1.1 2>$null) -join ' '
$deviceIp = if ($route -match '\bsrc\s+(\d{1,3}(?:\.\d{1,3}){3})') { $Matches[1] } else { "<superbox-ip>" }

Write-Host "Native myQ bridge installed."
Write-Host "Endpoint: http://${deviceIp}:8765"
Write-Host "API key: $ApiKey"
Write-Host "Test: Invoke-RestMethod http://${deviceIp}:8765/health"
Write-Host "Debug nodes: Invoke-RestMethod http://${deviceIp}:8765/debug/nodes -Headers @{ 'X-API-Key' = '$ApiKey' }"
Write-Output $ApiKey
