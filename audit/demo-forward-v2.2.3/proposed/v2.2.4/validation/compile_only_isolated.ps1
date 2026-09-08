# Derived from the exact Candidate 3 Compile-Only runner. Same six targets and 0/0 gate.
# All output is constrained to a fresh reports directory; no terminal data directory writes.
param(
 [Parameter(Mandatory=$true)][string]$PackageRoot,
 [Parameter(Mandatory=$true)][string]$RunRoot,
 [Parameter(Mandatory=$true)][string]$MetaEditorExe,
 [Parameter(Mandatory=$true)][string]$StandardIncludeRoot
)
$ErrorActionPreference="Stop"
$Repo=(git rev-parse --show-toplevel).Trim()
$Reports=[IO.Path]::GetFullPath((Join-Path $Repo 'reports'))+[IO.Path]::DirectorySeparatorChar
$RunRoot=[IO.Path]::GetFullPath($RunRoot)
if(!$RunRoot.StartsWith($Reports,[StringComparison]::OrdinalIgnoreCase)){throw 'RUN_ROOT_MUST_BE_UNDER_PROJECT_REPORTS'}
if(Test-Path -LiteralPath $RunRoot){throw 'FRESH_RUN_ROOT_REQUIRED'}
$DataPath=Join-Path $RunRoot 'DATA'
New-Item -ItemType Directory -Path (Join-Path $DataPath 'MQL5/Include') -Force | Out-Null
Copy-Item -Path (Join-Path $StandardIncludeRoot '*') -Destination (Join-Path $DataPath 'MQL5/Include') -Recurse
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$Here=[IO.Path]::GetFullPath($PackageRoot)
$Out=Join-Path $RunRoot "OUTPUT"
$Ev=Join-Path $Out "EVIDENCE"
$Logs=Join-Path $Ev "COMPILE_LOGS"
New-Item -ItemType Directory -Force -Path $Out,$Ev,$Logs | Out-Null
$RunLog=Join-Path $Ev "QROS_V224_C3_COMPILE_ONLY.log"
if(Test-Path $RunLog){Remove-Item $RunLog -Force}
function Log([string]$m){$s="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $m";Write-Host $s;Add-Content -LiteralPath $RunLog -Value $s -Encoding UTF8}
function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function Bundle(){$zip=Join-Path $Out "QROS_V224_C3_COMPILE_ONLY_EVIDENCE.zip";if(Test-Path $zip){Remove-Item $zip -Force};Compress-Archive -Path (Join-Path $Ev '*') -DestinationPath $zip -CompressionLevel Optimal;Log "EVIDENCE_BUNDLE=$zip";return $zip}
function Fail([string]$reason,[int]$code){Log "FAIL $reason";[ordered]@{schema="QROS_V224_C3_COMPILE_ONLY_RECEIPT_1.0";decision="FAIL";reason=$reason;utc=(Get-Date).ToUniversalTime().ToString('o');terminal_restarted=$false;terminal_stopped=$false;terminal_launched=$false;orders_authorized=$false}|ConvertTo-Json -Depth 8|Set-Content (Join-Path $Ev 'QROS_V224_C3_COMPILE_ONLY_RECEIPT.json') -Encoding UTF8;Bundle|Out-Null;Write-Host "FAIL-CLOSED. MT5 activo no fue detenido ni reiniciado.";exit $code}
Log "START Candidate3 COMPILE-ONLY. No terminal stop/restart/launch; no orders."
if(!(Test-Path $MetaEditorExe)){Fail "METAEDITOR_NOT_FOUND" 10}
if(!(Test-Path $DataPath)){Fail "DATA_PATH_NOT_FOUND" 11}
$procs=@(Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" -ErrorAction SilentlyContinue)
$procInfo=@();foreach($p in $procs){$procInfo += [ordered]@{pid=[int]$p.ProcessId;name=[string]$p.Name;creation_date=[string]$p.CreationDate}}
$procInfo|ConvertTo-Json -Depth 5|Set-Content (Join-Path $Ev 'TERMINAL_PROCESS_SNAPSHOT.json') -Encoding UTF8
Log ("terminal64 processes observed="+$procs.Count+" read-only")
$Manifest=Get-Content -LiteralPath (Join-Path $Here 'PACKAGE_MANIFEST.json') -Raw | ConvertFrom-Json
$Expected=@{}
foreach($prop in $Manifest.expected_sources.PSObject.Properties){$Expected[$prop.Name]=$prop.Value}
if($Expected.Count-ne8){Fail "EXACT_EIGHT_SOURCE_MANIFEST_REQUIRED" 20}
foreach($rel in $Expected.Keys){$p=Join-Path $Here $rel;if(!(Test-Path $p)){Fail ("PACKAGE_SOURCE_MISSING_"+$rel) 20};if((Sha $p)-ne$Expected[$rel]){Fail ("PACKAGE_SOURCE_HASH_"+$rel) 21}}
Log "PACKAGE SOURCE HASHES VERIFIED 8/8"
$Inc=Join-Path $DataPath 'MQL5\Include';$Exp=Join-Path $DataPath 'MQL5\Experts';$Scr=Join-Path $DataPath 'MQL5\Scripts';$Pre=Join-Path $DataPath 'MQL5\Presets'
foreach($d in @($Inc,$Exp,$Scr,$Pre)){if(!(Test-Path $d)){New-Item -ItemType Directory -Force -Path $d|Out-Null}}
Copy-Item (Join-Path $Here 'MQL5\Include\QROS_DEMO_BUS_v2_2_4.mqh') $Inc -Force
Copy-Item (Join-Path $Here 'MQL5\Include\QROS_RISK_KERNEL_APPROVED_v15420.mqh') $Inc -Force
Get-ChildItem (Join-Path $Here 'MQL5\Experts') -Filter '*.mq5'|ForEach-Object{Copy-Item $_.FullName $Exp -Force}
Get-ChildItem (Join-Path $Here 'MQL5\Scripts') -Filter '*.mq5'|ForEach-Object{Copy-Item $_.FullName $Scr -Force}
Get-ChildItem (Join-Path $Here 'MQL5\Presets') -Filter '*.set'|ForEach-Object{Copy-Item $_.FullName $Pre -Force}
Log "Candidate3 source copied under V224-only names; no V223 source overwritten"
$Targets=@(
 @{kind='Expert';name='QROS_XAU_M1_DEMO_EMITTER_v2_2_4.mq5'},@{kind='Expert';name='QROS_NQX_17_31_DEMO_EMITTER_v2_2_4.mq5'},@{kind='Expert';name='QROS_DIV3_R3_DEMO_EMITTER_v2_2_4.mq5'},@{kind='Expert';name='QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5'},@{kind='Script';name='QROS_V224_MODULE_CERTIFY.mq5'},@{kind='Script';name='QROS_V224_RUNTIME_BOOTSTRAP.mq5'})
$compile=@();foreach($t in $Targets){$srcp=if($t.kind-eq'Expert'){Join-Path $Exp $t.name}else{Join-Path $Scr $t.name};$log=Join-Path $Logs ($t.name+'.log');if(Test-Path $log){Remove-Item $log -Force};$p=Start-Process $MetaEditorExe -WindowStyle Hidden -ArgumentList "/portable","/compile:`"$srcp`"","/include:`"$(Join-Path $DataPath 'MQL5')`"","/log:`"$log`"" -Wait -PassThru;if(!(Test-Path $log)){Fail ("COMPILE_LOG_MISSING_"+$t.name) 30};$text=Get-Content $log -Raw;$pass=($text-match'Result:\s*0 errors,\s*0 warnings');$compile += [ordered]@{name=$t.name;kind=$t.kind;exit_code=$p.ExitCode;pass=$pass;log_sha256=Sha $log};$compile|ConvertTo-Json -Depth 8|Set-Content (Join-Path $Ev 'COMPILE_RESULTS.json') -Encoding UTF8;if(!$pass){Fail ("COMPILE_NOT_0_0_"+$t.name) 31};Log ("COMPILE PASS 0/0 "+$t.name)}
$compile|ConvertTo-Json -Depth 8|Set-Content (Join-Path $Ev 'COMPILE_RESULTS.json') -Encoding UTF8
$ex5=@();foreach($t in $Targets){$dir=if($t.kind-eq'Expert'){$Exp}else{$Scr};$stem=[IO.Path]::GetFileNameWithoutExtension($t.name);$p=Join-Path $dir ($stem+'.ex5');if(!(Test-Path $p)){Fail ("EX5_MISSING_"+$stem) 32};$ex5 += [ordered]@{name=[IO.Path]::GetFileName($p);bytes=(Get-Item $p).Length;sha256=Sha $p}}
$ex5|ConvertTo-Json -Depth 8|Set-Content (Join-Path $Ev 'EX5_HASHES.json') -Encoding UTF8
foreach($n in @('V224_TEST_MATRIX.json','V224_OFFLINE_TEST_RESULTS.json','V224_BLOCKERS.json','V224_DECISION.json','V224_MANIFEST_SHA256.json','V224_CHANGELOG.md')){$p=Join-Path $Here $n;if(Test-Path $p){Copy-Item $p $Ev -Force}}
$receipt=[ordered]@{schema='QROS_V224_C3_COMPILE_ONLY_RECEIPT_1.0';decision='PASS';utc=(Get-Date).ToUniversalTime().ToString('o');compile='6/6 PASS 0 errors / 0 warnings';terminal_restarted=$false;terminal_stopped=$false;terminal_launched=$false;orders_authorized=$false;strategy_tester_executed=$false;runtime_canary_executed=$false;deployment_authorized=$false;next_gate='NATIVE_PARITY_AND_ISOLATED_MT5_SAFETY_GATES'}
$receipt|ConvertTo-Json -Depth 8|Set-Content (Join-Path $Ev 'QROS_V224_C3_COMPILE_ONLY_RECEIPT.json') -Encoding UTF8
$zip=Bundle;Write-Host '';Write-Host 'QROS V2.2.4 Candidate3 COMPILE-ONLY: PASS';Write-Host "Evidence: $zip";exit 0
