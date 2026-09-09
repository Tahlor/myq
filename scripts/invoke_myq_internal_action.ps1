param(
    [ValidateSet("probe", "open", "close")]
    [string]$Action = "probe",
    [switch]$Execute,
    [ValidateSet("", "open", "close")]
    [string]$ConfirmAction = "",
    [string]$AdbSerial = "",
    [string]$AdbPath = "adb",
    [string]$FridaPath = "frida",
    [string]$ValidatedFridaVersion = "17.9.0",
    [bool]$EnsureFridaServer = $true
)

$ErrorActionPreference = "Stop"
$PackageName = "com.chamberlain.android.liftmaster.myq"
$DashboardActivity = "com.chamberlain.myq.main.HomeTabsActivity"

function Resolve-Executable([string]$Value, [string]$Name) {
    $command = Get-Command $Value -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    if (Test-Path -LiteralPath $Value) { return (Resolve-Path -LiteralPath $Value).Path }

    if ($Name -eq "adb" -and $Value -eq "adb") {
        $bundledAdb = Join-Path $HOME ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\site-packages\adbutils\binaries\adb.exe"
        if (Test-Path -LiteralPath $bundledAdb) { return $bundledAdb }
    }
    if ($Name -eq "frida" -and $Value -eq "frida") {
        $fridaCandidates = @(Get-ChildItem (Join-Path $env:APPDATA "Python\Python*\Scripts\frida.exe") -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
        if ($fridaCandidates.Count -gt 0) { return $fridaCandidates[0].FullName }
    }

    throw "$Name was not found at '$Value' or a known local fallback. Pass the explicit executable path."
}

if ($Execute) {
    if ($Action -eq "probe") { throw "-Execute requires -Action open or close." }
    if ($ConfirmAction -ne $Action) {
        throw "Live internal actuation requires -ConfirmAction $Action."
    }
} elseif ($ConfirmAction) {
    throw "-ConfirmAction is only valid together with -Execute."
}

$adb = Resolve-Executable $AdbPath "adb"
$frida = Resolve-Executable $FridaPath "frida"
$fridaVersion = ((& $frida --version | Select-Object -First 1).ToString()).Trim()
if ($fridaVersion -ne $ValidatedFridaVersion) {
    throw "Refusing unvalidated Frida $fridaVersion; Superbox attach is validated with $ValidatedFridaVersion."
}

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" -AdbPath $adb | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial." }

if ($EnsureFridaServer) {
    $server = (& $adb -s $AdbSerial shell ps -A | Select-String "frida-server-$ValidatedFridaVersion-android-arm")
    if (-not $server) {
        $installer = Resolve-Path "$PSScriptRoot\..\..\superbox\scripts\install_frida_server.ps1" -ErrorAction SilentlyContinue
        if (-not $installer) { throw "Matching frida-server is not running and sibling Tahlor/superbox installer was not found." }
        $oldPath = $env:PATH
        try {
            $env:PATH = "$(Split-Path $adb);$(Split-Path $frida);$oldPath"
            & $installer.Path -AdbSerial $AdbSerial -FridaVersion $ValidatedFridaVersion | Out-Host
        } finally {
            $env:PATH = $oldPath
        }
    }
}

& $adb -s $AdbSerial shell am start -n "$PackageName/$DashboardActivity" | Out-Null
Start-Sleep -Seconds 2
$myqPid = ((& $adb -s $AdbSerial shell pidof $PackageName) -join " ").Trim()
if (-not $myqPid) { throw "Official myQ process is not running after HomeTabsActivity launch." }
$myqPid = ($myqPid -split "\s+")[0]

& $adb -s $AdbSerial forward --remove tcp:27042 2>$null | Out-Null
& $adb -s $AdbSerial forward tcp:27042 tcp:27042 | Out-Null

$agentPath = Resolve-Path "$PSScriptRoot\..\reverse\frida\garage_internal_control.js"
$agent = Get-Content -Raw $agentPath.Path
$executeLiteral = if ($Execute) { "true" } else { "false" }
$prefix = "globalThis.MYQ_ACTION = '$Action';`nglobalThis.MYQ_EXECUTE = $executeLiteral;`n"
$tempPath = Join-Path $env:TEMP ("myq-internal-" + [guid]::NewGuid().ToString("N") + ".js")
[IO.File]::WriteAllText($tempPath, $prefix + $agent, (New-Object System.Text.UTF8Encoding($false)))

try {
    $timeout = if ($Execute) { 24 } else { 10 }
    $rawOutput = @(& $frida -H 127.0.0.1:27042 -p $myqPid -l $tempPath -q -t $timeout 2>&1 | ForEach-Object { $_.ToString() })
} finally {
    Remove-Item -LiteralPath $tempPath -Force -ErrorAction SilentlyContinue
}

$events = @()
foreach ($line in $rawOutput) {
    if (-not $line.TrimStart().StartsWith("{")) { continue }
    try { $events += ($line | ConvertFrom-Json) } catch { }
}
if (-not $events) { throw "Frida returned no structured internal-control events." }

foreach ($event in $events) {
    if ($event.kind -in @("fatal", "blocked", "dispatch_error", "unverified")) {
        $detail = if ($event.data.reason) { $event.data.reason } elseif ($event.data.error) { $event.data.error } else { $event.kind }
        throw "Internal myQ control failed closed: $detail"
    }
}

if ($Execute) {
    $noop = $events | Where-Object { $_.kind -eq "noop" } | Select-Object -Last 1
    $verified = $events | Where-Object { $_.kind -eq "verified" } | Select-Object -Last 1
    if (-not $noop -and -not $verified) {
        throw "Internal command outcome is ambiguous; do not retry the command."
    }
} elseif ($Action -eq "probe") {
    $openSuppressed = $events | Where-Object { $_.kind -eq "suppressed" -and $_.data.action -eq "open" }
    $closeSuppressed = $events | Where-Object { $_.kind -eq "suppressed" -and $_.data.action -eq "close" }
    if (-not $openSuppressed -or -not $closeSuppressed) { throw "Dry-run probe did not intercept both open and close paths." }
} else {
    $noop = $events | Where-Object { $_.kind -eq "noop" } | Select-Object -Last 1
    $suppressed = $events | Where-Object { $_.kind -eq "suppressed" -and $_.data.action -eq $Action }
    if (-not $noop -and -not $suppressed) { throw "Dry-run did not intercept requested $Action path." }
}

$events | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 6 }