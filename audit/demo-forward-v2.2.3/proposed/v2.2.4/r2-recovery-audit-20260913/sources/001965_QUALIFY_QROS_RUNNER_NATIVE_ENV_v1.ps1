Set-StrictMode -Version 3.0
$ErrorActionPreference='Stop'

$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$Schema='QROS_RUNNER_NATIVE_ENV_QUALIFICATION_1.0'
$RunId=('r2_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'_'+([Guid]::NewGuid().ToString('N').Substring(0,8)))
$OutRoot='C:\QROS_RUNNER_NATIVE_ENV_QUALIFIER_v1'
$Ev=Join-Path $OutRoot $RunId
$Logs=Join-Path $Ev 'logs'
$EvidenceZip=Join-Path $OutRoot ('QROS_RUNNER_NATIVE_ENV_EVIDENCE_'+$RunId+'.zip')
$DarwinexInstall='C:\Program Files\Darwinex MetaTrader 5'
$ActiveDataPath='C:\Users\makk7\AppData\Roaming\MetaQuotes\Terminal\6C3C6A11D1C3791DD4DBF45421BF8028'
$TerminalRoot=Split-Path -Parent $ActiveDataPath
$Common=Join-Path $TerminalRoot 'Common\Files'
$IsoA=('C:\QROS_MT5_R2_'+$RunId+'_A')
$IsoB=('C:\QROS_MT5_R2_'+$RunId+'_B')
$ExpectedRunnerSha='17be652ebb5c3745590ceae798a02d136285a2c8dc1c3645f2be578dfa8d8375'
$ExpectedHarnessSha='PENDING_BUILD'
$Log=Join-Path $Ev 'R2_QUALIFIER.log'
$script:ExitCode=99
$script:Success=$false

New-Item -ItemType Directory -Force -Path $Ev,$Logs|Out-Null

function Write-Q([string]$m){
  $s="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $m"
  Write-Host $s
  Add-Content -LiteralPath $Log -Value $s -Encoding UTF8
}
function Sha([string]$p){return (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function Fail([string]$m,[int]$code){$e=New-Object System.Exception($m);$e.Data['QROS_CODE']=$code;throw $e}
function SafeIsoPath([string]$p){
  if([string]::IsNullOrWhiteSpace($p)){return $false}
  $full=[System.IO.Path]::GetFullPath($p)
  return ($full.StartsWith('C:\QROS_MT5_R2_',[System.StringComparison]::OrdinalIgnoreCase))
}
function Copy-Tree([string]$src,[string]$dst){
  New-Item -ItemType Directory -Force -Path $dst|Out-Null
  & robocopy.exe $src $dst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  $rc=$LASTEXITCODE
  if($rc -ge 8){Fail ('ROBOCOPY_'+$rc+'_'+$src) 22}
}
function Stop-IsolatedProcess($p,[string]$iso){
  if($null -eq $p){return}
  if(!(SafeIsoPath $iso)){Fail 'STOP_PROCESS_ISO_GUARD_REJECTED' 23}
  try{
    $p.Refresh()
    if(!$p.HasExited){
      if([string]::IsNullOrWhiteSpace($p.Path) -or !($p.Path -like "$iso*")){Fail 'STOP_PROCESS_PATH_GUARD_REJECTED' 23}
      Stop-Process -Id $p.Id -Force -ErrorAction Stop
      try{Wait-Process -Id $p.Id -Timeout 15 -ErrorAction SilentlyContinue}catch{}
    }
  }catch [System.InvalidOperationException]{}
}
function Recreate-Iso([string]$iso){
  if(!(SafeIsoPath $iso)){Fail 'ISOLATION_PATH_GUARD_FAILED' 20}
  $stale=@(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object {try{$_.Path -like "$iso*"}catch{$false}})
  if(@($stale).Count -gt 0){Fail ('STALE_ISOLATED_TERMINAL_RUNNING_'+$iso) 21}
  if(Test-Path $iso){Remove-Item -LiteralPath $iso -Recurse -Force}
  New-Item -ItemType Directory -Force -Path $iso|Out-Null
  Copy-Tree $DarwinexInstall $iso
  Copy-Tree (Join-Path $ActiveDataPath 'config') (Join-Path $iso 'config')
  New-Item -ItemType Directory -Force -Path (Join-Path $iso 'MQL5\Experts'),(Join-Path $iso 'MQL5\Include'),(Join-Path $iso 'MQL5\Profiles\Tester')|Out-Null
  Copy-Tree (Join-Path $ActiveDataPath 'MQL5\Include') (Join-Path $iso 'MQL5\Include')
  Copy-Item -LiteralPath (Join-Path $Here 'MQL5\Experts\QROS_RUNNER_ENV_QUALIFIER_v1.mq5') -Destination (Join-Path $iso 'MQL5\Experts') -Force
}
function Read-ExclusiveText([string]$file,[int]$retryMs=15000){
  $deadline=[DateTime]::UtcNow.AddMilliseconds($retryMs)
  do{
    if(Test-Path $file){
      $fs=$null
      try{
        $fs=[System.IO.File]::Open($file,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::None)
        $len=[int]$fs.Length;$bytes=New-Object byte[] $len;$off=0
        while($off -lt $len){$n=$fs.Read($bytes,$off,$len-$off);if($n -le 0){break};$off+=$n}
        if($off -ne $len){throw 'SHORT_READ'}
        return [System.Text.Encoding]::UTF8.GetString($bytes)
      }catch [System.IO.IOException]{} finally {if($null -ne $fs){try{$fs.Dispose()}catch{}}}
    }
    Start-Sleep -Milliseconds 125
  }while([DateTime]::UtcNow -lt $deadline)
  return $null
}
function Read-CsvRows([string]$file,[int]$retryMs=15000){
  $text=Read-ExclusiveText $file $retryMs
  if($null -eq $text){return @()}
  try{return @($text | ConvertFrom-Csv)}catch{return @()}
}
function Copy-Exclusive([string]$src,[string]$dst,[int]$retryMs=15000){
  $deadline=[DateTime]::UtcNow.AddMilliseconds($retryMs)
  do{
    if(Test-Path $src){
      $s=$null;$d=$null
      try{
        $s=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::None)
        $d=[System.IO.File]::Open($dst,[System.IO.FileMode]::Create,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
        $s.CopyTo($d);$d.Flush();return $true
      }catch [System.IO.IOException]{} finally {if($null -ne $d){try{$d.Dispose()}catch{}};if($null -ne $s){try{$s.Dispose()}catch{}}}
    }
    Start-Sleep -Milliseconds 125
  }while([DateTime]::UtcNow -lt $deadline)
  return $false
}
function Wait-Exclusive([string]$file,[int]$seconds=30){return ($null -ne (Read-ExclusiveText $file ($seconds*1000)))}
function Read-ResultStatus([string]$file,[string]$id,[int]$retryMs=15000){
  $rows=@(Read-CsvRows $file $retryMs)
  foreach($r in $rows){if([string]$r.test_id -eq $id){return [string]$r.status}}
  return 'MISSING'
}
function Read-FirstRow([string]$file,[int]$retryMs=15000){
  $rows=@(Read-CsvRows $file $retryMs)
  foreach($r in $rows){return $r}
  return $null
}
function Make-Set([string]$iso,[string]$name,[int]$mode,[string]$prefix,[int]$holdMs,[long]$expectedToken){
  $p=Join-Path $iso ('MQL5\Profiles\Tester\'+$name+'.set')
  @("InpMode=$mode","InpPrefix=$prefix","InpHoldMs=$holdMs","InpExpectedToken=$expectedToken") | Set-Content -LiteralPath $p -Encoding ASCII
  return $name+'.set'
}
function Make-Ini([string]$name,[string]$set,[string]$fromDate='2026.09.08',[string]$toDate='2026.09.09'){
  $ini=Join-Path $Ev ($name+'.ini')
  @"
[Experts]
AllowLiveTrading=0
AllowDllImport=0

[Tester]
Expert=QROS_RUNNER_ENV_QUALIFIER_v1
ExpertParameters=$set
Symbol=XAUUSD
Period=M1
Model=4
ExecutionMode=0
Optimization=0
FromDate=$fromDate
ToDate=$toDate
ForwardMode=0
Deposit=1000000
Currency=USD
Leverage=100
ShutdownTerminal=1
UseLocal=1
UseRemote=0
UseCloud=0
"@ | Set-Content -LiteralPath $ini -Encoding ASCII
  $raw=Get-Content -LiteralPath $ini -Raw
  if($raw -notmatch 'AllowLiveTrading=0' -or $raw -notmatch 'UseRemote=0' -or $raw -notmatch 'UseCloud=0'){Fail ('INI_SAFETY_CONTRACT_'+$name) 26}
  return $ini
}
function Start-TesterProcess([string]$iso,[string]$name,[string]$set){
  if(!(SafeIsoPath $iso)){Fail 'START_TESTER_ISO_GUARD' 27}
  $terminal=Join-Path $iso 'terminal64.exe';if(!(Test-Path $terminal)){Fail 'ISOLATED_TERMINAL_MISSING' 27}
  $ini=Make-Ini $name $set
  return Start-Process -FilePath $terminal -ArgumentList @('/portable',("/config:`"$ini`"")) -PassThru
}
function Run-Tester([string]$iso,[string]$name,[string]$set,[int]$timeoutSec=900){
  Write-Q ('TESTER START '+$name)
  $p=Start-TesterProcess $iso $name $set
  $done=$true
  try{Wait-Process -Id $p.Id -Timeout $timeoutSec -ErrorAction Stop}catch{$done=$false}
  if(!$done){Stop-IsolatedProcess $p $iso;Fail ('ISOLATED_TESTER_TIMEOUT_'+$name) 40}
  try{$p.Refresh()}catch{}
  Write-Q ('TESTER END '+$name+' exit='+$p.ExitCode)
  return $p.ExitCode
}
function Zip-Evidence(){
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  if(Test-Path $EvidenceZip){Remove-Item -LiteralPath $EvidenceZip -Force}
  [System.IO.Compression.ZipFile]::CreateFromDirectory($Ev,$EvidenceZip,[System.IO.Compression.CompressionLevel]::Optimal,$false)
  return $EvidenceZip
}
function Snapshot-Processes([string]$name){
  $rows=New-Object System.Collections.Generic.List[object]
  foreach($p in @(Get-Process terminal64 -ErrorAction SilentlyContinue)){
    $path='';try{$path=$p.Path}catch{}
    $rows.Add([pscustomobject]@{id=$p.Id;path=$path;start=$(try{$p.StartTime.ToUniversalTime().ToString('o')}catch{''})})
  }
  $rows | Export-Csv -LiteralPath (Join-Path $Ev $name) -NoTypeInformation -Encoding UTF8
}
function Runner-SelfTest(){
  $rows=New-Object System.Collections.Generic.List[object]
  function C([string]$id,[bool]$pass,[string]$detail){$rows.Add([pscustomobject]@{id=$id;status=$(if($pass){'PASS'}else{'FAIL'});detail=$detail});if(!$pass){Fail ('R2_SELFTEST_'+$id) 15}}
  C 'S01_PS_MAJOR' ($PSVersionTable.PSVersion.Major -ge 5) ($PSVersionTable.PSVersion.ToString())
  $o='{"files":{"a":1,"b":2}}'|ConvertFrom-Json;$n=0;foreach($x in $o.files.PSObject.Properties){$n++};C 'S02_PSOBJECT_ENUM' ($n -eq 2) ('n='+$n)
  $one=@('x');C 'S03_ARRAY_CARDINALITY' (@($one).Count -eq 1) 'explicit @() cardinality'
  C 'S04_ACTIVE_PATH_REJECTED' (!(SafeIsoPath $ActiveDataPath)) $ActiveDataPath
  C 'S05_INSTALL_PATH_REJECTED' (!(SafeIsoPath $DarwinexInstall)) $DarwinexInstall
  C 'S06_ISOA_ACCEPTED' (SafeIsoPath $IsoA) $IsoA
  C 'S07_ISOB_ACCEPTED' (SafeIsoPath $IsoB) $IsoB
  $lp=Join-Path $Ev 'SELFTEST_LOCK.bin';$a=$null;$blocked=$false
  try{$a=[System.IO.File]::Open($lp,[System.IO.FileMode]::Create,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None);try{$b=[System.IO.File]::Open($lp,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::None);$b.Dispose()}catch [System.IO.IOException]{$blocked=$true}}finally{if($null -ne $a){$a.Dispose()}}
  C 'S08_FILESHARE_NONE_BLOCKS' $blocked 'second open denied while writer owns file'
  $text=Read-ExclusiveText $lp 1000;C 'S09_FILE_READ_AFTER_CLOSE' ($null -ne $text) 'exclusive read after close'
  $tmp=Join-Path $Ev 'ATOMIC.tmp';$fin=Join-Path $Ev 'ATOMIC.final';Set-Content -LiteralPath $tmp -Value 'ok' -Encoding ASCII;Move-Item -LiteralPath $tmp -Destination $fin -Force;C 'S10_ATOMIC_RENAME' (Test-Path $fin) 'local evidence rename'
  $tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::ParseFile($MyInvocation.ScriptName,[ref]$tokens,[ref]$errors)|Out-Null;C 'S11_AST_PARSE' (@($errors).Count -eq 0) ('errors='+@($errors).Count)
  $sw=[System.Diagnostics.Stopwatch]::StartNew();while($sw.ElapsedMilliseconds -lt 250){};$sw.Stop();C 'S12_WALLCLOCK' ($sw.ElapsedMilliseconds -ge 200) ('ms='+$sw.ElapsedMilliseconds)
  $deadline=[DateTime]::UtcNow.AddMilliseconds(250);while([DateTime]::UtcNow -lt $deadline){};C 'S13_TIMEOUT_PRIMITIVE' ([DateTime]::UtcNow -ge $deadline) 'deadline reached fail-closed primitive'
  $rows | Export-Csv -LiteralPath (Join-Path $Ev 'RUNNER_SELFTEST.csv') -NoTypeInformation -Encoding UTF8
}

try{
  Write-Q ('START QROS Runner Native Environment Qualifier run_id='+$RunId)
  Write-Q 'SAFETY: no Candidate3 execution, AllowLiveTrading=0, no broker orders, no active terminal control.'
  Snapshot-Processes 'ACTIVE_TERMINALS_BEFORE.csv'
  Runner-SelfTest

  $TerminalSrc=Join-Path $DarwinexInstall 'terminal64.exe';$MetaSrc=Join-Path $DarwinexInstall 'metaeditor64.exe'
  if(!(Test-Path $TerminalSrc)){Fail 'DARWINEX_TERMINAL_NOT_FOUND' 10}
  if(!(Test-Path $MetaSrc)){Fail 'DARWINEX_METAEDITOR_NOT_FOUND' 11}
  if(!(Test-Path $ActiveDataPath)){Fail 'ACTIVE_DATA_PATH_NOT_FOUND' 12}
  if(!(Test-Path (Join-Path $ActiveDataPath 'config'))){Fail 'ACTIVE_CONFIG_NOT_FOUND' 13}
  $ActiveInclude=Join-Path $ActiveDataPath 'MQL5\Include';if(!(Test-Path (Join-Path $ActiveInclude 'Trade\Trade.mqh'))){Fail 'STANDARD_TRADE_INCLUDE_NOT_FOUND' 18}

  $ManifestPath=Join-Path $Here 'PACKAGE_MANIFEST_SHA256.json';if(!(Test-Path $ManifestPath)){Fail 'PACKAGE_MANIFEST_MISSING' 14}
  $Pm=Get-Content -LiteralPath $ManifestPath -Raw|ConvertFrom-Json;$mc=0
  foreach($prop in $Pm.files.PSObject.Properties){$mc++;$rel=[string]$prop.Name;$meta=$prop.Value;$fp=Join-Path $Here $rel;if(!(Test-Path $fp)){Fail ('MANIFEST_FILE_MISSING_'+$rel) 14};if((Sha $fp) -ne [string]$meta.sha256){Fail ('MANIFEST_HASH_MISMATCH_'+$rel) 15};if((Get-Item -LiteralPath $fp).Length -ne [long]$meta.bytes){Fail ('MANIFEST_SIZE_MISMATCH_'+$rel) 15}}
  Write-Q ('PACKAGE MANIFEST PASS entries='+$mc)

  $ruq=Join-Path $Here 'RUNNER_UNDER_QUALIFICATION.ps1';if((Sha $ruq) -ne $ExpectedRunnerSha){Fail 'RUNNER_UNDER_QUALIFICATION_SHA_MISMATCH' 16}
  Write-Q ('R1 BOUND RUNNER SHA PASS '+$ExpectedRunnerSha)

  Recreate-Iso $IsoA;Recreate-Iso $IsoB
  Copy-Item -LiteralPath (Join-Path $Here 'MQL5\Experts\QROS_RUNNER_ENV_QUALIFIER_v1.mq5') -Destination (Join-Path $IsoB 'MQL5\Experts') -Force

  $incCsv=Join-Path $Ev 'STANDARD_INCLUDE_SNAPSHOT_SHA256.csv';$incRows=New-Object System.Collections.Generic.List[object];$incCount=0
  foreach($f in @(Get-ChildItem -LiteralPath (Join-Path $IsoA 'MQL5\Include') -File -Recurse)){$incCount++;$incRows.Add([pscustomobject]@{rel=$f.FullName.Substring((Join-Path $IsoA 'MQL5\Include').Length).TrimStart('\');bytes=$f.Length;sha256=(Sha $f.FullName)})}
  $incRows|Export-Csv -LiteralPath $incCsv -NoTypeInformation -Encoding UTF8
  $tradeSha=Sha (Join-Path $IsoA 'MQL5\Include\Trade\Trade.mqh')
  Write-Q ('STANDARD INCLUDE SNAPSHOT PASS files='+$incCount+' Trade.mqh='+$tradeSha)

  $MetaA=Join-Path $IsoA 'metaeditor64.exe';$src=Join-Path $IsoA 'MQL5\Experts\QROS_RUNNER_ENV_QUALIFIER_v1.mq5';$cl=Join-Path $Logs 'QROS_RUNNER_ENV_QUALIFIER_v1.mq5.log'
  $cp=Start-Process -FilePath $MetaA -ArgumentList @('/portable',("/compile:`"$src`""),("/log:`"$cl`"")) -Wait -PassThru
  if(!(Test-Path $cl)){Fail 'COMPILE_LOG_MISSING' 30};$ct=Get-Content -LiteralPath $cl -Raw;if($ct -notmatch 'Result:\s*0 errors,\s*0 warnings'){Fail 'COMPILE_NOT_0_0' 31}
  $ex5=[System.IO.Path]::ChangeExtension($src,'.ex5');if(!(Test-Path $ex5)){Fail 'QUALIFIER_EX5_MISSING' 32};Copy-Item -LiteralPath $ex5 -Destination (Join-Path $IsoB 'MQL5\Experts\QROS_RUNNER_ENV_QUALIFIER_v1.ex5') -Force
  Write-Q ('METAEDITOR COMPILE PASS 0/0 ex5='+$(Sha $ex5))

  # Native no-trading materialization smoke
  $smokePrefix=('QROS_R2_'+$RunId+'_SMOKE');$smokeSet=Make-Set $IsoA 'R2_SMOKE' 1 $smokePrefix 0 0;[void](Run-Tester $IsoA 'R2_SMOKE' $smokeSet 900)
  $smokeFile=Join-Path $Common ($smokePrefix+'_RESULTS.csv');if((Read-ResultStatus $smokeFile 'R2_MQL_SMOKE' 30000) -ne 'PASS'){Fail 'NATIVE_MQL_SMOKE_FAIL' 33};if(!(Copy-Exclusive $smokeFile (Join-Path $Ev 'R2_SMOKE_RESULTS.csv') 10000)){Fail 'SMOKE_SNAPSHOT_FAIL' 34}
  $smrow=Read-FirstRow $smokeFile 5000;if($null -eq $smrow -or [int]$smrow.mql_tester -ne 1){Fail 'SMOKE_NOT_STRATEGY_TESTER' 35};$mt5Build=[int]$smrow.terminal_build
  Write-Q ('NATIVE MQL MATERIALIZATION PASS build='+$mt5Build)

  # Two-process fencing with real wall-clock overlap
  $fencePrefix=('QROS_R2_'+$RunId+'_FENCE');$holderSet=Make-Set $IsoA 'R2_HOLDER' 2 $fencePrefix 180000 0;$probeSet=Make-Set $IsoB 'R2_PROBE' 3 $fencePrefix 0 0
  $holder=Start-TesterProcess $IsoA 'R2_HOLDER' $holderSet
  $ready=Join-Path $Common ($fencePrefix+'_HOLDER_READY.csv');if(!(Wait-Exclusive $ready 120)){Stop-IsolatedProcess $holder $IsoA;Fail 'FENCE_HOLDER_READY_TIMEOUT' 50}
  $rdy=Read-FirstRow $ready 5000;if($null -eq $rdy -or [int]$rdy.ok -ne 1){Stop-IsolatedProcess $holder $IsoA;Fail 'FENCE_HOLDER_READY_INVALID' 51}
  [void](Run-Tester $IsoB 'R2_PROBE' $probeSet 900)
  $probe=Join-Path $Common ($fencePrefix+'_RESULTS.csv');if((Read-ResultStatus $probe 'R2_FENCE_PROBE' 15000) -ne 'PASS'){Stop-IsolatedProcess $holder $IsoA;Fail 'FENCE_SECOND_EXECUTOR_NOT_DENIED' 52}
  $holderDone=$true;try{Wait-Process -Id $holder.Id -Timeout 260 -ErrorAction Stop}catch{$holderDone=$false}
  if(!$holderDone){Stop-IsolatedProcess $holder $IsoA;Fail 'FENCE_HOLDER_RELEASE_TIMEOUT' 53}
  $released=Join-Path $Common ($fencePrefix+'_RELEASED.csv');if(!(Wait-Exclusive $released 30)){Fail 'FENCE_RELEASE_MARKER_MISSING' 54}
  $rel=Read-FirstRow $released 5000;if($null -eq $rel -or [long]$rel.token -ne [long]$rdy.token){Fail 'FENCE_RELEASE_TOKEN_MISMATCH' 55}
  $reSet=Make-Set $IsoB 'R2_REACQUIRE' 4 $fencePrefix 0 0;[void](Run-Tester $IsoB 'R2_REACQUIRE' $reSet 900);if((Read-ResultStatus $probe 'R2_FENCE_REACQUIRE' 15000) -ne 'PASS'){Fail 'FENCE_REACQUIRE_FAIL' 56}
  foreach($f in @($ready,$released,$probe)){if(Test-Path $f){[void](Copy-Exclusive $f (Join-Path $Ev ([System.IO.Path]::GetFileName($f))) 10000)}}
  Write-Q 'FENCING PASS second executor denied, release token matched, reacquire passed'

  # Cross-process restart/persistence synthetic state
  $restartPrefix=('QROS_R2_'+$RunId+'_RESTART');$wset=Make-Set $IsoA 'R2_RESTART_WRITE' 5 $restartPrefix 0 0;[void](Run-Tester $IsoA 'R2_RESTART_WRITE' $wset 900)
  $stateTokenFile=Join-Path $Common ($restartPrefix+'_STATE_TOKEN.csv');$tr=Read-FirstRow $stateTokenFile 15000;if($null -eq $tr -or [int]$tr.ok -ne 1){Fail 'RESTART_WRITE_TOKEN_MISSING' 60};$token=[long]$tr.token
  $rset=Make-Set $IsoA 'R2_RESTART_READ' 6 $restartPrefix 0 $token;[void](Run-Tester $IsoA 'R2_RESTART_READ' $rset 900)
  $restartResults=Join-Path $Common ($restartPrefix+'_RESULTS.csv');if((Read-ResultStatus $restartResults 'R2_RESTART_READ' 15000) -ne 'PASS'){Fail 'RESTART_READ_FAIL' 61}
  foreach($f in @($stateTokenFile,$restartResults,(Join-Path $Common ($restartPrefix+'_STATE.csv')))){if(Test-Path $f){[void](Copy-Exclusive $f (Join-Path $Ev ([System.IO.Path]::GetFileName($f))) 10000)}}
  Write-Q 'RESTART/PERSISTENCE PASS across separate tester processes'

  Snapshot-Processes 'ACTIVE_TERMINALS_AFTER.csv'
  $includeSnapshotSha=Sha $incCsv
  $fingerprint=[ordered]@{runner_sha256=$ExpectedRunnerSha;qualifier_ps1_sha256=(Sha $MyInvocation.MyCommand.Path);qualifier_mq5_sha256=(Sha (Join-Path $Here 'MQL5\Experts\QROS_RUNNER_ENV_QUALIFIER_v1.mq5'));terminal64_sha256=(Sha $TerminalSrc);metaeditor64_sha256=(Sha $MetaSrc);terminal_build=$mt5Build;powershell=$PSVersionTable.PSVersion.ToString();trade_mqh_sha256=$tradeSha;include_snapshot_sha256=$includeSnapshotSha;iso_a=$IsoA;iso_b=$IsoB;active_data_path=$ActiveDataPath}
  $fingerprint|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $Ev 'R3_ENVIRONMENT_FINGERPRINT.json') -Encoding UTF8
  $receipt=[ordered]@{schema=$Schema;utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;decision='PASS';state='NATIVE_ENV_QUALIFIED';runner_under_qualification_sha256=$ExpectedRunnerSha;fingerprint=$fingerprint;checks=[ordered]@{runner_selftest='13/13 PASS';manifest='PASS';standard_include_snapshot='PASS';metaeditor_compile='0 errors / 0 warnings';strategy_tester_smoke='PASS_NO_TRADING';fencing='PASS_SECOND_DENIED_RELEASE_REACQUIRE';restart_persistence='PASS'};real_broker_orders_authorized=$false;real_broker_orders_sent=0;active_terminal_control_actions=0;active_data_write_actions=0;candidate_execution_allowed=$true;candidate_execution_performed=$false;deployment_allowed=$false;cert_arm_allowed=$false;v223_cert_rule='KEEP_QDB1_EXEC_CERT_0'}
  $receipt|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $Ev 'RUNNER_NATIVE_QUALIFICATION_RECEIPT.json') -Encoding UTF8
  $z=Zip-Evidence;$zsha=Sha $z;$script:Success=$true;$script:ExitCode=0
  Write-Host '';Write-Host '============================================================';Write-Host 'QROS RUNNER R2: NATIVE_ENV_QUALIFIED';Write-Host ('Evidence: '+$z);Write-Host ('SHA-256: '+$zsha);Write-Host 'No Candidate3 was executed. No real broker orders. Keep QDB1.EXEC.CERT=0.';Write-Host '============================================================'
}catch{
  $reason=$_.Exception.Message;$code=99;try{if($_.Exception.Data.Contains('QROS_CODE')){$code=[int]$_.Exception.Data['QROS_CODE']}}catch{}
  try{Write-Q ('FAIL '+$reason+' code='+$code)}catch{}
  try{Snapshot-Processes 'ACTIVE_TERMINALS_AFTER_FAIL.csv'}catch{}
  $fr=[ordered]@{schema=$Schema;utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;decision='FAIL';state='RUNNER_REJECTED_NATIVE_ENV';reason=$reason;code=$code;real_broker_orders_authorized=$false;real_broker_orders_sent=0;candidate_execution_allowed=$false;candidate_execution_performed=$false;deployment_allowed=$false;cert_arm_allowed=$false;v223_cert_rule='KEEP_QDB1_EXEC_CERT_0'}
  try{$fr|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $Ev 'RUNNER_NATIVE_QUALIFICATION_RECEIPT.json') -Encoding UTF8}catch{}
  $z=$null;try{$z=Zip-Evidence}catch{};if($z){try{Write-Host ('Evidence: '+$z);Write-Host ('SHA-256: '+(Sha $z))}catch{}}
  $script:ExitCode=$code
}
exit $script:ExitCode
