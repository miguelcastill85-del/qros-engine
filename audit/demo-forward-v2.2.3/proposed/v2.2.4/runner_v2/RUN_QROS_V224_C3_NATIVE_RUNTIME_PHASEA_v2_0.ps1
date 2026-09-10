param(
  [string]$DarwinexInstall="C:\Program Files\Darwinex MetaTrader 5",
  [string]$ActiveDataPath="C:\Users\makk7\AppData\Roaming\MetaQuotes\Terminal\6C3C6A11D1C3791DD4DBF45421BF8028"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$Version="2.0"
$VersionSlug="v2_0"
$Schema="QROS_V224_C3_NATIVE_RUNTIME_PHASEA_RECEIPT_2.0"
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$RunId=(Get-Date -Format 'yyyyMMdd_HHmmss')+"_"+([guid]::NewGuid().ToString('N').Substring(0,8))
$OutRoot="C:\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_v2_0"
$Out=Join-Path $OutRoot $RunId
$Ev=Join-Path $Out "EVIDENCE"
$Logs=Join-Path $Ev "COMPILE_LOGS"
$IsoA=("C:\QROS_MT5_ISOLATED_V224_PHASEA20_A_"+$RunId)
$IsoB=("C:\QROS_MT5_ISOLATED_V224_PHASEA20_B_"+$RunId)
$Common="$env:APPDATA\MetaQuotes\Terminal\Common\Files"
$PrefixBase=("QROS_V224_PHASEA20_"+$RunId)
$EvidenceZip=Join-Path $OutRoot ("QROS_V224_C3_NATIVE_RUNTIME_PHASEA_EVIDENCE_v2_0_"+$RunId+".zip")
$script:hp=$null
$script:pp=$null
$script:rp=$null
$script:ExitCode=0
$script:Success=$false

New-Item -ItemType Directory -Force -Path $OutRoot,$Out,$Ev,$Logs,$Common | Out-Null
$Log=Join-Path $Ev "QROS_V224_C3_NATIVE_RUNTIME_PHASEA_v2_0.log"

function Write-Q([string]$m){
  $s="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $m"
  Write-Host $s
  Add-Content -LiteralPath $Log -Value $s -Encoding UTF8
}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function SafeIsoPath([string]$p){
  if([string]::IsNullOrWhiteSpace($p)){return $false}
  $full=[System.IO.Path]::GetFullPath($p)
  return ($full.StartsWith($IsoA,[System.StringComparison]::OrdinalIgnoreCase) -or
          $full.StartsWith($IsoB,[System.StringComparison]::OrdinalIgnoreCase))
}
function Fail([string]$reason,[int]$code){
  $e=New-Object System.Exception($reason)
  $e.Data["QROS_CODE"]=$code
  throw $e
}
function Zip-Evidence(){
  try{
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if(Test-Path $EvidenceZip){Remove-Item -LiteralPath $EvidenceZip -Force}
    [System.IO.Compression.ZipFile]::CreateFromDirectory($Ev,$EvidenceZip,[System.IO.Compression.CompressionLevel]::Optimal,$false)
    return $EvidenceZip
  }catch{
    Write-Q ("EVIDENCE ZIP ERROR "+$_.Exception.Message)
    return $null
  }
}
function Copy-Tree([string]$src,[string]$dst){
  New-Item -ItemType Directory -Force -Path $dst|Out-Null
  & robocopy.exe $src $dst /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  $rc=$LASTEXITCODE
  if($rc -ge 8){Fail ("ROBOCOPY_"+$rc) 22}
}
function Recreate-Iso([string]$iso){
  if(!(SafeIsoPath $iso)){Fail 'ISOLATION_PATH_GUARD_FAILED' 20}
  $procs=Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object {try{$_.Path -like "$iso*"}catch{$false}}
  if($procs){Fail ("STALE_ISOLATED_TERMINAL_RUNNING_"+$iso) 21}
  if(Test-Path $iso){Remove-Item -LiteralPath $iso -Recurse -Force}
  New-Item -ItemType Directory -Force -Path $iso|Out-Null
  Copy-Tree $DarwinexInstall $iso
  Copy-Tree (Join-Path $ActiveDataPath 'config') (Join-Path $iso 'config')
  New-Item -ItemType Directory -Force -Path (Join-Path $iso 'MQL5\Experts'),(Join-Path $iso 'MQL5\Include'),(Join-Path $iso 'MQL5\Profiles\Tester')|Out-Null
  Copy-Tree (Join-Path $ActiveDataPath 'MQL5\Include') (Join-Path $iso 'MQL5\Include')
  Copy-Item -LiteralPath (Join-Path $Here 'MQL5\Include\QROS_DEMO_BUS_v2_2_4.mqh') -Destination (Join-Path $iso 'MQL5\Include') -Force
  Copy-Item -LiteralPath (Join-Path $Here 'MQL5\Include\QROS_RISK_KERNEL_APPROVED_v15420.mqh') -Destination (Join-Path $iso 'MQL5\Include') -Force
  Copy-Item -LiteralPath (Join-Path $Here 'MQL5\Experts\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.mq5') -Destination (Join-Path $iso 'MQL5\Experts') -Force
  Get-ChildItem -LiteralPath (Join-Path $Here 'MQL5\Profiles\Tester') -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $iso 'MQL5\Profiles\Tester') -Force
  }
}
function Set-ProfileValues([string]$iso,[string]$set,[string]$prefix,[int]$holdMs=-1){
  $p=Join-Path $iso ('MQL5\Profiles\Tester\'+$set)
  if(!(Test-Path $p)){Fail ('SET_NOT_FOUND_'+$set) 23}
  $t=Get-Content -LiteralPath $p -Raw
  if($t -notmatch '(?m)^InpHarnessPrefix='){Fail ('SET_PREFIX_FIELD_MISSING_'+$set) 24}
  $t=[regex]::Replace($t,'(?m)^InpHarnessPrefix=.*$',('InpHarnessPrefix='+$prefix))
  if($holdMs -ge 0){
    if($t -notmatch '(?m)^InpHarnessFenceHoldMs='){Fail ('SET_HOLD_FIELD_MISSING_'+$set) 25}
    $t=[regex]::Replace($t,'(?m)^InpHarnessFenceHoldMs=.*$',('InpHarnessFenceHoldMs='+$holdMs))
  }
  Set-Content -LiteralPath $p -Value $t -Encoding ASCII
}
function Make-Ini([string]$iso,[string]$name,[string]$set,[int]$allowTrade,[string]$fromDate='2026.09.08',[string]$toDate='2026.09.09'){
  $ini=Join-Path $Ev ($name+'.ini')
  @"
[Experts]
AllowLiveTrading=$allowTrade
AllowDllImport=0

[Tester]
Expert=QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1
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
"@|Set-Content -LiteralPath $ini -Encoding ASCII
  $it=Get-Content -LiteralPath $ini -Raw
  if($it -notmatch '\[Tester\]' -or $it -notmatch 'UseLocal=1' -or $it -notmatch 'UseRemote=0' -or
     $it -notmatch 'UseCloud=0' -or $it -notmatch 'ShutdownTerminal=1'){
    Fail ('INI_CONTRACT_FAILED_'+$name) 26
  }
  return $ini
}
function Run-Tester([string]$iso,[string]$name,[string]$set,[int]$allowTrade,[int]$timeoutSec=1800,[string]$fromDate='2026.09.08',[string]$toDate='2026.09.09'){
  $terminal=Join-Path $iso 'terminal64.exe'
  $ini=Make-Ini $iso $name $set $allowTrade $fromDate $toDate
  Write-Q ("TESTER START "+$name+" allowTrade="+$allowTrade+" dates="+$fromDate+".."+$toDate+" (simulated Strategy Tester only)")
  $p=Start-Process -FilePath $terminal -ArgumentList @('/portable',("/config:`"$ini`"")) -PassThru
  $done=$true
  try{Wait-Process -Id $p.Id -Timeout $timeoutSec -ErrorAction Stop}catch{$done=$false}
  if(!$done){
    try{$p.Refresh();if(!$p.HasExited -and $p.Path -like "$iso*"){Stop-Process -Id $p.Id -Force}}catch{}
    Fail ('ISOLATED_TESTER_TIMEOUT_'+$name) 40
  }
  try{$p.Refresh()}catch{}
  Write-Q ("TESTER END "+$name+" exit="+$p.ExitCode)
  Start-Sleep -Milliseconds 500
}
function Read-ExclusiveText([string]$file,[int]$retryMs=10000){
  $deadline=[DateTime]::UtcNow.AddMilliseconds($retryMs)
  do{
    if(Test-Path $file){
      $fs=$null
      try{
        $fs=[System.IO.File]::Open($file,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::None)
        $len=[int]$fs.Length
        $bytes=New-Object byte[] $len
        $off=0
        while($off -lt $len){
          $n=$fs.Read($bytes,$off,$len-$off)
          if($n -le 0){break}
          $off+=$n
        }
        if($off -ne $len){throw "SHORT_READ"}
        return [System.Text.Encoding]::UTF8.GetString($bytes)
      }catch [System.IO.IOException]{
      }finally{
        if($null -ne $fs){try{$fs.Dispose()}catch{}}
      }
    }
    Start-Sleep -Milliseconds 125
  }while([DateTime]::UtcNow -lt $deadline)
  return $null
}
function Read-CsvRows([string]$file,[int]$retryMs=10000){
  $text=Read-ExclusiveText $file $retryMs
  if($null -eq $text){return @()}
  try{return @($text | ConvertFrom-Csv)}catch{return @()}
}
function Read-Marker([string]$file,[string[]]$headers,[int]$retryMs=10000){
  $text=Read-ExclusiveText $file $retryMs
  if($null -eq $text){return $null}
  try{return @($text | ConvertFrom-Csv -Header $headers)[0]}catch{return $null}
}
function Wait-ForCommonResult([string]$file,[int]$seconds=30){
  return ($null -ne (Read-ExclusiveText $file ($seconds*1000)))
}
function Copy-Exclusive([string]$src,[string]$dst,[int]$retryMs=10000){
  $deadline=[DateTime]::UtcNow.AddMilliseconds($retryMs)
  do{
    if(Test-Path $src){
      $s=$null;$d=$null
      try{
        $s=[System.IO.File]::Open($src,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::None)
        $d=[System.IO.File]::Open($dst,[System.IO.FileMode]::Create,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
        $s.CopyTo($d)
        $d.Flush()
        return $true
      }catch [System.IO.IOException]{
      }finally{
        if($null -ne $d){try{$d.Dispose()}catch{}}
        if($null -ne $s){try{$s.Dispose()}catch{}}
      }
    }
    Start-Sleep -Milliseconds 125
  }while([DateTime]::UtcNow -lt $deadline)
  return $false
}
function Snapshot-CommonPrefix([string]$prefix,[int]$retryMs=10000){
  $items=@(Get-ChildItem -LiteralPath $Common -Filter ($prefix+'*') -File -ErrorAction SilentlyContinue)
  foreach($item in $items){
    if(!(Copy-Exclusive $item.FullName (Join-Path $Ev $item.Name) $retryMs)){
      Fail ('EVIDENCE_SNAPSHOT_LOCKED_'+$item.Name) 81
    }
  }
  return $items.Count
}
function Read-Status([string]$file,[string]$id,[int]$retryMs=10000){
  $rows=Read-CsvRows $file $retryMs
  $r=$rows | Where-Object {$_.test_id -eq $id} | Select-Object -First 1
  if($null -eq $r){return 'MISSING'}
  return [string]$r.status
}
function Stop-IsolatedProcess($p,[string]$iso){
  if($null -eq $p){return}
  if(!(SafeIsoPath $iso)){return}
  try{
    $p.Refresh()
    if(!$p.HasExited -and $p.Path -like "$iso*"){
      Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
      try{Wait-Process -Id $p.Id -Timeout 15 -ErrorAction SilentlyContinue}catch{}
    }
  }catch{}
}
function Capture-Diagnostics([string]$tag,[string]$iso){
  $d=Join-Path $Ev ('DIAGNOSTICS_'+$tag)
  New-Item -ItemType Directory -Force -Path $d|Out-Null
  Get-ChildItem -LiteralPath $Common -Filter ($PrefixBase+'*') -ErrorAction SilentlyContinue |
    Select-Object FullName,Length,LastWriteTime | ConvertTo-Json -Depth 4 |
    Set-Content -LiteralPath (Join-Path $d 'COMMON_RUN_FILES.json') -Encoding UTF8
  $roots=@((Join-Path $iso 'logs'),(Join-Path $iso 'Tester'))
  foreach($root in $roots){
    if(Test-Path $root){
      Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.log' -ErrorAction SilentlyContinue |
        Where-Object {$_.LastWriteTime -gt (Get-Date).AddMinutes(-30)} |
        ForEach-Object {
          $safe=($_.FullName -replace '[:\\/ ]','_')
          Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $d $safe) -Force -ErrorAction SilentlyContinue
        }
    }
  }
  $testerRoot=Join-Path $env:APPDATA 'MetaQuotes\Tester'
  if(Test-Path $testerRoot){
    Get-ChildItem -LiteralPath $testerRoot -Recurse -File -Filter '*.log' -ErrorAction SilentlyContinue |
      Where-Object {$_.LastWriteTime -gt (Get-Date).AddMinutes(-30)} |
      ForEach-Object {
        $safe=('APPDATA_'+($_.FullName -replace '[:\\/ ]','_'))
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $d $safe) -Force -ErrorAction SilentlyContinue
      }
  }
}

function Cleanup-Owned(){
  try{Stop-IsolatedProcess $script:rp $IsoB}catch{}
  try{Stop-IsolatedProcess $script:pp $IsoB}catch{}
  try{Stop-IsolatedProcess $script:hp $IsoA}catch{}
  $script:rp=$null;$script:pp=$null;$script:hp=$null
}
function Snapshot-ActiveAfter(){
  $a=@()
  Get-Process terminal64 -ErrorAction SilentlyContinue | ForEach-Object {
    try{$a += [pscustomobject]@{pid=$_.Id;path=$_.Path}}catch{$a += [pscustomobject]@{pid=$_.Id;path='UNKNOWN'}}
  }
  $a|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $Ev 'ACTIVE_TERMINALS_AFTER.json') -Encoding UTF8
}

function Runner-SelfTest(){
  $checks=New-Object System.Collections.Generic.List[object]
  function C([string]$id,[bool]$pass,[string]$detail){
    $checks.Add([pscustomobject]@{id=$id;status=$(if($pass){'PASS'}else{'FAIL'});detail=$detail})
    if(!$pass){Fail ('RUNNER_SELFTEST_'+$id) 15}
  }
  C 'S01_POWERSHELL_VERSION' ($PSVersionTable.PSVersion.Major -ge 5) ($PSVersionTable.PSVersion.ToString())
  C 'S02_PATH_GUARD_ACTIVE_DATA_REJECT' (!(SafeIsoPath $ActiveDataPath)) $ActiveDataPath
  C 'S03_PATH_GUARD_INSTALL_REJECT' (!(SafeIsoPath $DarwinexInstall)) $DarwinexInstall
  C 'S04_PATH_GUARD_ISOA_ACCEPT' (SafeIsoPath $IsoA) $IsoA
  C 'S05_PATH_GUARD_ISOB_ACCEPT' (SafeIsoPath $IsoB) $IsoB
  $lp=Join-Path $Out 'SELFTEST_LOCK.txt'
  $cp=Join-Path $Out 'SELFTEST_LOCK_COPY.txt'
  $fs=$null
  try{
    $fs=[System.IO.File]::Open($lp,[System.IO.FileMode]::Create,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
    $b=[System.Text.Encoding]::UTF8.GetBytes("qros-lock-selftest")
    $fs.Write($b,0,$b.Length);$fs.Flush()
    $blocked=($null -eq (Read-ExclusiveText $lp 300))
    C 'S06_EXCLUSIVE_READ_BLOCKED_WHILE_WRITER_OPEN' $blocked 'FileShare.None reader correctly blocked'
  }finally{
    if($null -ne $fs){$fs.Dispose()}
  }
  $text=Read-ExclusiveText $lp 2000
  C 'S07_EXCLUSIVE_READ_AFTER_CLOSE' ($text -eq 'qros-lock-selftest') $text
  $copied=Copy-Exclusive $lp $cp 2000
  C 'S08_EXCLUSIVE_COPY_AFTER_CLOSE' $copied 'exclusive copy helper'
  C 'S09_EXCLUSIVE_COPY_HASH' ((Sha $lp) -eq (Sha $cp)) (Sha $lp)
  $csv=Join-Path $Out 'SELFTEST.csv'
  "test_id,status,detail`nSELF,PASS,ok" | Set-Content -LiteralPath $csv -Encoding UTF8
  C 'S10_CSV_PARSE' ((Read-Status $csv 'SELF') -eq 'PASS') 'Read-Status via exclusive snapshot'
  $marker=Join-Path $Out 'SELFTEST_MARKER.csv'
  "1,123,Darwinex-Demo,42" | Set-Content -LiteralPath $marker -Encoding UTF8
  $mr=Read-Marker $marker @('ok','token','server','login') 2000
  C 'S11_MARKER_PARSE' ($null -ne $mr -and [int]$mr.ok -eq 1 -and [long]$mr.token -eq 123) 'headerless marker parse'
  $collision=@(Get-ChildItem -LiteralPath $Common -Filter ($PrefixBase+'*') -ErrorAction SilentlyContinue).Count
  C 'S12_UNIQUE_COMMON_NAMESPACE' ($collision -eq 0) ("collision_count="+$collision)
  $pt=$null;$pe=$null
  [void][System.Management.Automation.Language.Parser]::ParseFile($MyInvocation.MyCommand.Path,[ref]$pt,[ref]$pe)
  C 'S13_POWERSHELL_AST_PARSE' (@($pe).Count -eq 0) ("parse_errors="+@($pe).Count)
  $checks | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Ev 'RUNNER_SELFTEST.json') -Encoding UTF8
  Write-Q ("RUNNER SELFTEST PASS "+$checks.Count+"/"+$checks.Count)
}

try {
Write-Q ('START Candidate3 native runtime Phase-A gate v2.0 run_id='+$RunId)
Write-Q 'SAFETY: Strategy Tester only. No active terminal stop/restart. No real broker orders. No deployment. No CERT mutation in active terminal.'

$TerminalSrc=Join-Path $DarwinexInstall 'terminal64.exe'
$MetaSrc=Join-Path $DarwinexInstall 'metaeditor64.exe'
if(!(Test-Path $TerminalSrc)){Fail 'DARWINEX_TERMINAL_NOT_FOUND' 10}
if(!(Test-Path $MetaSrc)){Fail 'DARWINEX_METAEDITOR_NOT_FOUND' 11}
if(!(Test-Path $ActiveDataPath)){Fail 'ACTIVE_DATA_PATH_NOT_FOUND' 12}
if(!(Test-Path (Join-Path $ActiveDataPath 'config'))){Fail 'ACTIVE_CONFIG_NOT_FOUND' 13}
$ActiveInclude=Join-Path $ActiveDataPath 'MQL5\Include'
if(!(Test-Path $ActiveInclude)){Fail 'ACTIVE_MQL5_INCLUDE_NOT_FOUND' 17}
if(!(Test-Path (Join-Path $ActiveInclude 'Trade\Trade.mqh'))){Fail 'ACTIVE_STANDARD_TRADE_INCLUDE_NOT_FOUND' 18}

$ManifestPath=Join-Path $Here 'PACKAGE_MANIFEST_SHA256.json'
if(!(Test-Path $ManifestPath)){Fail 'PACKAGE_MANIFEST_MISSING' 14}
$Pm=Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach($prop in $Pm.files.PSObject.Properties){
  $rel=[string]$prop.Name
  $meta=$prop.Value
  $fp=Join-Path $Here $rel
  if(!(Test-Path $fp)){Fail ('PACKAGE_MANIFEST_FILE_MISSING_'+$rel) 14}
  if((Sha $fp) -ne [string]$meta.sha256){Fail ('PACKAGE_MANIFEST_HASH_MISMATCH_'+$rel) 15}
  if((Get-Item -LiteralPath $fp).Length -ne [long]$meta.bytes){Fail ('PACKAGE_MANIFEST_SIZE_MISMATCH_'+$rel) 15}
}
Write-Q ('PACKAGE MANIFEST PASS entries='+$Pm.files.PSObject.Properties.Count)

$Expected=@{
 'AUTHORITY\QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5'='721b63b96a297c5a0752a34f3439ff5babc7882e624df7c1ceb1d46fcdf99608';
 'MQL5\Include\QROS_DEMO_BUS_v2_2_4.mqh'='db389efd44f02af7ad437a2a49f8b50c88b5e344fa32c964c70812b930324ae5';
 'MQL5\Include\QROS_RISK_KERNEL_APPROVED_v15420.mqh'='8af000aac09747b896cef4e8c9263aaf675dab4fefa07b3d9d4b7c1c170ab49f';
 'MQL5\Experts\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.mq5'='f140a1019b4539e9df819c26f2144d26ad27b0714230a9d0fdb6739d9b50f5c3'
}
foreach($rel in $Expected.Keys){
  $p=Join-Path $Here $rel
  if(!(Test-Path $p)){Fail ("PACKAGE_FILE_MISSING_"+$rel) 14}
  if((Sha $p)-ne $Expected[$rel]){Fail ("PACKAGE_HASH_MISMATCH_"+$rel) 15}
}
Write-Q 'IDENTITY PASS exact repaired executor + bus + approved risk kernel + sealed test harness'

$HarnessText=Get-Content -LiteralPath (Join-Path $Here 'MQL5\Experts\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.mq5') -Raw
$HasPlaced=$HarnessText -match 'lrc==TRADE_RETCODE_PLACED'
$HasDone=$HarnessText -match 'lrc==TRADE_RETCODE_DONE'
$HasDonePartial=$HarnessText -match 'lrc==TRADE_RETCODE_DONE_PARTIAL'
$HasObserved=$HarnessText -match 'bool\s+lpass=.*lobserved'
if(!$HasPlaced -or !$HasDone -or !$HasDonePartial -or !$HasObserved){
  Fail 'A15_ACCEPTED_RETCODE_OBSERVED_STATE_PREFLIGHT_FAILED' 19
}
Write-Q 'A15 PREFLIGHT PASS accepted retcode set mirrors executor and requires observed working order'

$ht=Get-Content -LiteralPath (Join-Path $Here 'MQL5\Experts\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.mq5') -Raw
if($ht -notmatch 'REFUSES NON-TESTER EXECUTION' -or $ht -notmatch 'MQLInfoInteger\(MQL_TESTER\)'){Fail 'HARNESS_TESTER_GUARD_MISSING' 16}

Runner-SelfTest

$ActiveBefore=@()
Get-Process terminal64 -ErrorAction SilentlyContinue | ForEach-Object {
  try{$ActiveBefore += [pscustomobject]@{pid=$_.Id;path=$_.Path}}catch{$ActiveBefore += [pscustomobject]@{pid=$_.Id;path='UNKNOWN'}}
}
$ActiveBefore|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $Ev 'ACTIVE_TERMINALS_BEFORE.json') -Encoding UTF8
Write-Q ("ACTIVE TERMINAL SNAPSHOT before count="+$ActiveBefore.Count+" -- no action taken")

try{Recreate-Iso $IsoA;Recreate-Iso $IsoB}catch{Fail ('ISOLATED_CLONE_FAILED_'+$_.Exception.Message) 22}
Write-Q 'TWO ISOLATED CLONES READY; active data/MQL5/profiles/global variables untouched by runner'
$IncludeRoot=Join-Path $IsoA 'MQL5\Include'
$IncludeSnapshot=Get-ChildItem -LiteralPath $IncludeRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
  [pscustomobject]@{relative_path=$_.FullName.Substring($IncludeRoot.Length+1);bytes=$_.Length;sha256=(Sha $_.FullName)}
}
$IncludeSnapshot | Export-Csv -LiteralPath (Join-Path $Ev 'STANDARD_INCLUDE_SNAPSHOT_SHA256.csv') -NoTypeInformation -Encoding UTF8
Write-Q ("STANDARD INCLUDE SNAPSHOT PASS files="+@($IncludeSnapshot).Count+" Trade.mqh="+(Sha (Join-Path $IncludeRoot 'Trade\Trade.mqh')))

$MetaA=Join-Path $IsoA 'metaeditor64.exe'
$src=Join-Path $IsoA 'MQL5\Experts\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.mq5'
$cl=Join-Path $Logs 'QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.mq5.log'
if(Test-Path $cl){Remove-Item $cl -Force}
$p=Start-Process -FilePath $MetaA -ArgumentList @('/portable',("/compile:`"$src`""),("/log:`"$cl`"")) -Wait -PassThru
Start-Sleep -Milliseconds 500
if(!(Test-Path $cl)){Fail 'COMPILE_LOG_MISSING' 30}
$ct=Get-Content -LiteralPath $cl -Raw
if($ct -notmatch 'Result:\s*0 errors,\s*0 warnings'){Fail 'COMPILE_NOT_0_0' 31}
$ex5=[System.IO.Path]::ChangeExtension($src,'.ex5')
if(!(Test-Path $ex5)){Fail 'HARNESS_EX5_MISSING_AFTER_COMPILE' 32}
$Compile=[ordered]@{source_sha256=(Sha $src);ex5_sha256=(Sha $ex5);compiler_sha256=(Sha $MetaA);exit_code=$p.ExitCode;result='0 errors / 0 warnings'}
$Compile|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $Ev 'COMPILE_RESULT.json') -Encoding UTF8
Write-Q ("COMPILE PASS 0/0 harness EX5 sha="+$Compile.ex5_sha256)
Copy-Item -LiteralPath $ex5 -Destination (Join-Path $IsoB 'MQL5\Experts\QROS_V224_C3_NATIVE_RUNTIME_PHASEA_HARNESS_v1.ex5') -Force

$smokePrefix=($PrefixBase+'_RUNNER_SMOKE')
Set-ProfileValues $IsoA 'QROS_V224_PHASEA_FENCE_REACQUIRE.set' $smokePrefix 1000
Run-Tester $IsoA 'RUNNER_NATIVE_SMOKE' 'QROS_V224_PHASEA_FENCE_REACQUIRE.set' 0 300
$smokeReady=Join-Path $Common ($smokePrefix+'_HOLDER_READY.csv')
$smokeReleased=Join-Path $Common ($smokePrefix+'_RELEASED.csv')
$smokeResults=Join-Path $Common ($smokePrefix+'_RESULTS.csv')
if(!(Wait-ForCommonResult $smokeReady 30)){Fail 'RUNNER_NATIVE_SMOKE_READY_MISSING' 33}
if(!(Wait-ForCommonResult $smokeReleased 30)){Fail 'RUNNER_NATIVE_SMOKE_RELEASE_MISSING' 34}
$sm=Read-Marker $smokeReady @('ok','token','server','login') 5000
$sr=Read-Marker $smokeReleased @('released','token','server','login') 5000
if($null -eq $sm -or $null -eq $sr -or [int]$sm.ok -ne 1 -or [int]$sr.released -ne 1 -or [long]$sm.token -ne [long]$sr.token){Fail 'RUNNER_NATIVE_SMOKE_MARKER_INVALID' 35}
if((Read-Status $smokeResults 'F01_FENCE_HOLDER_ACQUIRE' 5000) -ne 'PASS'){Fail 'RUNNER_NATIVE_SMOKE_RESULT_NOT_PASS' 36}
[void](Snapshot-CommonPrefix $smokePrefix 5000)
Write-Q 'RUNNER NATIVE MATERIALIZATION SMOKE PASS before Candidate3 runtime tests'

$runtimePrefix=($PrefixBase+'_RUNTIME_A1')
Set-ProfileValues $IsoA 'QROS_V224_PHASEA_RUNTIME.set' $runtimePrefix
$runtimeCommon=Join-Path $Common ($runtimePrefix+'_RESULTS.csv')
Run-Tester $IsoA 'RUNTIME_ATTEMPT1' 'QROS_V224_PHASEA_RUNTIME.set' 1 2400 '2026.09.08' '2026.09.09'
$runtimeReady=Wait-ForCommonResult $runtimeCommon 30
if(!$runtimeReady){
  Write-Q 'RUNTIME RESULT unavailable/quiescence-not-proven after attempt1; preserving diagnostics and performing one isolated tester-only retry'
  Capture-Diagnostics 'RUNTIME_ATTEMPT1_MISSING' $IsoA
  $runtimePrefix=($PrefixBase+'_RUNTIME_A2')
  Set-ProfileValues $IsoA 'QROS_V224_PHASEA_RUNTIME.set' $runtimePrefix
  $runtimeCommon=Join-Path $Common ($runtimePrefix+'_RESULTS.csv')
  Start-Sleep -Seconds 2
  Run-Tester $IsoA 'RUNTIME_ATTEMPT2' 'QROS_V224_PHASEA_RUNTIME.set' 1 2400 '2026.01.05' '2026.03.31'
  $runtimeReady=Wait-ForCommonResult $runtimeCommon 30
}
if(!$runtimeReady){Capture-Diagnostics 'RUNTIME_ATTEMPT2_MISSING' $IsoA;Fail 'RUNTIME_RESULTS_MISSING_AFTER_TWO_NATIVE_TESTER_ATTEMPTS' 50}
$runtime=Join-Path $Ev 'QROS_V224_PHASEA_RUNTIME_RESULTS.csv'
if(!(Copy-Exclusive $runtimeCommon $runtime 10000)){Fail 'RUNTIME_RESULTS_EXCLUSIVE_SNAPSHOT_FAILED' 50}
$runtimeSummaryCommon=Join-Path $Common ($runtimePrefix+'_SUMMARY.csv')
if(Test-Path $runtimeSummaryCommon){[void](Copy-Exclusive $runtimeSummaryCommon (Join-Path $Ev 'QROS_V224_PHASEA_RUNTIME_SUMMARY.csv') 10000)}
[void](Snapshot-CommonPrefix $runtimePrefix 10000)
$rows=Read-CsvRows $runtime 10000
if($rows.Count -eq 0){Fail 'RUNTIME_RESULTS_PARSE_EMPTY' 50}
$failRows=@($rows|Where-Object {$_.status -eq 'FAIL'})
$mandatory=@('A01_TESTER_ONLY','A02_DARWINEX_DEMO_ENV','A03_TESTER_TRADE_PERMISSION','A04_HISTORYSELECT_NATIVE','A05_BIDASK_BARRIERS','A06_NATIVE_SESSION_SCHEDULE','A08_CTRADE_MARKET_BUY','A09_PROTECTION_OBSERVED','A10_CTRADE_INVALID_MODIFY_REJECT','A11_EXECUTOR_MGMT_MODIFY_CONFIRMED','A12_MGMT_SURVIVES_ENTRY_FAULT','A13_CTRADE_INVALID_VOLUME_REJECT','A14_CTRADE_INVALID_STOPS_REJECT','A15_CTRADE_PENDING_PLACED','A16_CTRADE_PENDING_DELETE','A17_ULONG_GT_2P53_ROUNDTRIP','A18_TORN_INTENT_FAIL_CLOSED','A19_LOST_ACK_REMAINS_RESERVED','A20_RESERVED_RESTART_CANCELS','A21_RECOVERY_LOCK_CLEAN_RELEASE','A23_PARTIAL_RESIDUAL_RISK_NATIVE_STATE')
$missingMandatory=@()
foreach($id in $mandatory){if((Read-Status $runtime $id)-ne 'PASS'){$missingMandatory+=$id}}
if($failRows.Count -gt 0){Fail ('RUNTIME_NATIVE_FAIL_'+($failRows.test_id -join '_')) 51}
if($missingMandatory.Count -gt 0){Fail ('RUNTIME_MANDATORY_NOT_PASS_'+($missingMandatory -join '_')) 52}
Write-Q 'RUNTIME NATIVE CORE PASS mandatory exact-state/CTrade tests'

$holderPrefix=($PrefixBase+'_FENCE_HOLDER')
$probePrefix=($PrefixBase+'_FENCE_PROBE')
Set-ProfileValues $IsoA 'QROS_V224_PHASEA_FENCE_HOLDER.set' $holderPrefix 90000
Set-ProfileValues $IsoB 'QROS_V224_PHASEA_FENCE_PROBE.set' $probePrefix 20000
$holderIni=Make-Ini $IsoA 'FENCE_HOLDER' 'QROS_V224_PHASEA_FENCE_HOLDER.set' 0
$probeIni=Make-Ini $IsoB 'FENCE_PROBE' 'QROS_V224_PHASEA_FENCE_PROBE.set' 0
$holderReady=Join-Path $Common ($holderPrefix+'_HOLDER_READY.csv')
$holderReleased=Join-Path $Common ($holderPrefix+'_RELEASED.csv')
$holderResults=Join-Path $Common ($holderPrefix+'_RESULTS.csv')
$probeResults=Join-Path $Common ($probePrefix+'_RESULTS.csv')
Write-Q 'FENCING START holder process'
$script:hp=Start-Process -FilePath (Join-Path $IsoA 'terminal64.exe') -ArgumentList @('/portable',("/config:`"$holderIni`"")) -PassThru
if(!(Wait-ForCommonResult $holderReady 60)){Capture-Diagnostics 'FENCE_HOLDER_READY_MISSING' $IsoA;Stop-IsolatedProcess $script:hp $IsoA;Fail 'FENCE_HOLDER_READY_TIMEOUT' 60}
$hcsv=Read-Marker $holderReady @('ok','token','server','login') 10000
if($null -eq $hcsv -or [int]$hcsv.ok -ne 1){Stop-IsolatedProcess $script:hp $IsoA;Fail 'FENCE_HOLDER_DID_NOT_ACQUIRE' 61}
Write-Q 'FENCING holder acquired and marker closed; launching second isolated tester during physical holder lease'
$script:pp=Start-Process -FilePath (Join-Path $IsoB 'terminal64.exe') -ArgumentList @('/portable',("/config:`"$probeIni`"")) -PassThru
if(!(Wait-ForCommonResult $probeResults 75)){Capture-Diagnostics 'FENCE_PROBE_RESULT_MISSING' $IsoB;Stop-IsolatedProcess $script:pp $IsoB;Stop-IsolatedProcess $script:hp $IsoA;Fail 'FENCE_PROBE_RESULT_TIMEOUT' 62}
if((Read-Status $probeResults 'F02_SECOND_EXECUTOR_BLOCKED' 10000) -ne 'PASS'){[void](Snapshot-CommonPrefix $probePrefix 10000);Stop-IsolatedProcess $script:pp $IsoB;Stop-IsolatedProcess $script:hp $IsoA;Fail 'TWO_TERMINAL_FENCING_NOT_PROVEN' 64}
Write-Q 'FENCING exclusion PASS second executor denied exact common lock'
if(!(Wait-ForCommonResult $holderReleased 135)){Capture-Diagnostics 'FENCE_HOLDER_RELEASE_MARKER_MISSING' $IsoA;Stop-IsolatedProcess $script:pp $IsoB;Stop-IsolatedProcess $script:hp $IsoA;Fail 'FENCE_HOLDER_RELEASE_EVIDENCE_TIMEOUT' 63}
$rel=Read-Marker $holderReleased @('released','token','server','login') 10000
if($null -eq $rel -or [int]$rel.released -ne 1 -or [long]$rel.token -ne [long]$hcsv.token){Stop-IsolatedProcess $script:pp $IsoB;Stop-IsolatedProcess $script:hp $IsoA;Fail 'FENCE_HOLDER_RELEASE_MARKER_INVALID' 65}
if((Read-Status $holderResults 'F01_FENCE_HOLDER_ACQUIRE' 10000) -ne 'PASS'){Stop-IsolatedProcess $script:pp $IsoB;Stop-IsolatedProcess $script:hp $IsoA;Fail 'FENCE_HOLDER_RESULT_NOT_PASS_AFTER_RELEASE' 66}
Write-Q 'FENCING release evidence PASS: lock released and holder result writer quiescent'
[void](Snapshot-CommonPrefix $holderPrefix 10000);[void](Snapshot-CommonPrefix $probePrefix 10000)
Stop-IsolatedProcess $script:pp $IsoB;Stop-IsolatedProcess $script:hp $IsoA;$script:pp=$null;$script:hp=$null

$rePrefix=($PrefixBase+'_FENCE_REACQUIRE')
Set-ProfileValues $IsoB 'QROS_V224_PHASEA_FENCE_REACQUIRE.set' $rePrefix 1000
$reIni=Make-Ini $IsoB 'FENCE_REACQUIRE' 'QROS_V224_PHASEA_FENCE_REACQUIRE.set' 0
$reReady=Join-Path $Common ($rePrefix+'_HOLDER_READY.csv')
$reReleased=Join-Path $Common ($rePrefix+'_RELEASED.csv')
$reResults=Join-Path $Common ($rePrefix+'_RESULTS.csv')
$script:rp=Start-Process -FilePath (Join-Path $IsoB 'terminal64.exe') -ArgumentList @('/portable',("/config:`"$reIni`"")) -PassThru
if(!(Wait-ForCommonResult $reReady 60)){Capture-Diagnostics 'FENCE_REACQUIRE_READY_MISSING' $IsoB;Stop-IsolatedProcess $script:rp $IsoB;Fail 'FENCE_POST_RELEASE_REACQUIRE_READY_TIMEOUT' 67}
$rcsv=Read-Marker $reReady @('ok','token','server','login') 10000
if($null -eq $rcsv -or [int]$rcsv.ok -ne 1){Stop-IsolatedProcess $script:rp $IsoB;Fail 'FENCE_POST_RELEASE_REACQUIRE_FAILED' 68}
if(!(Wait-ForCommonResult $reReleased 30)){Capture-Diagnostics 'FENCE_REACQUIRE_RELEASE_MISSING' $IsoB;Stop-IsolatedProcess $script:rp $IsoB;Fail 'FENCE_POST_RELEASE_RELEASE_TIMEOUT' 69}
if((Read-Status $reResults 'F01_FENCE_HOLDER_ACQUIRE' 10000) -ne 'PASS'){Stop-IsolatedProcess $script:rp $IsoB;Fail 'FENCE_POST_RELEASE_RESULT_NOT_PASS' 70}
[void](Snapshot-CommonPrefix $rePrefix 10000);Stop-IsolatedProcess $script:rp $IsoB;$script:rp=$null
Write-Q 'TWO-TERMINAL FENCING PASS exclusion while held + release + post-release reacquire'

$rwPrefix=($PrefixBase+'_RESTART_WRITE');$rrPrefix=($PrefixBase+'_RESTART_READ')
Set-ProfileValues $IsoA 'QROS_V224_PHASEA_RESTART_WRITE.set' $rwPrefix
Run-Tester $IsoA 'RESTART_WRITE' 'QROS_V224_PHASEA_RESTART_WRITE.set' 0 1200
$rwCommon=Join-Path $Common ($rwPrefix+'_RESULTS.csv')
if(!(Wait-ForCommonResult $rwCommon 30)){Fail 'RESTART_PHASE1_RESULTS_MISSING_OR_LOCKED' 71}
$rwrite=Join-Path $Ev 'QROS_V224_PHASEA_RESTART_WRITE_RESULTS.csv'
if(!(Copy-Exclusive $rwCommon $rwrite 10000)){Fail 'RESTART_PHASE1_SNAPSHOT_FAILED' 71}
[void](Snapshot-CommonPrefix $rwPrefix 10000)
if((Read-Status $rwrite 'R01_RESTART_WRITE') -ne 'PASS'){Fail 'RESTART_PHASE1_WRITE_NOT_PASS' 71}
Set-ProfileValues $IsoA 'QROS_V224_PHASEA_RESTART_READ.set' $rrPrefix
Run-Tester $IsoA 'RESTART_READ' 'QROS_V224_PHASEA_RESTART_READ.set' 0 1200
$rrCommon=Join-Path $Common ($rrPrefix+'_RESULTS.csv')
if(!(Wait-ForCommonResult $rrCommon 30)){Fail 'RESTART_PHASE2_RESULTS_MISSING_OR_LOCKED' 72}
$rread=Join-Path $Ev 'QROS_V224_PHASEA_RESTART_READ_RESULTS.csv'
if(!(Copy-Exclusive $rrCommon $rread 10000)){Fail 'RESTART_PHASE2_SNAPSHOT_FAILED' 72}
[void](Snapshot-CommonPrefix $rrPrefix 10000)
$r02=Read-Status $rread 'R02_RESTART_READ';$r03=Read-Status $rread 'R03_RESTART_UNRESOLVED_REMAINS_RESERVED'
$restartState=''
if($r02 -eq 'PASS' -and $r03 -eq 'PASS'){$restartState='PASS_NATIVE_TESTER_PROCESS_RESTART'}elseif($r02 -eq 'BLOCKED'){$restartState='BLOCKED_BY_TESTER_GLOBAL_VARIABLE_SCOPE'}else{Fail ('RESTART_RECONSTRUCTION_FAILED_R02_'+$r02+'_R03_'+$r03) 72}
Write-Q ("RESTART PROBE "+$restartState)

$A07=Read-Status $runtime 'A07_TESTER_OFFSET_CONTRACT';$A22=Read-Status $runtime 'A22_EXACT_SENDENTRY_NATIVE_TESTER';$A24=Read-Status $runtime 'A24_REAL_BROKER_PARTIAL_OR_LOST_ACK';$A25=Read-Status $runtime 'A25_DST_TRANSITION_AUTHORITY'
Cleanup-Owned;Snapshot-ActiveAfter
$receipt=[ordered]@{schema=$Schema;utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;decision='PASS_WITH_EXTERNAL_BLOCKERS';candidate='QROS_DARWINEX_DEMO_V224_CANDIDATE3';candidate_state='FROZEN_CANDIDATE';runner_qualification='PASS_LOCAL_SELFTEST_PLUS_NATIVE_FILE_LIFECYCLE';native_compile='PASS_1_OF_1_0_ERRORS_0_WARNINGS';runtime_native_core='PASS';runtime_tests=[ordered]@{total=$rows.Count;pass=@($rows|Where-Object {$_.status -eq 'PASS'}).Count;fail=@($rows|Where-Object {$_.status -eq 'FAIL'}).Count;skip=@($rows|Where-Object {$_.status -eq 'SKIP'}).Count;blocked=@($rows|Where-Object {$_.status -eq 'BLOCKED'}).Count};two_terminal_fencing='PASS';restart_probe=$restartState;tester_offset_contract=$A07;exact_sendentry_in_tester=$A22;native_tester_scope='MQL5_STRATEGY_TESTER_SIMULATED_ORDERS_ONLY';common_namespace=$PrefixBase;real_broker_orders_authorized=$false;real_broker_orders_sent=0;active_terminal_touched=$false;v223_cert_rule='KEEP_QDB1_EXEC_CERT_0';deployment_allowed=$false;cert_arm_allowed=$false;blockers=@('REAL_DARWINEX_CTRADE_PARTIAL_FILL_AND_NETWORK_LOST_ACK_NOT_FORCEABLE_IN_LOCAL_TESTER','REAL_DARWINEX_MODIFY_CLOSE_REJECTION_AND_RECONNECT_GATE_REMAINS_SEPARATE','DST_OFFSET_TRANSITION_AND_AUTHORITATIVE_SESSION_CLOSE_LEAD_REMAIN_EXTERNAL',$(if($restartState -like 'BLOCKED*'){'FULL_REAL_TERMINAL_RESTART_WITH_BROKER_INVENTORY_REMAINS_EXTERNAL'}else{'REAL_TERMINAL_RESTART_WITH_LIVE_DEMO_INVENTORY_REMAINS_EXTERNAL'}));next_gate='CONTROLLED_DARWINEX_DEMO_BROKER_ADVERSARIAL_MICRO_GATE_REQUIRES_SEPARATE_EXPLICIT_ORDER_AUTHORIZATION'}
$receiptPath=Join-Path $Ev 'QROS_V224_C3_NATIVE_RUNTIME_PHASEA_RECEIPT_v2_0.json'
$receipt|ConvertTo-Json -Depth 12|Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Q 'PASS_WITH_EXTERNAL_BLOCKERS Phase-A native runtime gate v2.0 complete';Write-Q 'NO deployment / NO active CERT changes / NO real broker orders'
$z=Zip-Evidence;if(!$z){Fail 'EVIDENCE_ZIP_FAILED' 80};$zsha=Sha $z;$script:Success=$true;$script:ExitCode=0
Write-Host "";Write-Host "============================================================";Write-Host "QROS V224 Candidate3 Native Runtime Phase-A v2.0: PASS_WITH_EXTERNAL_BLOCKERS";Write-Host "Run ID: $RunId";Write-Host "Evidence: $z";Write-Host "SHA-256: $zsha";Write-Host "Next: upload this evidence ZIP to ChatGPT.";Write-Host "Do NOT enable QDB1.EXEC.CERT. Do NOT deploy Candidate3.";Write-Host "============================================================"

} catch {
  $reason=$_.Exception.Message;$code=99
  try{if($_.Exception.Data.Contains('QROS_CODE')){$code=[int]$_.Exception.Data['QROS_CODE']}}catch{}
  try{Write-Q ("FAIL "+$reason+" code="+$code)}catch{}
  try{Capture-Diagnostics ('FAIL_'+($reason -replace '[^A-Za-z0-9_.-]','_')) $IsoA}catch{}
  try{Cleanup-Owned}catch{};try{Snapshot-ActiveAfter}catch{}
  $fr=[ordered]@{schema=$Schema;utc=(Get-Date).ToUniversalTime().ToString('o');run_id=$RunId;decision='FAIL';reason=$reason;code=$code;candidate='QROS_DARWINEX_DEMO_V224_CANDIDATE3';candidate_state='FROZEN_CANDIDATE';classification=$(if($reason -like 'RUNTIME_NATIVE_FAIL_*' -or $reason -like 'RUNTIME_MANDATORY_NOT_PASS_*'){'CANDIDATE_OR_NATIVE_RUNTIME_FAILURE'}else{'RUNNER_OR_GATE_INFRASTRUCTURE_FAILURE'});native_tester_only=$true;real_broker_orders_authorized=$false;real_broker_orders_sent=0;active_terminal_touched=$false;deployment_allowed=$false;cert_arm_allowed=$false;v223_cert_rule='KEEP_QDB1_EXEC_CERT_0'}
  try{$fr|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $Ev 'QROS_V224_C3_NATIVE_RUNTIME_PHASEA_RECEIPT_v2_0.json') -Encoding UTF8}catch{}
  $z=$null;try{$z=Zip-Evidence}catch{}
  if($z){try{Write-Host "Evidence: $z";Write-Host "SHA-256: $(Sha $z)"}catch{}}else{Write-Host "Evidence ZIP could not be created; inspect $Ev"}
  $script:ExitCode=$code
}
exit $script:ExitCode
