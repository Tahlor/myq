[CmdletBinding()]
param(
    [string]$SourcePath = (Join-Path $PSScriptRoot '..\captures\credentials_myq.pi3.raw'),
    [string]$ConfigPath = (Join-Path $PSScriptRoot '..\config\myq_credentials.local.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
    throw "Credential source was not found: $SourcePath"
}

$lines = @(Get-Content -LiteralPath $SourcePath | ForEach-Object { $_.Trim() } | Where-Object { $_.Length -gt 0 })
if ($lines.Count -ne 2) {
    throw "Expected exactly two non-empty credential lines, found $($lines.Count)."
}
if ($lines[0] -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') {
    throw 'Credential line 1 is not shaped like an email address.'
}
if ($lines[1].Length -eq 0) {
    throw 'Credential line 2 is empty.'
}

$configDirectory = Split-Path -Parent $ConfigPath
if (-not (Test-Path -LiteralPath $configDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $configDirectory -Force | Out-Null
}

if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
} else {
    $config = [pscustomobject]@{}
}

$config | Add-Member -MemberType NoteProperty -Name email -Value $lines[0] -Force
$config | Add-Member -MemberType NoteProperty -Name password -Value $lines[1] -Force

$json = $config | ConvertTo-Json -Depth 10
[IO.File]::WriteAllText($ConfigPath, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

[pscustomobject]@{
    imported = $true
    email_length = $lines[0].Length
    password_length = $lines[1].Length
    config_path = [IO.Path]::GetFullPath($ConfigPath)
    keys = @($config.PSObject.Properties.Name)
} | ConvertTo-Json -Compress
