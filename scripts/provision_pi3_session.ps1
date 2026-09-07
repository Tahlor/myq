[CmdletBinding()]
param(
    [string]$SessionPath = (Join-Path $PSScriptRoot '..\config\cloud_session.json'),
    [string]$SshTarget = 'pi@192.168.187.103',
    [string]$SshPath = 'ssh'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedSessionPath = [IO.Path]::GetFullPath($SessionPath)
if (-not (Test-Path -LiteralPath $resolvedSessionPath -PathType Leaf)) {
    throw "Cloud session file was not found: $resolvedSessionPath"
}

$raw = Get-Content -LiteralPath $resolvedSessionPath -Raw
$session = $raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace([string]$session.access_token) -or
    [string]::IsNullOrWhiteSpace([string]$session.refresh_token)) {
    throw 'Cloud session must contain access_token and refresh_token.'
}

# The script is sent as a command argument, but the token-bearing JSON is sent
# only on SSH stdin. The remote helper validates and atomically installs it as
# a 0600 file; neither token is printed or placed in a process argument.
$remoteScript = @'
import json
import os
import pathlib
import sys
import tempfile

path = pathlib.Path("/home/pi/bashrc/secure/myq_cloud_session.json")
data = json.loads(sys.stdin.read())
if not data.get("access_token") or not data.get("refresh_token"):
    raise SystemExit("session is missing required tokens")
path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    os.chmod(temp_name, 0o600)
    os.replace(temp_name, path)
    os.chmod(path, 0o600)
finally:
    try:
        os.unlink(temp_name)
    except FileNotFoundError:
        pass
print("myQ cloud session installed")
'@
$encodedScript = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes($remoteScript)
)
$remoteCommand = '/home/pi/Projects/py311/bin/python -c "import base64; exec(base64.b64decode(' +
    "'" + $encodedScript + "'" +
    '))"'

$raw | & $SshPath -o BatchMode=yes -o ConnectTimeout=10 $SshTarget $remoteCommand
if ($LASTEXITCODE -ne 0) {
    throw "Could not provision the Pi3 myQ cloud session (ssh exit $LASTEXITCODE)."
}

[pscustomobject]@{
    status = 'ok'
    target = $SshTarget
    remote_path = '/home/pi/bashrc/secure/myq_cloud_session.json'
    access_token_present = $true
    refresh_token_present = $true
} | ConvertTo-Json -Compress
