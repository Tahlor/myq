param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{1,3}(?:\.\d{1,3}){3}$')]
    [string]$CandidateIp,
    [string]$Pi3Host = "pi3",
    [string]$RouterHost = "192.168.187.1",
    [int]$RouterPort = 1222,
    [string]$RouterUser = "admin",
    [string]$RouterKeyPath = "/home/pi/.ssh/id_rsa",
    [string]$OutputRoot = "captures\lan"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    throw "ssh was not found on PATH"
}

$octets = $CandidateIp -split '\.' | ForEach-Object { [int]$_ }
if ($octets | Where-Object { $_ -gt 255 }) {
    throw "CandidateIp must be a valid IPv4 address"
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $OutputRoot ("conntrack-" + $stamp)
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$target = "$RouterUser@$RouterHost"
$sshOptions = "-o BatchMode=yes -o ConnectTimeout=5 -i $RouterKeyPath -p $RouterPort"
$listCommand = "/usr/sbin/conntrack -L -p tcp --dport 8883 2>/dev/null | grep -F $CandidateIp || true"
$procCommand = "cat /proc/net/nf_conntrack 2>/dev/null | grep -F $CandidateIp | grep -F dport=8883 || true"

$listPath = Join-Path $outDir "conntrack-list.txt"
$procPath = Join-Path $outDir "nf-conntrack.txt"

& ssh $Pi3Host "ssh $sshOptions $target '$listCommand'" 2>&1 | Out-File -Encoding utf8 $listPath
if ($LASTEXITCODE -ne 0) {
    throw "Router conntrack query failed; inspect the ignored capture for SSH diagnostics."
}

& ssh $Pi3Host "ssh $sshOptions $target '$procCommand'" 2>&1 | Out-File -Encoding utf8 $procPath
if ($LASTEXITCODE -ne 0) {
    throw "Router nf_conntrack query failed; inspect the ignored capture for SSH diagnostics."
}

$listCount = @(Get-Content $listPath | Where-Object { $_ -match '(^|\s)src=' -or $_ -match 'tcp' }).Count
$procCount = @(Get-Content $procPath | Where-Object { $_ -match 'ESTABLISHED' -or $_ -match 'dport=8883' }).Count

[pscustomobject]@{
    status = "ok"
    candidate_ip = "<redacted-local-candidate>"
    conntrack_entries = $listCount
    nf_conntrack_entries = $procCount
    raw_capture = (Resolve-Path $outDir).Path
    note = "Read-only metadata only; no packet payload or TLS/MQTT framing is captured."
} | ConvertTo-Json
