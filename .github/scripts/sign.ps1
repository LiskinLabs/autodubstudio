param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$FilePath
)

$maxRetries = 15
$retryDelaySeconds = 30

for ($i = 0; $i -lt $maxRetries; $i++) {
    Write-Host "Signing attempt $($i + 1) of $maxRetries for $FilePath..."
    & "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x86\signtool.exe" sign /debug /tr http://ts.ssl.com /td sha256 /fd sha256 /n "Silvestr Liskin" $FilePath
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Signing succeeded!"
        exit 0
    }
    
    Write-Host "Signing failed, waiting for SSL.com malware scan ($retryDelaySeconds seconds)..."
    Start-Sleep -Seconds $retryDelaySeconds
}

Write-Error "Failed to sign file after $maxRetries attempts."
exit 1
