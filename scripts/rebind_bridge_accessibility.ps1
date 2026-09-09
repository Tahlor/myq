param(
    [string]$AdbSerial = "",
    [string]$AdbPath = "adb",
    [switch]$UseRoot
)

$ErrorActionPreference = "Stop"
$PackageName = "com.tahlor.myqbridge"
$ServiceComponent = "com.tahlor.myqbridge/com.tahlor.myqbridge.BridgeAccessibilityService"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" -AdbPath $AdbPath | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }

$adb = Get-Command $AdbPath -ErrorAction Stop

function Set-SecureSetting {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($UseRoot) {
        & $adb.Source -s $AdbSerial shell su 0 settings put secure $Name $Value
    } else {
        & $adb.Source -s $AdbSerial shell settings put secure $Name $Value
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to update secure setting $Name" }
}

$current = (& $adb.Source -s $AdbSerial shell settings get secure enabled_accessibility_services | Out-String).Trim()
if ($current -eq "null") { $current = "" }
$services = @($current -split ':' | Where-Object { $_ })

# A package update can leave the component listed but detached. Toggling the
# manager around a preserved remove/re-add is the reliable rebind trigger
# observed on this Superbox firmware.
$withoutBridge = @($services | Where-Object { $_ -ne $ServiceComponent })
Set-SecureSetting -Name "accessibility_enabled" -Value "0"
Set-SecureSetting -Name "enabled_accessibility_services" -Value ($withoutBridge -join ':')
Start-Sleep -Milliseconds 500
$newValue = (@($withoutBridge + $ServiceComponent) -join ':')
Set-SecureSetting -Name "enabled_accessibility_services" -Value $newValue
Set-SecureSetting -Name "accessibility_enabled" -Value "1"

# The foreground host owns TCP 8765 and is intentionally started from the
# visible companion activity, not from a background LAN request.
& $adb.Source -s $AdbSerial shell am start -n "$PackageName/.MainActivity" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to start the bridge activity" }
Start-Sleep -Seconds 5

$dump = (& $adb.Source -s $AdbSerial shell dumpsys accessibility | Out-String)
$boundSection = [regex]::Match(
    $dump,
    'Bound services:(.*?)(?:\r?\n\s*Enabled services:)',
    [System.Text.RegularExpressions.RegexOptions]::Singleline
).Groups[1].Value
$enabledSection = [regex]::Match(
    $dump,
    'Enabled services:(.*?)(?:\r?\n\s*Binding services:)',
    [System.Text.RegularExpressions.RegexOptions]::Singleline
).Groups[1].Value

if (-not $enabledSection.Contains($ServiceComponent)) {
    throw "The myQ bridge accessibility service is not enabled"
}
if (-not $boundSection.Contains("myQ LAN Bridge")) {
    throw "The myQ bridge accessibility service is enabled but not bound"
}

Write-Host "myQ bridge accessibility service is enabled and bound."
Write-Host "Existing accessibility services were preserved."
