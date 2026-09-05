param(
    [string]$DeviceIP = "192.168.187.153",
    [int[]]$Ports = @(5858, 5555)
)

$ErrorActionPreference = "Stop"

function Get-AdbSerialForIp([string]$Ip) {
    foreach ($line in (& adb devices)) {
        if ($line -match "^$([regex]::Escape($Ip)):\d+\s+device\b") {
            return ($line -split "\s+")[0]
        }
    }
    return $null
}

function Try-AdbConnect([string]$Target) {
    & adb connect $Target | Out-Null
    Start-Sleep -Milliseconds 400
    return Get-AdbSerialForIp $DeviceIP
}

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "adb was not found on PATH"
}

& adb start-server | Out-Null
$serial = Get-AdbSerialForIp $DeviceIP
if ($serial) { Write-Output $serial; exit 0 }

foreach ($port in $Ports) {
    $serial = Try-AdbConnect "${DeviceIP}:$port"
    if ($serial) { Write-Output $serial; exit 0 }
}

foreach ($line in (& adb mdns services 2>$null)) {
    if ($line -match "\b$([regex]::Escape($DeviceIP)):(\d+)\b") {
        $serial = Try-AdbConnect "${DeviceIP}:$($Matches[1])"
        if ($serial) { Write-Output $serial; exit 0 }
    }
}

throw "No ADB endpoint found for $DeviceIP. Check adb mdns services and the Superbox DHCP address."
