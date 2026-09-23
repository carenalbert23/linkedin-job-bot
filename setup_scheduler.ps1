# ─────────────────────────────────────────────────────────────────────────────
# Registers a daily Windows Task Scheduler job that runs job_search.py.
# Run it ONCE, from a normal PowerShell window (no admin needed):
#
#   powershell -ExecutionPolicy Bypass -File ".\setup_scheduler.ps1"
#
# Optional: change the time it runs
#   powershell -ExecutionPolicy Bypass -File ".\setup_scheduler.ps1" -At "09:30"
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$At       = "11:00",
    [string]$TaskName = "LinkedIn Job Search Bot"
)

# Resolve paths relative to this script, so the repo works wherever you clone it.
$repoDir    = $PSScriptRoot
$scriptPath = Join-Path $repoDir "job_search.py"

if (-not (Test-Path $scriptPath)) {
    Write-Error "job_search.py not found next to this script ($repoDir)."
    exit 1
}

# Find python.exe on PATH. ('python' on Windows can be the Store alias stub,
# which is a 0-byte launcher — so prefer py.exe when it's available.)
$pythonPath = $null
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) {
    $pythonPath = (& $py.Source -c "import sys; print(sys.executable)" 2>$null)
}
if (-not $pythonPath) {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { $pythonPath = $python.Source }
}

if (-not $pythonPath -or -not (Test-Path $pythonPath)) {
    Write-Error "Python not found on PATH. Install Python 3.10+ from python.org (tick 'Add to PATH'), then re-run."
    exit 1
}

Write-Host "Python:  $pythonPath"
Write-Host "Script:  $scriptPath"
Write-Host "Runs at: $At daily"
Write-Host ""

$action   = New-ScheduledTaskAction -Execute $pythonPath -Argument "`"$scriptPath`"" -WorkingDirectory $repoDir
$trigger  = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Task '$TaskName' registered."
Write-Host ""
Write-Host "Test it right now with:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "Remove it later with:"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
