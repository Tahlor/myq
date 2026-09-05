param(
    [Parameter(Mandatory = $true)]
    [string]$ApkDirectory,
    [string]$OutputDirectory = "jadx-output"
)

$ErrorActionPreference = "Stop"
if (-not (Get-Command jadx -ErrorAction SilentlyContinue)) {
    throw "jadx was not found on PATH"
}

$apks = @(Get-ChildItem $ApkDirectory -Filter *.apk | Sort-Object Name)
if ($apks.Count -eq 0) { throw "No APK files found in $ApkDirectory" }

$base = $apks | Where-Object { $_.Name -match "(^|-)base\.apk$" } | Select-Object -First 1
if (-not $base) { $base = $apks | Select-Object -First 1 }

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Write-Host "Decompiling $($base.FullName) -> $OutputDirectory"
& jadx --show-bad-code --deobf -d $OutputDirectory $base.FullName
if ($LASTEXITCODE -ne 0) { throw "jadx failed" }

python "$PSScriptRoot\..\tools\summarize_jadx.py" $OutputDirectory
