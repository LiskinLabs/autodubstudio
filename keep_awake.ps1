param($durationMinutes = 300)
$wshell = New-Object -ComObject wscript.shell
$i = 0
Write-Host "Keep Awake started for $durationMinutes minutes..."
while ($i -lt $durationMinutes) {
    Start-Sleep -Seconds 60
    $wshell.SendKeys('{F15}')
    $i++
}
Write-Host "Keep Awake finished."
