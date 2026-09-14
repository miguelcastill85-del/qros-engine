param(
 [string]$DarwinexInstall="C:\Program Files\Darwinex MetaTrader 5",
 [string]$ActiveDataPath="C:\Users\makk7\AppData\Roaming\MetaQuotes\Terminal\6C3C6A11D1C3791DD4DBF45421BF8028"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version 3.0
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$RunId=(Get-Date -Format 'yyyyMMdd_HHmmss')+"_"+([guid]::NewGuid().ToString('N').Substring(0,8))
$OutRoot="C:\QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v2"
$Out=Join-Path $OutRoot $RunId
$Ev=Join-Path $Out "EVIDENCE"
$Logs=Join-Path $Ev "LOGS"
$IsoA="C:\QROS_MT5_R2T_${RunId}_A"
$IsoB="C:\QROS_MT5_R2T_${RunId}_B"
$Prefix="QROS_R2T_"+$RunId
$EvidenceZip=Join-Path $OutRoot ("QROS_RUNNER_RUNTIME_FENCE_EVIDENCE_"+$RunId+".zip")
New-Item -ItemType Directory -Force -Path $OutRoot,$Out,$Ev,$Logs | Out-Null
$Log=Join-Path $Ev "R2T_QUALIFIER.log"

function Write-Q([string]$m){$s="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $m";Write-Host $s;Add-Content -LiteralPath $Log -Value $s -Encoding UTF8}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function Fail([string]$r,[int]$c){$e=New-Object System.Exception($r);$e.Data["QROS_CODE"]=$c;throw $e}
function Canon([string]$p){
 if([string]::IsNullOrWhiteSpace($p)){return $null}
 return [IO.Path]::GetFullPath($p).TrimEnd([char[]]@('\','/'))
}
function SafeIso([string]$p){
 $f=Canon $p
 if($null -eq $f){return $false}
 $a=Canon $IsoA;$b=Canon $IsoB
 return ($f.Equals($a,[StringComparison]::OrdinalIgnoreCase) -or $f.Equals($b,[StringComparison]::OrdinalIgnoreCase))
}
function Is-UnderIso([string]$path,[string]$iso){
 if([string]::IsNullOrWhiteSpace($path) -or !(SafeIso $iso)){return $false}
 $p=Canon $path;$root=(Canon $iso)+[IO.Path]::DirectorySeparatorChar
 return $p.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)
}
function Get-IsoTerminalProcesses([string]$iso){
 if(!(SafeIso $iso)){Fail 'ISO_PROCESS_ENUM_PATH_GUARD' 24}
 $rows=@()
 foreach($p in @(Get-Process terminal64 -ErrorAction SilentlyContinue)){
  try{
   $pp=[string]$p.Path
   if(Is-UnderIso $pp $iso){
    $rows += [pscustomobject]@{pid=[int]$p.Id;path=$pp}
   }
  }catch{}
 }
 return $rows
}
function Wait-IsoTerminal([string]$iso,[int]$ms=15000){
 $dl=[DateTime]::UtcNow.AddMilliseconds($ms)
 do{
  $rows=@(Get-IsoTerminalProcesses $iso)
  if(@($rows).Count -gt 0){return @($rows)}
  Start-Sleep -Milliseconds 125
 }while([DateTime]::UtcNow -lt $dl)
 return @()
}
function Assert-IsoStopped([string]$iso,[int]$ms=20000,[bool]$ThrowOnFail=$true){
 $dl=[DateTime]::UtcNow.AddMilliseconds($ms)
 do{
  $rows=@(Get-IsoTerminalProcesses $iso)
  if(@($rows).Count -eq 0){return $true}
  Start-Sleep -Milliseconds 125
 }while([DateTime]::UtcNow -lt $dl)
 if($ThrowOnFail){Fail ('ISO_TERMINAL_STILL_RUNNING_'+$iso) 25}
 return $false
}
function Stop-IsoTerminals([string]$iso,[bool]$ThrowOnFail=$true){
 if(!(SafeIso $iso)){if($ThrowOnFail){Fail 'STOP_ISO_PATH_GUARD' 26};return $false}
 foreach($r in @(Get-IsoTerminalProcesses $iso)){
  if(!(Is-UnderIso ([string]$r.path) $iso)){if($ThrowOnFail){Fail 'STOP_PROCESS_PATH_MISMATCH' 27};continue}
  try{Stop-Process -Id ([int]$r.pid) -Force -ErrorAction Stop}catch{if($ThrowOnFail){throw}}
 }
 return (Assert-IsoStopped $iso 20000 $ThrowOnFail)
}
function Cleanup(){
 try{[void](Stop-IsoTerminals $IsoA $false)}catch{}
 try{[void](Stop-IsoTerminals $IsoB $false)}catch{}
}
function Copy-Tree([string]$s,[string]$d){
 New-Item -ItemType Directory -Force -Path $d|Out-Null
 & robocopy.exe $s $d /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
 if($LASTEXITCODE -ge 8){Fail ("ROBOCOPY_"+$LASTEXITCODE) 20}
}
function Recreate-Iso([string]$iso){
 if(!(SafeIso $iso)){Fail 'ISO_PATH_GUARD' 21}
 $stale=@(Get-IsoTerminalProcesses $iso)
 if(@($stale).Count -gt 0){Fail 'STALE_ISO_PROCESS' 22}
 if(Test-Path $iso){Remove-Item -LiteralPath $iso -Recurse -Force}
 New-Item -ItemType Directory -Force -Path $iso|Out-Null
 Copy-Tree $DarwinexInstall $iso
 Copy-Tree (Join-Path $ActiveDataPath 'config') (Join-Path $iso 'config')
 New-Item -ItemType Directory -Force -Path (Join-Path $iso 'MQL5\Experts'),(Join-Path $iso 'MQL5\Presets'),(Join-Path $iso 'MQL5\Files')|Out-Null
 Copy-Item -LiteralPath (Join-Path $Here 'MQL5\Experts\QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1.mq5') -Destination (Join-Path $iso 'MQL5\Experts') -Force
}
function Read-ExclusiveText([string]$f,[int]$ms=15000){
 $dl=[DateTime]::UtcNow.AddMilliseconds($ms)
 do{
  if(Test-Path $f){
   $h=$null
   try{
    $h=[IO.File]::Open($f,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::None)
    $b=New-Object byte[] ([int]$h.Length);$o=0
    while($o -lt $b.Length){$n=$h.Read($b,$o,$b.Length-$o);if($n -le 0){break};$o+=$n}
    if($o -eq $b.Length){return [Text.Encoding]::UTF8.GetString($b)}
   }catch [IO.IOException]{} finally {if($null -ne $h){$h.Dispose()}}
  }
  Start-Sleep -Milliseconds 125
 }while([DateTime]::UtcNow -lt $dl)
 return $null
}
function Read-Rows([string]$f,[int]$ms=15000){$t=Read-ExclusiveText $f $ms;if($null -eq $t){return @()};try{return @($t|ConvertFrom-Csv)}catch{return @()}}
function First([string]$f,[string]$id,[int]$ms=15000){foreach($r in @(Read-Rows $f $ms)){if([string]$r.test_id -eq $id){return $r}};return $null}
function Write-Set([string]$iso,[string]$name,[int]$mode,[int]$hold,[long]$token){
 $p=Join-Path $iso ("MQL5\Presets\"+$name+".set")
 @("InpMode=$mode","InpPrefix=$Prefix","InpHoldMs=$hold","InpExpectedToken=$token")|Set-Content -LiteralPath $p -Encoding ASCII
 return $name+".set"
}
function Write-Ini([string]$name,[string]$set){
 $p=Join-Path $Ev ($name+".ini")
 @"
[Experts]
AllowLiveTrading=0
AllowDllImport=0
Enabled=1
Account=0
Profile=0

[StartUp]
Expert=QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1
ExpertParameters=$set
Symbol=XAUUSD
Period=M1
"@|Set-Content -LiteralPath $p -Encoding ASCII
 return $p
}
function Start-Normal([string]$iso,[string]$name,[string]$set){
 if(!(SafeIso $iso)){Fail 'START_PATH_GUARD' 23}
 if(@(Get-IsoTerminalProcesses $iso).Count -ne 0){Fail 'START_WITH_STALE_ISO_PROCESS' 28}
 $term=Join-Path $iso 'terminal64.exe';$ini=Write-Ini $name $set
 [void](Start-Process -FilePath $term -ArgumentList @('/portable',("/config:`"$ini`"")) -PassThru)
 $owned=@(Wait-IsoTerminal $iso 20000)
 if(@($owned).Count -eq 0){Fail 'ACTUAL_ISO_TERMINAL_NOT_DISCOVERED' 29}
 Write-Q ('PROCESS OWNERSHIP BOUND iso='+$iso+' pids='+(($owned|ForEach-Object {$_.pid}) -join ','))
 return @($owned)
}
function LocalFile([string]$iso,[string]$suffix){Join-Path $iso ("MQL5\Files\"+$Prefix+"_"+$suffix)}
function Snapshot-Procs([string]$name){
 $rows=@()
 foreach($p in @(Get-Process terminal64 -ErrorAction SilentlyContinue)){try{$rows += [pscustomobject]@{pid=[int]$p.Id;path=[string]$p.Path}}catch{}}
 if(@($rows).Count -gt 0){$rows|Export-Csv -LiteralPath (Join-Path $Ev $name) -NoTypeInformation -Encoding UTF8}else{Set-Content -LiteralPath (Join-Path $Ev $name) -Value '' -Encoding UTF8}
}
function Copy-Evidence([string]$src,[string]$name){if(Test-Path $src){Copy-Item -LiteralPath $src -Destination (Join-Path $Ev $name) -Force}}
function Zip-Evidence(){Add-Type -AssemblyName IO.Compression.FileSystem;if(Test-Path $EvidenceZip){Remove-Item -LiteralPath $EvidenceZip -Force};[IO.Compression.ZipFile]::CreateFromDirectory($Ev,$EvidenceZip,[IO.Compression.CompressionLevel]::Optimal,$false);return $EvidenceZip}

try{
 Write-Q ('START R2T v2 actual-terminal qualifier run_id='+$RunId)
 Write-Q 'SAFETY: no Candidate3, no trade API, AllowLiveTrading=0, isolated clones only.'
 Snapshot-Procs 'ACTIVE_TERMINALS_BEFORE.csv'
 $TerminalSrc=Join-Path $DarwinexInstall 'terminal64.exe';$MetaSrc=Join-Path $DarwinexInstall 'metaeditor64.exe'
 if(!(Test-Path $TerminalSrc) -or !(Test-Path $MetaSrc)){Fail 'DARWINEX_BINARIES_MISSING' 10}
 if(!(Test-Path $ActiveDataPath)){Fail 'ACTIVE_DATA_MISSING' 11}
 $mp=Get-Content -LiteralPath (Join-Path $Here 'PACKAGE_MANIFEST_SHA256.json') -Raw|ConvertFrom-Json
 foreach($pr in $mp.files.PSObject.Properties){$fp=Join-Path $Here ([string]$pr.Name);if(!(Test-Path $fp)){Fail ('MANIFEST_MISSING_'+$pr.Name) 12};if((Sha $fp)-ne [string]$pr.Value.sha256){Fail ('MANIFEST_HASH_'+$pr.Name) 13}}
 Recreate-Iso $IsoA;Recreate-Iso $IsoB
 $src=Join-Path $IsoA 'MQL5\Experts\QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1.mq5';$cl=Join-Path $Logs 'compile.log'
 $cp=Start-Process -FilePath (Join-Path $IsoA 'metaeditor64.exe') -ArgumentList @('/portable',("/compile:`"$src`""),("/log:`"$cl`"")) -Wait -PassThru
 if(!(Test-Path $cl)){Fail 'COMPILE_LOG_MISSING' 30}
 $ct=Get-Content -LiteralPath $cl -Raw
 if($ct -notmatch 'Result:\s*0 errors,\s*0 warnings'){Fail 'COMPILE_NOT_0_0' 31}
 $ex5=[IO.Path]::ChangeExtension($src,'.ex5');if(!(Test-Path $ex5)){Fail 'EX5_MISSING' 32}
 Copy-Item -LiteralPath $ex5 -Destination (Join-Path $IsoB 'MQL5\Experts\QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1.ex5') -Force
 Write-Q ('COMPILE PASS 0/0 ex5='+$(Sha $ex5))
 $s=Write-Set $IsoA 'R2T_SMOKE' 1 0 0;$sp=Start-Normal $IsoA 'R2T_SMOKE' $s
 $sf=LocalFile $IsoA 'RESULT.csv';$sr=First $sf 'R2T_SMOKE' 60000
 if($null -eq $sr -or $sr.status -ne 'PASS' -or [int]$sr.mql_tester -ne 0){Fail 'NORMAL_RUNTIME_SMOKE_FAIL' 40}
 Copy-Evidence $sf 'R2T_SMOKE_RESULT.csv';[void](Stop-IsoTerminals $IsoA $true)
 Write-Q ('NORMAL RUNTIME SMOKE PASS build='+$sr.build+' common='+$sr.common_path)
 $hs=Write-Set $IsoA 'R2T_HOLDER' 2 120000 0;$hp=Start-Normal $IsoA 'R2T_HOLDER' $hs
 $hf=LocalFile $IsoA 'HOLDER_READY.csv';$hr=First $hf 'R2T_HOLDER_READY' 60000
 if($null -eq $hr -or $hr.status -ne 'PASS'){Fail 'HOLDER_READY_FAIL' 50}
 Copy-Evidence $hf 'R2T_HOLDER_READY.csv'
 $ps=Write-Set $IsoB 'R2T_PROBE' 3 0 0;$pp=Start-Normal $IsoB 'R2T_PROBE' $ps
 $pf=LocalFile $IsoB 'RESULT.csv';$pr=First $pf 'R2T_FENCE_PROBE' 60000
 if($null -eq $pr){Fail 'PROBE_RESULT_MISSING' 51}
 Copy-Evidence $pf 'R2T_PROBE_RESULT.csv'
 if([string]$hr.common_path -ne [string]$pr.common_path){Fail ('COMMON_PATH_MISMATCH holder='+$hr.common_path+' probe='+$pr.common_path) 52}
 if($pr.status -ne 'PASS'){Fail ('ACTUAL_RUNTIME_FENCE_BROKEN_'+$pr.detail) 53}
 [void](Stop-IsoTerminals $IsoB $true)
 Write-Q 'ACTUAL TERMINAL FENCE PASS second executor denied exact FILE_COMMON lock'
 $rf=LocalFile $IsoA 'RELEASED.csv';$rr=First $rf 'R2T_RELEASED' 150000
 if($null -eq $rr -or $rr.status -ne 'PASS' -or [long]$rr.token -ne [long]$hr.token){Fail 'HOLDER_RELEASE_FAIL' 54}
 Copy-Evidence $rf 'R2T_RELEASED.csv';[void](Stop-IsoTerminals $IsoA $true)
 $rs=Write-Set $IsoB 'R2T_REACQUIRE' 4 0 0;$rp=Start-Normal $IsoB 'R2T_REACQUIRE' $rs
 $rpf=LocalFile $IsoB 'RESULT.csv';$rar=First $rpf 'R2T_FENCE_REACQUIRE' 60000
 if($null -eq $rar -or $rar.status -ne 'PASS'){Fail 'REACQUIRE_FAIL' 55}
 Copy-Evidence $rpf 'R2T_REACQUIRE_RESULT.csv';[void](Stop-IsoTerminals $IsoB $true)
 $ws=Write-Set $IsoA 'R2T_RESTART_WRITE' 5 0 0;$wp=Start-Normal $IsoA 'R2T_RESTART_WRITE' $ws
 $wf=LocalFile $IsoA 'RESULT.csv';$wr=First $wf 'R2T_RESTART_WRITE' 60000
 if($null -eq $wr -or $wr.status -ne 'PASS'){Fail 'RESTART_WRITE_FAIL' 60}
 $tok=[long]$wr.token;Copy-Evidence $wf 'R2T_RESTART_WRITE_RESULT.csv';[void](Stop-IsoTerminals $IsoA $true)
 $rdset=Write-Set $IsoA 'R2T_RESTART_READ' 6 0 $tok;$rdp=Start-Normal $IsoA 'R2T_RESTART_READ' $rdset
 $rdf=LocalFile $IsoA 'RESULT.csv';$rdr=First $rdf 'R2T_RESTART_READ' 60000
 if($null -eq $rdr -or $rdr.status -ne 'PASS'){Fail 'RESTART_READ_FAIL' 61}
 Copy-Evidence $rdf 'R2T_RESTART_READ_RESULT.csv';[void](Stop-IsoTerminals $IsoA $true)
 Snapshot-Procs 'ACTIVE_TERMINALS_AFTER.csv'
 $receipt=[ordered]@{schema='QROS_RUNNER_RUNTIME_FENCE_QUALIFICATION_2.1';utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;decision='PASS';state='ACTUAL_TERMINAL_FENCE_QUALIFIED_V2';build=[int]$sr.build;common_path=[string]$hr.common_path;checks=[ordered]@{normal_runtime_smoke='PASS';process_ownership_by_actual_iso_path='PASS';common_path_identity='PASS';second_executor_denied='PASS';release='PASS';reacquire='PASS';restart_persistence='PASS';no_orphan_isolated_terminal='PASS'};candidate3_executed=$false;trade_api_present=$false;real_broker_orders_authorized=$false;real_broker_orders_sent=0;deployment_allowed=$false;cert_arm_allowed=$false;v223_cert_rule='KEEP_QDB1_EXEC_CERT_0'}
 $receipt|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $Ev 'R2T_RECEIPT.json') -Encoding UTF8
 $z=Zip-Evidence;Write-Host '';Write-Host 'R2T V2 PASS ACTUAL_TERMINAL_FENCE_QUALIFIED_V2';Write-Host ('Evidence: '+$z);Write-Host ('SHA-256: '+(Sha $z));exit 0
}catch{
 $reason=$_.Exception.Message;$code=99;try{if($_.Exception.Data.Contains('QROS_CODE')){$code=[int]$_.Exception.Data['QROS_CODE']}}catch{}
 $etype=$_.Exception.GetType().FullName
 $stack=[string]$_.ScriptStackTrace
 $pos=[string]$_.InvocationInfo.PositionMessage
 try{Write-Q ('FAIL '+$reason+' code='+$code+' type='+$etype)}catch{}
 try{
  @(
   'reason='+$reason,
   'code='+$code,
   'exception_type='+$etype,
   'position='+$pos,
   'script_stack='+$stack
  )|Set-Content -LiteralPath (Join-Path $Ev 'ERROR_DIAGNOSTIC.txt') -Encoding UTF8
 }catch{}
 try{Snapshot-Procs 'ACTIVE_TERMINALS_AFTER_FAIL.csv'}catch{}
 $fr=[ordered]@{schema='QROS_RUNNER_RUNTIME_FENCE_QUALIFICATION_2.1';utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;decision='FAIL';state='RUNNER_REJECTED_ACTUAL_TERMINAL_FENCE';reason=$reason;code=$code;exception_type=$etype;position=$pos;script_stack=$stack;candidate3_executed=$false;real_broker_orders_authorized=$false;real_broker_orders_sent=0;deployment_allowed=$false;cert_arm_allowed=$false;v223_cert_rule='KEEP_QDB1_EXEC_CERT_0'}
 try{$fr|ConvertTo-Json -Depth 10|Set-Content -LiteralPath (Join-Path $Ev 'R2T_RECEIPT.json') -Encoding UTF8}catch{}
 try{$z=Zip-Evidence;Write-Host ('Evidence: '+$z);Write-Host ('SHA-256: '+(Sha $z))}catch{}
 exit $code
}finally{Cleanup}
