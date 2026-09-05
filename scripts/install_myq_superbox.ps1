param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,
    [string]$AdbSerial = ""
)

$ErrorActionPreference = "Stop"
$PackageName = "com.chamberlain.android.liftmaster.myq"

if (-not $AdbSerial) {
    $AdbSerial = (& "$PSScriptRoot\connect_superbox.ps1" | Select-Object -Last 1).Trim()
}
if (-not $AdbSerial) { throw "Could not resolve Superbox ADB serial" }

Write-Host "Superbox: $AdbSerial"
& adb -s $AdbSerial shell getprop ro.build.version.release
& adb -s $AdbSerial shell getprop ro.product.cpu.abilist

$item = Get-Item $PackagePath
if ($item.PSIsContainer) {
    $apks = @(Get-ChildItem $item.FullName -Filter *.apk | Sort-Object Name)
    if ($apks.Count -eq 0) { throw "No APKs found in $PackagePath" }
    Write-Host "Installing $($apks.Count) split APKs..."
    & adb -s $AdbSerial install-multiple -r -d @($apks.FullName)
} else {
    if ($item.Extension -ne ".apk") {
        throw "PackagePath must be an .apk file or a directory containing split APKs"
    }
    & adb -s $AdbSerial install -r -d $item.FullName
}
if ($LASTEXITCODE -ne 0) { throw "adb install failed" }

Write-Host "Installed package information:"
& adb -s $AdbSerial shell dumpsys package $PackageName | Select-String "versionName=|versionCode="

Write-Host "Launching myQ..."
& adb -s $AdbSerial shell monkey -p $PackageName -c android.intent.category.LAUNCHER 1 | Out-Null
Write-Host "Done. Complete login interactively; credentials are intentionally never accepted by this script."
