param(
    [string]$AdbSerial = "192.168.187.153:5858",
    [string]$AdbPath = "adb",
    [string]$OutputPath = "config\cloud_session.json",
    [string]$AppVersion = "5.243.1.73243",
    [string]$UserAgent = "S7MAX/Android 12"
)

$ErrorActionPreference = "Stop"
$PackageName = "com.chamberlain.android.liftmaster.myq"
$PrefsPath = "/data/user/0/$PackageName/shared_prefs/LiftmasterMyQPrefs.xml"

function Read-RootFile([string]$Path) {
    $text = (& $AdbPath -s $AdbSerial exec-out su 0 cat $Path | Out-String)
    if ($LASTEXITCODE -ne 0 -or -not $text.Trim()) {
        throw "Could not read the myQ preference file from the Superbox."
    }
    return $text
}

function Get-PrefValue([hashtable]$Values, [string]$Name) {
    if (-not $Values.ContainsKey($Name)) {
        return ""
    }
    return [string]$Values[$Name]
}

function Decrypt-PrefValue(
    [string]$Ciphertext,
    [byte[]]$Key,
    [byte[]]$Iv
) {
    if (-not $Ciphertext) {
        return ""
    }

    $aes = [System.Security.Cryptography.Aes]::Create()
    try {
        $aes.Mode = [System.Security.Cryptography.CipherMode]::CBC
        $aes.Padding = [System.Security.Cryptography.PaddingMode]::PKCS7
        $aes.KeySize = 256
        $aes.BlockSize = 128
        $aes.Key = $Key
        $aes.IV = $Iv
        $cipherBytes = [Convert]::FromBase64String($Ciphertext)
        $decryptor = $aes.CreateDecryptor()
        try {
            $plainBytes = $decryptor.TransformFinalBlock($cipherBytes, 0, $cipherBytes.Length)
            return [Text.Encoding]::UTF8.GetString($plainBytes)
        } finally {
            $decryptor.Dispose()
        }
    } finally {
        $aes.Dispose()
    }
}

$xmlText = Read-RootFile $PrefsPath
$document = [System.Xml.XmlDocument]::new()
$document.LoadXml($xmlText)
$values = @{}
foreach ($node in $document.DocumentElement.ChildNodes) {
    $name = $node.GetAttribute("name")
    if (-not $name) {
        continue
    }
    $value = if ($node.HasAttribute("value")) { $node.GetAttribute("value") } else { $node.InnerText }
    $values[$name] = [string]$value
}

$ivText = Get-PrefValue $values "vW74vkdpqqg"
if (-not $ivText) {
    throw "The app has not initialized its encrypted preference key yet."
}

# This is the app's public build-time encryption phrase, recovered from the
# installed APK. It protects app-local storage, not the owner's myQ password.
$secretPhrase = "zyxwvuts©2018ChamberlainGroupzyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxw"
$digest = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($secretPhrase))
$key = New-Object byte[] 32
$copyLength = [Math]::Min(32, $digest.Length - 3)
[Array]::Copy($digest, 3, $key, 0, $copyLength)
$iv = [Convert]::FromBase64String($ivText)

$accessToken = Decrypt-PrefValue (Get-PrefValue $values "vV42ykopqqt") $key $iv
$refreshToken = Decrypt-PrefValue (Get-PrefValue $values "sW10ykapqqh") $key $iv
if (-not $accessToken -or -not $refreshToken) {
    throw "The official myQ app does not currently have both OAuth tokens. Authenticate it first, then rerun this extractor."
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $resolvedOutput
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$session = [ordered]@{
    access_token = $accessToken
    refresh_token = $refreshToken
    client_id = "ANDROID_CGI_MYQ"
    app_version = $AppVersion
    user_agent = $UserAgent
}
$tempPath = "$resolvedOutput.$([Guid]::NewGuid().ToString('N')).tmp"
try {
    $json = $session | ConvertTo-Json
    [IO.File]::WriteAllText($tempPath, "$json`n", [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $resolvedOutput -Force
} finally {
    if (Test-Path -LiteralPath $tempPath) {
        Remove-Item -LiteralPath $tempPath -Force
    }
}

[pscustomobject]@{
    status = "ok"
    output = $resolvedOutput
    access_token_present = $true
    refresh_token_present = $true
    client_id = "ANDROID_CGI_MYQ"
} | ConvertTo-Json
