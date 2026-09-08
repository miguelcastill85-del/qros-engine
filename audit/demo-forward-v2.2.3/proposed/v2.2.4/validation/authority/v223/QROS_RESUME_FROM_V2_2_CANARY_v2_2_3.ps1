param(
 [string]$TerminalExe="C:\Program Files\Darwinex MetaTrader 5\terminal64.exe",
 [string]$MetaEditorExe="C:\Program Files\Darwinex MetaTrader 5\metaeditor64.exe",
 [string]$DataPath="C:\Users\makk7\AppData\Roaming\MetaQuotes\Terminal\6C3C6A11D1C3791DD4DBF45421BF8028"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$ProfileName="QROS_DEMO_RUNTIME_V2_2"
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$PriorOut="C:\QROS_DARWINEX_DEMO_RUNTIME_V2_2"
$PriorEv=Join-Path $PriorOut "EVIDENCE"
$Out="C:\QROS_DARWINEX_DEMO_RUNTIME_V2_2_3"
$Ev=Join-Path $Out "EVIDENCE"
$Logs=Join-Path $Ev "COMPILE_LOGS"
$Common="$env:APPDATA\MetaQuotes\Terminal\Common\Files"

New-Item -ItemType Directory -Force -Path $Out,$Ev,$Logs | Out-Null
$RunLog=Join-Path $Ev "QROS_DEPLOYMENT_RUNTIME_V2_2_3_RESUME.log"
if(Test-Path $RunLog){Remove-Item $RunLog -Force}

function Write-QrosLog([string]$m){
 $s="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $m"
 Write-Host $s
 Add-Content -LiteralPath $RunLog -Value $s -Encoding UTF8
}

function Get-QrosSha([string]$p){
 (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()
}

function StopQ($p){
 if($null -eq $p){return}
 try{
   if(!$p.HasExited){
     try{$p.CloseMainWindow()|Out-Null}catch{}
     $p.WaitForExit(8000)|Out-Null
     if(!$p.HasExited){
       Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
     }
   }
 }catch{}
}

function Capture([string]$tag){
 $d=Join-Path $Ev ("RUNTIME_LOGS_"+$tag)
 New-Item -ItemType Directory -Force -Path $d | Out-Null
 foreach($r in @((Join-Path $DataPath "MQL5\Logs"),(Join-Path $DataPath "Logs"))){
   if(Test-Path $r){
     Get-ChildItem $r -File -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending |
       Select-Object -First 10 |
       ForEach-Object{
         Copy-Item $_.FullName (Join-Path $d $_.Name) -Force -ErrorAction SilentlyContinue
       }
   }
 }
}

function Bundle-QrosEvidence {
 $zip=Join-Path $Out "QROS_DEPLOYMENT_RUNTIME_V2_2_3_EVIDENCE.zip"
 try{
   if(Test-Path $zip){Remove-Item $zip -Force}
   Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
   [System.IO.Compression.ZipFile]::CreateFromDirectory(
      $Ev,$zip,[System.IO.Compression.CompressionLevel]::Optimal,$false)
   Write-QrosLog "EVIDENCE_BUNDLE=$zip"
 }catch{
   Write-QrosLog ("EVIDENCE_BUNDLE_FAILED="+$_.Exception.Message)
 }
}

function Fail([string]$reason,[int]$code,$proc=$null){
 if($null-ne$proc){StopQ $proc}
 Write-QrosLog "FAIL $reason"
 Capture "FAIL"
 $r=[ordered]@{
   schema="QROS_DEPLOYMENT_RUNTIME_V2_2_3_RECEIPT_1.0"
   decision="FAIL"
   reason=$reason
   utc=(Get-Date).ToUniversalTime().ToString("o")
   demo_forward_active=$false
 }
 $r|ConvertTo-Json -Depth 12 |
   Set-Content -LiteralPath (Join-Path $Ev "QROS_DEPLOYMENT_RUNTIME_V2_2_3_RECEIPT.json") -Encoding UTF8
 Bundle-QrosEvidence
 exit $code
}

function StartQ([string]$ini,[bool]$profile=$true){
 $a=@()
 if($profile){$a+=("/profile:"+$ProfileName)}
 $a+=("/config:`"$ini`"")
 Start-Process $TerminalExe -ArgumentList $a -PassThru
}

function Read-QrosCsvLastShared([string]$Path,[int]$Attempts=30,[int]$DelayMs=100){
 for($i=0;$i-lt$Attempts;$i++){
   if(Test-Path -LiteralPath $Path){
     try{
       $fs=[System.IO.File]::Open(
         $Path,
         [System.IO.FileMode]::Open,
         [System.IO.FileAccess]::Read,
         [System.IO.FileShare]::ReadWrite
       )
       try{
         $sr=New-Object System.IO.StreamReader($fs,[System.Text.Encoding]::UTF8,$true)
         try{$text=$sr.ReadToEnd()}finally{$sr.Dispose()}
       }finally{
         if($null-ne$fs){$fs.Dispose()}
       }

       if(-not [string]::IsNullOrWhiteSpace($text)){
         try{
           $rows=@($text | ConvertFrom-Csv)
           if(@($rows).Count-gt0){
             $last=$rows[-1]
             if($null-ne$last -and
                $last.PSObject.Properties.Name -contains "decision" -and
                $last.PSObject.Properties.Name -contains "reason"){
               return $last
             }
           }
         }catch{}
       }
     }catch{}
   }
   Start-Sleep -Milliseconds $DelayMs
 }
 return $null
}

function Copy-QrosSharedFile([string]$Source,[string]$Destination){
 for($i=0;$i-lt50;$i++){
   try{
     $fs=[System.IO.File]::Open(
       $Source,
       [System.IO.FileMode]::Open,
       [System.IO.FileAccess]::Read,
       [System.IO.FileShare]::ReadWrite
     )
     try{
       $out=[System.IO.File]::Open(
         $Destination,
         [System.IO.FileMode]::Create,
         [System.IO.FileAccess]::Write,
         [System.IO.FileShare]::Read
       )
       try{$fs.CopyTo($out)}finally{$out.Dispose()}
     }finally{$fs.Dispose()}
     return
   }catch{
     Start-Sleep -Milliseconds 100
   }
 }
 Fail ("COPY_SHARED_FAILED_"+[IO.Path]::GetFileName($Source)) 112
}

function Import-ClosedCsvLast([string]$Path){
 if(!(Test-Path -LiteralPath $Path)){return $null}
 try{
   $rows=@(Import-Csv -LiteralPath $Path)
   if(@($rows).Count-lt1){return $null}
   return $rows[-1]
 }catch{
   return $null
 }
}

function Assert-CompileLog([string]$Path){
 if(!(Test-Path -LiteralPath $Path)){Fail ("PRIOR_COMPILE_LOG_MISSING_"+[IO.Path]::GetFileName($Path)) 120}
 $txt=Get-Content -LiteralPath $Path -Raw
 if($txt-notmatch"Result:\s*0 errors,\s*0 warnings"){
   Fail ("PRIOR_COMPILE_NOT_0_0_"+[IO.Path]::GetFileName($Path)) 121
 }
}

function EqPrior([string]$A,[string]$B,[string]$Tag){
 $pa=Join-Path $PriorEv $A
 $pb=Join-Path $PriorEv $B
 if(!(Test-Path $pa)-or!(Test-Path $pb)){Fail ("PRIOR_PARITY_OUTPUT_"+$Tag) 122}
 $ha=Get-QrosSha $pa
 $hb=Get-QrosSha $pb
 if($ha-ne$hb){Fail ("PRIOR_PARITY_HASH_"+$Tag) 123}
 return [ordered]@{tag=$Tag;sha256=$ha}
}

Write-QrosLog "START RUNTIME V2.2.3 RESUME FROM VERIFIED V2.2 CHECKPOINT"

if(!(Test-Path $TerminalExe)){Fail "TERMINAL_NOT_FOUND" 10}
if(!(Test-Path $MetaEditorExe)){Fail "METAEDITOR_NOT_FOUND" 11}
if(!(Test-Path $DataPath)){Fail "DATA_PATH_NOT_FOUND" 12}
if(!(Test-Path $PriorEv)){Fail "PRIOR_V22_EVIDENCE_DIR_MISSING" 13}

# Close ONLY the prior QROS canary/runtime terminal left by the unhandled Import-Csv race.
$running=Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" -ErrorAction SilentlyContinue
if($running){
 $foreign=@()
 foreach($r in @($running)){
   $cmd=[string]$r.CommandLine
   if($cmd-match"QROS_DARWINEX_DEMO_RUNTIME_V2_2" -or
      $cmd-match"QROS_V2_RUNTIME_CANARY" -or
      $cmd-match"CANARY\.ini"){
     Write-QrosLog "CLOSING PRIOR QROS TERMINAL pid=$($r.ProcessId)"
     try{
       Stop-Process -Id ([int]$r.ProcessId) -Force -ErrorAction Stop
       Start-Sleep -Seconds 2
     }catch{
       Fail "PRIOR_QROS_TERMINAL_CLOSE_FAILED" 14
     }
   }else{
     $foreign+=$r
   }
 }
 if(@($foreign).Count-gt0){Fail "UNRELATED_MT5_RUNNING" 15}
}

# No START_RECEIPT may exist from v2.2. Screenshot/error occurred immediately after CANARY START.
$priorStart=Join-Path $PriorEv "QROS_THREE_MODULE_DEMO_FORWARD_START_RECEIPT_v2.json"
if(Test-Path $priorStart){Fail "UNEXPECTED_PRIOR_START_RECEIPT_EXISTS" 16}

# Reverify package authority 7/7.
$Auth=@{
 "QROS_XAU_M1_PDH_200S_SHADOW_v15700.mq5"="38a6da8ebe548b080c98c63592129e89aa5ed7fcd49324802e10597d2bfa5e72";
 "QROS_NQX_MULTISCALE_17_31_SHADOW_v15700.mq5"="d70cae24eec9154c9b0029b4d90b1515a92ab3b39f3a8541db88664270ea4f6b";
 "QROS_DIV3_NQX_PARITY_HARNESS_v1.mq5"="035d45e4e74cc6fcfbfd5da34533fd12ffbddcb7ad657d38ac678a18b45fd20c";
 "QROS_DIV3_PORTFOLIO_CONTROLLER_PARITY_v2.mq5"="2d6ebd5082ade0e5ec90fd0265d27d61d90c7bd384ce057c18ad9c6f1ef09035";
 "QROS_RISK_KERNEL_APPROVED_v15420.mqh"="8af000aac09747b896cef4e8c9263aaf675dab4fefa07b3d9d4b7c1c170ab49f";
 "QROS_DIV3_PORTFOLIO_CONTROLLER_CANDIDATES_v2.csv"="82ff86d765c19bc621ea3d947258729d833c382c6c31d2469aedb529222523b1";
 "QROS_DIV3_PORTFOLIO_CONTROLLER_RESULT_v2.csv"="b8d28b09c6e8783a872fd1bbb59c65d7463fa62d386ebeda7f4f03282ed29e46"
}
foreach($n in $Auth.Keys){
 $p=Join-Path (Join-Path $Here "AUTHORITY") $n
 if(!(Test-Path $p)){Fail ("AUTH_MISSING_"+$n) 20}
 if((Get-QrosSha $p)-ne$Auth[$n]){Fail ("AUTH_HASH_"+$n) 21}
}
Write-QrosLog "AUTHORITY 7/7 REVERIFIED"

# Reverify the exact v2.2 completed checkpoint from local evidence.
$priorLog=Join-Path $PriorEv "QROS_DEPLOYMENT_RUNTIME_V2_2.log"
if(!(Test-Path $priorLog)){Fail "PRIOR_V22_LOG_MISSING" 30}
$plog=Get-Content $priorLog -Raw

$requiredLogLines=@(
 "AUTHORITY 7/7 PASS",
 "COMPILE 12/12 PASS",
 "CONTROLLER PARITY PASS canonical 977",
 "CURRENT BUILD PARITY PASS",
 "PRELOAD PASS",
 "FORWARD MODULE CERT PASS XAU",
 "FORWARD MODULE CERT PASS NQX",
 "FORWARD MODULE CERT PASS DIV3",
 "CANARY START orders disabled"
)
foreach($line in $requiredLogLines){
 if($plog-notmatch[regex]::Escape($line)){Fail ("PRIOR_CHECKPOINT_LOG_MISSING_"+$line.Replace(" ","_")) 31}
}

if($plog-match"START_RECEIPT MATERIALIZED"){Fail "PRIOR_LOG_SHOWS_START_RECEIPT" 32}

$buildMatch=[regex]::Match($plog,"CURRENT BUILD PARITY PASS build=(\d+) comparisons=8")
if(!$buildMatch.Success){Fail "PRIOR_BUILD_NOT_RESOLVED" 33}
$Build=[int]$buildMatch.Groups[1].Value

$compileNames=@(
 "QROS_XAU_M1_PDH_200S_SHADOW_v15700.mq5",
 "QROS_NQX_MULTISCALE_17_31_SHADOW_v15700.mq5",
 "QROS_DIV3_NQX_PARITY_HARNESS_v1.mq5",
 "QROS_DIV3_PORTFOLIO_CONTROLLER_PARITY_v2.mq5",
 "QROS_XAU_M1_DEMO_EMITTER_v2.mq5",
 "QROS_NQX_17_31_DEMO_EMITTER_v2.mq5",
 "QROS_DIV3_R3_DEMO_EMITTER_v2_1.mq5",
 "QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5",
 "QROS_V2_PROFILE_PROBE.mq5",
 "QROS_V2_HISTORY_PRELOAD.mq5",
 "QROS_V21_MODULE_CERTIFY.mq5",
 "QROS_V21_RUNTIME_BOOTSTRAP.mq5"
)
foreach($n in $compileNames){
 Assert-CompileLog (Join-Path (Join-Path $PriorEv "COMPILE_LOGS") ($n+".log"))
}
Write-QrosLog "PRIOR COMPILE 12/12 REVERIFIED"

$parity=@()
$parity+=EqPrior "QROS_V2_PARITY_XAU_PARENT_TRADES_v15700.csv" "QROS_V2_PARITY_XAU_CHILD_TRADES_v15700.csv" "XAU_TRADES"
$parity+=EqPrior "QROS_V2_PARITY_XAU_PARENT_EVENTS_v15700.csv" "QROS_V2_PARITY_XAU_CHILD_EVENTS_v15700.csv" "XAU_EVENTS"
$parity+=EqPrior "QROS_V2_PARITY_NQX_PARENT_TRADES_v15700.csv" "QROS_V2_PARITY_NQX_CHILD_TRADES_v15700.csv" "NQX_TRADES"
$parity+=EqPrior "QROS_V2_PARITY_NQX_PARENT_CANDIDATES_v15700.csv" "QROS_V2_PARITY_NQX_CHILD_CANDIDATES_v15700.csv" "NQX_CANDIDATES"
$parity+=EqPrior "QROS_V2_PARITY_DIV3_PARENT_SIGNALS.csv" "QROS_V2_PARITY_DIV3_CHILD_SIGNALS.csv" "DIV3_SIGNALS"
$parity+=EqPrior "QROS_V2_PARITY_DIV3_PARENT_TRADES.csv" "QROS_V2_PARITY_DIV3_CHILD_TRADES.csv" "DIV3_TRADES"
$parity+=EqPrior "QROS_V2_PARITY_DIV3_PARENT_SUMMARY.csv" "QROS_V2_PARITY_DIV3_CHILD_SUMMARY.csv" "DIV3_SUMMARY"
Write-QrosLog "PRIOR MODULE PARITY 7/7 REVERIFIED"

$ctrl=Join-Path $PriorEv "QROS_V2_CONTROLLER_RESULT.csv"
if(!(Test-Path $ctrl)){Fail "PRIOR_CONTROLLER_RESULT_MISSING" 34}
if((Get-QrosSha $ctrl)-ne"b8d28b09c6e8783a872fd1bbb59c65d7463fa62d386ebeda7f4f03282ed29e46"){
 Fail "PRIOR_CONTROLLER_HASH_MISMATCH" 35
}
Write-QrosLog "PRIOR CONTROLLER 977 REVERIFIED"

$prof=Import-ClosedCsvLast (Join-Path $PriorEv "QROS_V2_PROFILE_PROBE.csv")
if($null-eq$prof -or $prof.decision-ne"PASS" -or [int]$prof.expert_count-ne0){
 Fail "PRIOR_PROFILE_PROBE_INVALID" 36
}

$m15=Import-ClosedCsvLast (Join-Path $PriorEv "QROS_V2_PRELOAD_M15.csv")
$h1=Import-ClosedCsvLast (Join-Path $PriorEv "QROS_V2_PRELOAD_H1.csv")

function Assert-PriorPreload(
 [object]$Row,
 [string]$Tag,
 [string]$ExpectedStart,
 [long]$MinBars,
 [int]$FailCode
){
 if($null-eq$Row){
   Fail ("PRIOR_"+$Tag+"_PRELOAD_MISSING") $FailCode
 }

 # Reverify exactly the gate V2.2 used when this checkpoint was created.
 if($Row.decision-ne"PASS" -or $Row.reason-ne"HISTORY_CACHE_READY"){
   Fail ("PRIOR_"+$Tag+"_PRELOAD_DECISION") $FailCode
 }

 if([string]$Row.requested_start-ne$ExpectedStart){
   Fail ("PRIOR_"+$Tag+"_PRELOAD_START") $FailCode
 }

 if([long]$Row.bars_total-lt$MinBars -or [int]$Row.chunks-lt1){
   Fail ("PRIOR_"+$Tag+"_PRELOAD_COVERAGE") $FailCode
 }

 if([string]::IsNullOrWhiteSpace([string]$Row.first) -or
    [string]::IsNullOrWhiteSpace([string]$Row.last)){
   Fail ("PRIOR_"+$Tag+"_PRELOAD_RANGE") $FailCode
 }

 $syncObserved=-1
 if($Row.PSObject.Properties.Name -contains "series_synchronized"){
   try{$syncObserved=[int]$Row.series_synchronized}catch{$syncObserved=-1}
 }

 Write-QrosLog ("PRIOR "+$Tag+" PRELOAD REVERIFIED bars="+
                [string]$Row.bars_total+
                " start="+[string]$Row.requested_start+
                " sync_observed="+[string]$syncObserved+
                " -- sync/currentness is re-certified prospectively in canary")
}

Assert-PriorPreload $m15 "M15" "2018.01.25 00:00" 100000 37
Assert-PriorPreload $h1  "H1"  "2025.01.01 00:00"   5000 38

foreach($tag in @("XAU","NQX","DIV3")){
 $r=Import-ClosedCsvLast (Join-Path $PriorEv ("QROS_V2_CERT_"+$tag+".csv"))
 if($null-eq$r -or $r.decision-ne"PASS" -or [int]$r.state-ne2 -or [int]$r.saved-ne1){
   Fail ("PRIOR_MODULE_CERT_INVALID_"+$tag) 39
 }
}
Write-QrosLog "PRIOR FORWARD CERT XAU/NQX/DIV3 REVERIFIED"

# Verify local unchanged runtime sources and binaries. Do not recompile completed components.
$Experts=Join-Path $DataPath "MQL5\Experts"
$Scripts=Join-Path $DataPath "MQL5\Scripts"
$Include=Join-Path $DataPath "MQL5\Include"
$Presets=Join-Path $DataPath "MQL5\Presets"

$runtimeSourceNames=@(
 "QROS_XAU_M1_DEMO_EMITTER_v2.mq5",
 "QROS_NQX_17_31_DEMO_EMITTER_v2.mq5",
 "QROS_DIV3_R3_DEMO_EMITTER_v2_1.mq5",
 "QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5"
)
foreach($n in $runtimeSourceNames){
 $pkg=Join-Path (Join-Path $Here "MQL5\Experts") $n
 $local=Join-Path $Experts $n
 $ex5=Join-Path $Experts ($n.Substring(0,$n.Length-4)+".ex5")
 if(!(Test-Path $local)){Fail ("LOCAL_RUNTIME_SOURCE_MISSING_"+$n) 40}
 if((Get-QrosSha $local)-ne(Get-QrosSha $pkg)){Fail ("LOCAL_RUNTIME_SOURCE_HASH_"+$n) 41}
 if(!(Test-Path $ex5)){Fail ("LOCAL_RUNTIME_BINARY_MISSING_"+$n) 42}
}

foreach($n in @("QROS_DEMO_BUS_v2.mqh","QROS_RISK_KERNEL_APPROVED_v15420.mqh")){
 $pkg=Join-Path (Join-Path $Here "MQL5\Include") $n
 $local=Join-Path $Include $n
 if(!(Test-Path $local)){Fail ("LOCAL_INCLUDE_MISSING_"+$n) 43}
 if((Get-QrosSha $local)-ne(Get-QrosSha $pkg)){Fail ("LOCAL_INCLUDE_HASH_"+$n) 44}
}

# Verify native templates created by the completed v2.2 module certifications.
$TemplateRoot=Join-Path $DataPath "MQL5\Profiles\Templates"
$templateHashes=@{}
foreach($name in @("QROS_V2_XAU_NATIVE.tpl","QROS_V2_NQX_NATIVE.tpl","QROS_V2_DIV3_NATIVE.tpl")){
 $tp=Join-Path $TemplateRoot $name
 if(!(Test-Path $tp)){Fail ("RESUME_TEMPLATE_MISSING_"+$name) 45}
 $templateHashes[$name]=Get-QrosSha $tp
}

# Reuse the clean profile baseline created and proven during v2.2.
$ProfilesRoot=Join-Path $DataPath "MQL5\Profiles\Charts"
$Qros=Join-Path $ProfilesRoot $ProfileName
$Base=Join-Path $ProfilesRoot ($ProfileName+"_BASELINE")
if(!(Test-Path $Base)){Fail "PRIOR_PROFILE_BASELINE_MISSING" 46}

function ResetProfile{
 if(Get-Process terminal64 -ErrorAction SilentlyContinue){Fail "RESET_WHILE_MT5_RUNNING" 47}
 if(Test-Path $Qros){Remove-Item $Qros -Recurse -Force}
 Copy-Item $Base $Qros -Recurse -Force
}

# Copy only the changed bootstrap and its two new presets, then compile only that bootstrap.
Copy-Item (Join-Path $Here "MQL5\Scripts\QROS_V223_RUNTIME_BOOTSTRAP.mq5") $Scripts -Force
Copy-Item (Join-Path $Here "MQL5\Presets\QROS_V223_BOOT_CANARY.set") $Presets -Force
Copy-Item (Join-Path $Here "MQL5\Presets\QROS_V223_BOOT_ARMED.set") $Presets -Force

$bootSrc=Join-Path $Scripts "QROS_V223_RUNTIME_BOOTSTRAP.mq5"
$bootLog=Join-Path $Logs "QROS_V223_RUNTIME_BOOTSTRAP.mq5.log"
if(Test-Path $bootLog){Remove-Item $bootLog -Force}
$p=Start-Process $MetaEditorExe -ArgumentList "/compile:`"$bootSrc`"","/log:`"$bootLog`"" -Wait -PassThru
if(!(Test-Path $bootLog)){Fail "V223_BOOTSTRAP_COMPILE_LOG_MISSING" 50}
$bootText=Get-Content $bootLog -Raw
if($bootText-notmatch"Result:\s*0 errors,\s*0 warnings"){Fail "V223_BOOTSTRAP_COMPILE_NOT_0_0" 51}
Write-QrosLog "PATCH COMPILE PASS QROS_V223_RUNTIME_BOOTSTRAP.mq5 identity=DIV3_v2_1"

# Materialize the reused-checkpoint receipt before canary.
$reusedFiles=@()
foreach($p in @(
 $priorLog,
 (Join-Path $PriorEv "QROS_V2_PROFILE_PROBE.csv"),
 (Join-Path $PriorEv "QROS_V2_PRELOAD_M15.csv"),
 (Join-Path $PriorEv "QROS_V2_PRELOAD_H1.csv"),
 (Join-Path $PriorEv "QROS_V2_CERT_XAU.csv"),
 (Join-Path $PriorEv "QROS_V2_CERT_NQX.csv"),
 (Join-Path $PriorEv "QROS_V2_CERT_DIV3.csv"),
 $ctrl
)){
 $reusedFiles += [ordered]@{file=$p;sha256=Get-QrosSha $p}
}

$checkpoint=[ordered]@{
 schema="QROS_DEPLOYMENT_RUNTIME_V2_2_REUSED_CHECKPOINT_1.0"
 verified_utc=(Get-Date).ToUniversalTime().ToString("o")
 source_runtime="V2.2"
 terminal_build=$Build
 authority="7/7 PASS"
 compile="12/12 PASS"
 module_parity=$parity
 controller="canonical 977 PASS"
 profile_probe="PASS zero experts"
 preload_m15=[ordered]@{
   decision=$m15.decision
   reason=$m15.reason
   requested_start=$m15.requested_start
   bars_total=[long]$m15.bars_total
   series_synchronized_observed=[int]$m15.series_synchronized
   sync_gate="PROSPECTIVE_CANARY"
 }
 preload_h1=[ordered]@{
   decision=$h1.decision
   reason=$h1.reason
   requested_start=$h1.requested_start
   bars_total=[long]$h1.bars_total
   series_synchronized_observed=[int]$h1.series_synchronized
   sync_gate="PROSPECTIVE_CANARY"
 }
 module_cert="XAU PASS; NQX PASS; DIV3 PASS"
 prior_start_receipt_exists=$false
 prior_demo_forward_active=$false
 changed_component="QROS_V223_RUNTIME_BOOTSTRAP.mq5 only; corrected DIV3 runtime identity v2 -> v2_1"
 changed_component_compile="0 errors / 0 warnings"
 template_hashes=$templateHashes
 reused_files=$reusedFiles
}
$checkpointPath=Join-Path $Ev "QROS_V22_REUSED_CHECKPOINT.json"
$checkpoint|ConvertTo-Json -Depth 20 |
 Set-Content -LiteralPath $checkpointPath -Encoding UTF8
$checkpointSha=Get-QrosSha $checkpointPath
Write-QrosLog "V2.2 CHECKPOINT REUSED sha=$checkpointSha"

# ---------- CANARY ONLY ----------
ResetProfile
$can=Join-Path $Common "QROS_V223_RUNTIME_CANARY.csv"
if(Test-Path $can){Remove-Item $can -Force}
$ini=Join-Path $Ev "CANARY_V223.ini"
@"
[Charts]
MaxBars=1000000
[Experts]
AllowLiveTrading=0
AllowDllImport=0
Enabled=1
[StartUp]
Expert=QROS_DEMO_PORTFOLIO_EXECUTOR_v2
ExpertParameters=QROS_V2_EXEC_UNARMED.set
Script=QROS_V223_RUNTIME_BOOTSTRAP
ScriptParameters=QROS_V223_BOOT_CANARY.set
Symbol=XAUUSD
Period=M1
ShutdownTerminal=0
"@ | Set-Content -LiteralPath $ini -Encoding ASCII

Write-QrosLog "CANARY V2.2.3 START orders disabled"
$cp=StartQ $ini $true
$deadline=(Get-Date).AddSeconds(21660)
$c=$null

$lastCanaryReason=""
while((Get-Date)-lt$deadline){
 $snap=Read-QrosCsvLastShared $can 8 100
 if($null-ne$snap){
   $c=$snap
   if([string]$c.reason-ne$lastCanaryReason){
     Write-QrosLog ("CANARY STATE decision="+[string]$c.decision+
                    " reason="+[string]$c.reason+
                    " xau_state="+[string]$c.xau_state+
                    " nqx_state="+[string]$c.nqx_state+
                    " div3_state="+[string]$c.div3_state+
                    " xau_sync="+[string]$c.xau_m1_sync_flag+
                    " m15_sync="+[string]$c.ndx_m15_sync_flag+
                    " h1_sync="+[string]$c.ndx_h1_sync_flag)
     $lastCanaryReason=[string]$c.reason
   }
   if($c.decision-eq"PASS"){break}
   if($c.decision-eq"FAIL"){
     try{Copy-QrosSharedFile $can (Join-Path $Ev "QROS_V223_RUNTIME_CANARY_LAST.csv")}catch{}
     Fail ("CANARY_"+$c.reason) 80 $cp
   }
 }
 if($cp.HasExited -and !(Test-Path $can)){Fail "CANARY_EXIT_NO_RECEIPT" 81 $cp}
 Start-Sleep -Milliseconds 500
}

if($null-eq$c -or $c.decision-ne"PASS"){
 try{if(Test-Path $can){Copy-QrosSharedFile $can (Join-Path $Ev "QROS_V223_RUNTIME_CANARY_LAST.csv")}}catch{}
 $lastReason=if($null-ne$c){[string]$c.reason}else{"NO_SNAPSHOT"}
 Fail ("CANARY_TIMEOUT_LAST_"+$lastReason) 82 $cp
}
if([int]$c.executor_armed-ne0 -or [int]$c.cert-ne0){Fail "CANARY_INVARIANT" 83 $cp}
if([int]$c.build-ne$Build){Fail "RUNTIME_BUILD_DIFFERS_FROM_PARITY_BUILD" 84 $cp}

# Stop canary only after PASS and preserve exact final snapshot.
StopQ $cp
Copy-QrosSharedFile $can (Join-Path $Ev "QROS_V223_RUNTIME_CANARY.csv")
Write-QrosLog "CANARY V2.2.3 PASS build=$($c.build) offset=$($c.utc_offset_sec)"

# START_RECEIPT must exist before armed terminal launch.
$start=[ordered]@{
 schema="QROS_THREE_MODULE_DEMO_FORWARD_START_RECEIPT_2.2.3"
 created_utc=(Get-Date).ToUniversalTime().ToString("o")
 status="START_AUTHORIZED_PENDING_ARMED_RUNTIME_CERTIFICATION"
 reused_checkpoint=$checkpointPath
 reused_checkpoint_sha256=$checkpointSha
 server=$c.server
 currency=$c.currency
 trade_mode=[int]$c.trade_mode
 login=[long]$c.login
 terminal_build=$Build
 current_build_parity="7/7 module outputs + controller canonical 977 PASS; reused from verified V2.2 checkpoint"
 individual_forward_cert="XAU PASS; NQX PASS; DIV3 PASS; reused from verified V2.2 checkpoint"
 combined_canary="PASS V2.2.3"
 bootstrap_patch="V2.2.3 exact DIV3 identity fix: runtime expected QROS_DIV3_R3_DEMO_EMITTER_v2_1; shared CSV race fix and prospective sync/currentness retained"
 risk_one_R_pct_balance=0.50
 max_reserved_risk_pct_balance=1.00
 max_new_entries_per_server_day=3
 one_position_per_asset=$true
 no_simultaneous_entries_same_timestamp=$true
 no_overnight=$true
 buy_entry="ASK"
 buy_exit_observation="BID"
 ambiguous_sl_tp="SL_FIRST"
 gap_fill="FIRST_EXECUTABLE_PRICE"
 zero_or_crossed_spread_fill="FORBIDDEN"
 orders_sent_before_start=0
 runtime_cert_latch="QDB1.EXEC.CERT"
 live_account_authorized=$false
 demo_only=$true
 g30_mutated=$false
}
$sp=Join-Path $Ev "QROS_THREE_MODULE_DEMO_FORWARD_START_RECEIPT_v2_2_3.json"
$start|ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $sp -Encoding UTF8
$ssh=Get-QrosSha $sp
Write-QrosLog "START_RECEIPT MATERIALIZED BEFORE ARMED LAUNCH sha=$ssh"

# ---------- ARMED RUNTIME ----------
ResetProfile
$armed=Join-Path $Common "QROS_V223_RUNTIME_ARMED.csv"
if(Test-Path $armed){Remove-Item $armed -Force}
$aini=Join-Path $Ev "ARMED_V223.ini"
@"
[Charts]
MaxBars=1000000
[Experts]
AllowLiveTrading=1
AllowDllImport=0
Enabled=1
[StartUp]
Expert=QROS_DEMO_PORTFOLIO_EXECUTOR_v2
ExpertParameters=QROS_V2_EXEC_ARMED.set
Script=QROS_V223_RUNTIME_BOOTSTRAP
ScriptParameters=QROS_V223_BOOT_ARMED.set
Symbol=XAUUSD
Period=M1
ShutdownTerminal=0
"@ | Set-Content -LiteralPath $aini -Encoding ASCII

Write-QrosLog "ARMED V2.2.3 START -- CERT LATCH 0 UNTIL RUNTIME PASS"
$ap=StartQ $aini $true
$deadline=(Get-Date).AddSeconds(960)
$a=$null

$lastArmedReason=""
while((Get-Date)-lt$deadline){
 $snap=Read-QrosCsvLastShared $armed 8 100
 if($null-ne$snap){
   $a=$snap
   if([string]$a.reason-ne$lastArmedReason){
     Write-QrosLog ("ARMED STATE decision="+[string]$a.decision+
                    " reason="+[string]$a.reason+
                    " cert="+[string]$a.cert)
     $lastArmedReason=[string]$a.reason
   }
   if($a.decision-eq"PASS"){break}
   if($a.decision-eq"FAIL"){
     try{Copy-QrosSharedFile $armed (Join-Path $Ev "QROS_V223_RUNTIME_ARMED_LAST.csv")}catch{}
     Fail ("ARMED_"+$a.reason) 90 $ap
   }
 }
 if($ap.HasExited -and !(Test-Path $armed)){Fail "ARMED_EXIT_NO_RECEIPT" 91 $ap}
 Start-Sleep -Milliseconds 500
}

if($null-eq$a -or $a.decision-ne"PASS"){
 try{if(Test-Path $armed){Copy-QrosSharedFile $armed (Join-Path $Ev "QROS_V223_RUNTIME_ARMED_LAST.csv")}}catch{}
 $lastReason=if($null-ne$a){[string]$a.reason}else{"NO_SNAPSHOT"}
 Fail ("ARMED_TIMEOUT_LAST_"+$lastReason) 92 $ap
}
if([int]$a.executor_armed-ne1 -or [int]$a.cert-ne1){Fail "ARMED_CERT_INVARIANT" 93 $ap}
if([int]$a.build-ne$Build){Fail "ARMED_BUILD_DRIFT" 94 $ap}

Copy-QrosSharedFile $armed (Join-Path $Ev "QROS_V223_RUNTIME_ARMED.csv")

$final=[ordered]@{
 schema="QROS_DEPLOYMENT_RUNTIME_V2_2_3_RECEIPT_1.0"
 completed_utc=(Get-Date).ToUniversalTime().ToString("o")
 decision="DEMO_FORWARD_ACTIVE"
 start_receipt=$sp
 start_receipt_sha256=$ssh
 reused_checkpoint_sha256=$checkpointSha
 terminal_build=$Build
 server=$a.server
 currency=$a.currency
 trade_mode=[int]$a.trade_mode
 login=[long]$a.login
 executor_armed=$true
 runtime_certified=$true
 modules="XAU READY; NQX READY; DIV3 READY"
 current_build_parity="PASS via verified V2.2 checkpoint"
 controller_parity="PASS canonical 977 via verified V2.2 checkpoint"
 fresh_ticks="PASS"
 functional_series_current="XAU M1; NDX M15; NDX H1"
 risk_one_R_pct_balance=0.50
 max_reserved_risk_pct_balance=1.00
 daily_new_entry_cap=3
 terminal_pid=$ap.Id
 terminal_left_running=$true
 live_account_authorized=$false
 demo_only=$true
 g30_mutated=$false
 next_gate="90 calendar days + >=50 closed portfolio trades + >=3/module + 100% reconciliation"
}
$fp=Join-Path $Ev "QROS_DEPLOYMENT_RUNTIME_V2_2_3_RECEIPT.json"
$final|ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $fp -Encoding UTF8

Capture "ACTIVE"
Write-QrosLog "DEMO_FORWARD_ACTIVE build=$Build pid=$($ap.Id)"
Bundle-QrosEvidence

Write-Host ""
Write-Host "============================================================"
Write-Host " QROS DEPLOYMENT RUNTIME V2.2.3: DEMO_FORWARD_ACTIVE"
Write-Host " Existing V2.2 scientific/deployment checkpoint was reused after re-verification."
Write-Host " MT5 remains running."
Write-Host " Evidence:"
Write-Host " C:\QROS_DARWINEX_DEMO_RUNTIME_V2_2_3\QROS_DEPLOYMENT_RUNTIME_V2_2_3_EVIDENCE.zip"
Write-Host "============================================================"
exit 0
