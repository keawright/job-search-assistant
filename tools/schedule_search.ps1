param([string]$TaskName = 'JobSearchAssistantMorning', [string]$At = '09:00')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$scriptPath = Join-Path $projectRoot 'tools\daily_search.py'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project virtual environment is missing.' }
# Do not replace another task or store a password. Run only as the signed-in user.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task $TaskName already exists. Inspect it before making changes."
}
$taskAction = New-ScheduledTaskAction -Execute $pythonPath -Argument ('"' + $scriptPath + '"') -WorkingDirectory $projectRoot
$taskTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $At
$taskSettings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Principal $taskPrincipal -Description 'Private job discovery; weekday mornings; no application submissions or workbook edits.'
