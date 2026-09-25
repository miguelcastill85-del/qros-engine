# Run locally ON THE DATA-HOST PC. Zero subscription cost; current user only.
# Daily 22:00 local and at interactive user logon; never assumes ChatGPT is a daemon.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$RepoDir,
 [Parameter(Mandatory=$true)][string]$Queue,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{64}$')][string]$QueueSha256,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f]{40}$')][string]$LivePointerSha1,
 [string]$PointerPath='control/QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF.json',
 [string]$PythonExe='python.exe',
 [string]$TaskName='QROS_AntiStall_V24',
 [switch]$ReplacePreviouslyFrozenTask,
 [switch]$RunNow
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path -LiteralPath $RepoDir).Path
$queuePath=(Resolve-Path -LiteralPath $Queue).Path
$python=(Get-Command $PythonExe -ErrorAction Stop).Source
$service=Join-Path $repo 'anti_stall\scripts\qros_continuation_service_v2_4.py'
$hostScript=Join-Path $repo 'anti_stall\hosts\run_windows_task_v2_4.ps1'
foreach($p in @($service,$hostScript)) { if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing host executable: $p" } }
if ($QueueSha256 -cne (Get-FileHash -LiteralPath $queuePath -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'FROZEN_QUEUE_SHA256_INVALID' }
if ($PointerPath -notmatch '^[a-zA-Z0-9_.\-/]+$' -or $PointerPath -match '(^|/)\.\.(/|$)') { throw 'UNSAFE_POINTER_PATH' }
$existing=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing -and -not $ReplacePreviouslyFrozenTask) { throw 'Existing scheduled task requires explicit -ReplacePreviouslyFrozenTask' }
$config=Join-Path $repo '.qros_v24_windows_frozen_runner.json'
$data=[ordered]@{repo_dir=$repo;python_exe=$python;queue=$queuePath;queue_sha256=$QueueSha256;pointer_path=$PointerPath;pointer_sha1=$LivePointerSha1}
$json=$data|ConvertTo-Json -Compress
if (Test-Path -LiteralPath $config) {
  if (-not $ReplacePreviouslyFrozenTask) { throw 'A frozen task config already exists; explicit -ReplacePreviouslyFrozenTask required to change it' }
}
$tmp=$config+'.tmp'
[System.IO.File]::WriteAllText($tmp,$json,[System.Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $tmp -Destination $config -Force
# Enforce current-user, interactive task; S4U would lose remote git credentials.
$user=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$action=New-ScheduledTaskAction -Execute (Join-Path $PSHOME 'powershell.exe') -Argument ('-NoProfile -File "' + $hostScript + '" -Config "' + $config + '"') -WorkingDirectory $repo
$triggers=@((New-ScheduledTaskTrigger -Daily -At '22:00'),(New-ScheduledTaskTrigger -AtLogOn -User $user))
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 7) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "INSTALLED task=$TaskName user=$user daily=22:00+logon; live remote proof checked at every execution; config=$config"
if ($RunNow) { Start-ScheduledTask -TaskName $TaskName; Write-Output 'STARTED_LOCAL_TASK_CHECK_WINDOWS_TASK_SCHEDULER_AND_FROZEN_LOGS' }
