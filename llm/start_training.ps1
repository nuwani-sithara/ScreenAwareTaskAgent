# PowerShell script to run training in background with logging
$scriptPath = "D:\SLIIT\Y4S1\RP\Project _works\ScreenAwareTaskAgent\llm_n"
$logFile = "$scriptPath\training.log"
$pythonExe = "$scriptPath\venv\Scripts\python.exe"
$trainScript = "$scriptPath\scripts\train_automation.py"

# Change to the script directory
Set-Location -LiteralPath $scriptPath

# Start training in background process
Write-Host "Starting training in background..."
Write-Host "Output log: $scriptPath\training_output.log"
Write-Host "Error log: $scriptPath\training_error.log"

# Start the process with proper quoting
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $pythonExe
$psi.Arguments = "`"$trainScript`""
$psi.WorkingDirectory = $scriptPath
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

$process = [System.Diagnostics.Process]::Start($psi)

# Redirect output to files asynchronously
$outputFile = [System.IO.File]::Create("$scriptPath\training_output.log")
$errorFile = [System.IO.File]::Create("$scriptPath\training_error.log")

$outputWriter = New-Object System.IO.StreamWriter($outputFile)
$errorWriter = New-Object System.IO.StreamWriter($errorFile)

$outputWriter.AutoFlush = $true
$errorWriter.AutoFlush = $true

Register-ObjectEvent -InputObject $process -EventName "OutputDataReceived" -Action {
    $outputWriter.WriteLine($EventArgs.Data)
} | Out-Null

Register-ObjectEvent -InputObject $process -EventName "ErrorDataReceived" -Action {
    $errorWriter.WriteLine($EventArgs.Data)
} | Out-Null

$process.BeginOutputReadLine()
$process.BeginErrorReadLine()

Write-Host ""
Write-Host "Training started with PID: $($process.Id)"
Write-Host ""
Write-Host "To check progress:"
Write-Host "  Get-Content '$scriptPath\training_output.log' -Tail 50 -Wait"
Write-Host ""
Write-Host "To check errors:"
Write-Host "  Get-Content '$scriptPath\training_error.log' -Tail 50"
Write-Host ""
Write-Host "To check if running:"
Write-Host "  Get-Process -Id $($process.Id) -ErrorAction SilentlyContinue"
Write-Host ""
Write-Host "To stop training:"
Write-Host "  Stop-Process -Id $($process.Id)"
