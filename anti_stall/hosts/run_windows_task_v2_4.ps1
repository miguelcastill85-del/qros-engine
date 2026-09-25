# QROS v2.4 task host: runs real local frozen subprocess work, never approves science.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Config)
$ErrorActionPreference='Stop'
$configPath=(Resolve-Path -LiteralPath $Config).Path
$c=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
foreach($key in @('repo_dir','python_exe','queue','queue_sha256','pointer_path','pointer_sha1')) {
    if ([string]::IsNullOrWhiteSpace($c.$key)) { throw "Missing frozen config field: $key" }
}
if ($c.queue_sha256 -notmatch '^[0-9a-f]{64}$' -or $c.pointer_sha1 -notmatch '^[0-9a-f]{40}$') { throw 'Invalid external hash pin' }
$repo=(Resolve-Path -LiteralPath $c.repo_dir).Path
$queue=(Resolve-Path -LiteralPath $c.queue).Path
$sha=(Get-FileHash -LiteralPath $queue -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sha -cne $c.queue_sha256) { throw 'Frozen queue SHA-256 drift; no worker started' }
$service=Join-Path $repo 'anti_stall\scripts\qros_continuation_service_v2_4.py'
if (-not (Test-Path -LiteralPath $service -PathType Leaf)) { throw 'v2.4 service not installed' }
$logDir=Join-Path (Split-Path -Parent $queue) 'QROS_V24_SCHEDULED_LOGS'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log=Join-Path $logDir (('QROS_V24_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.log'))
$argv=@($service,'--queue',$queue,'--expected-queue-sha256',$c.queue_sha256,
        '--git-dir',$repo,'--pointer-path',$c.pointer_path,
        '--expected-live-pointer-sha1',$c.pointer_sha1,
        '--max-cycles','20','--wall-seconds','21600','--cycle-seconds','180','--stages-per-cycle','5')
"QROS v2.4 starting $(Get-Date -Format o); logfile=$log" | Tee-Object -FilePath $log
& $c.python_exe @argv 2>&1 | Tee-Object -FilePath $log -Append
$code=$LASTEXITCODE
"QROS v2.4 exit=$code $(Get-Date -Format o)" | Tee-Object -FilePath $log -Append
exit $code
