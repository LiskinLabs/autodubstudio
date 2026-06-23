$logFile = "C:\Users\silvestr.liskin\.gemini\antigravity-cli\brain\f54a247a-2350-4d39-a63b-bfb9476e1fc3\.system_generated\tasks\task-1252.log"
Get-Content -Path $logFile -Wait -Tail 10 | ForEach-Object {
    if ($_ -match "Successfully finished: C:\\Users\\silvestr.liskin\\Downloads\\recordings\\ACP training-20251008_100238-Meeting Recording 1.mp4") {
        Write-Host "First video finished. Killing python process..."
        Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue
        Write-Host "Starting fast script for remaining videos..."
        $env:PYTHONIOENCODING="utf-8"
        Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "python", "-u", "run_remaining.py" -RedirectStandardOutput "C:\Users\silvestr.liskin\Desktop\AutoDubStudio\fast_processing.log"
        break
    }
}
