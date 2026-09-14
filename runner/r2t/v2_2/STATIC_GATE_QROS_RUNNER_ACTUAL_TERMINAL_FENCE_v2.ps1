param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version 3.0
$Here=Split-Path -Parent $MyInvocation.MyCommand.Path
$Source=Join-Path $Here "QUALIFY_QROS_RUNNER_ACTUAL_TERMINAL_FENCE_v2.ps1"
$Mql=Join-Path $Here "MQL5\Experts\QROS_RUNNER_RUNTIME_FENCE_QUALIFIER_v1.mq5"
$Manifest=Join-Path $Here "PACKAGE_MANIFEST_SHA256.json"
$Report=Join-Path $Here "R2T_V2_STATIC_GATE_REPORT_RUNTIME.json"

function Sha([string]$p){(Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant()}
function Fail([string]$m,[int]$c){Write-Host ("STATIC GATE FAIL: "+$m);exit $c}
function Count-Matches([string]$t,[string]$p){return ([regex]::Matches($t,$p,[Text.RegularExpressions.RegexOptions]::IgnoreCase)).Count}

if(!(Test-Path $Manifest)){Fail "manifest missing" 90}
$mp=Get-Content -LiteralPath $Manifest -Raw|ConvertFrom-Json
foreach($pr in $mp.files.PSObject.Properties){
 $fp=Join-Path $Here ([string]$pr.Name)
 if(!(Test-Path $fp)){Fail ("manifest missing "+$pr.Name) 91}
 if((Sha $fp)-ne ([string]$pr.Value.sha256).ToLowerInvariant()){Fail ("manifest hash mismatch "+$pr.Name) 92}
}
$t=Get-Content -LiteralPath $Source -Raw
$m=Get-Content -LiteralPath $Mql -Raw

function Test-Source([string]$x,[string]$mq){
 $r=[ordered]@{}
 $r["D04_NO_STARTPROCESS_PROXY_REGISTRY"]=(($x -notmatch '\$script:Owned') -and ($x -notmatch 'function\s+Stop-Owned'))
 $r["PS51_NO_GENERIC_LIST_RUNTIME"]=($x -notmatch 'System\.Collections\.Generic\.List|Collections\.Generic\.List')
 $r["D04_ENUM_ACTUAL_TERMINAL_BY_PATH"]=($x -match 'function\s+Get-IsoTerminalProcesses' -and $x -match '\$p\.Path')
 $r["D04_START_REBINDS_ACTUAL_PROCESS"]=($x -match 'Wait-IsoTerminal\s+\$iso\s+20000')
 $r["D04_STOP_ENUMERATES_ISO"]=($x -match 'function\s+Stop-IsoTerminals')
 $r["D04_STOP_PROVES_QUIESCENCE"]=($x -match 'Assert-IsoStopped\s+\$iso\s+20000\s+\$ThrowOnFail')
 $r["D10_STOP_PATH_GUARD"]=($x -match 'Is-UnderIso\s+\(\[string\]\$r\.path\)\s+\$iso')
 $r["D10_SINGLE_STOP_PROCESS"]=((Count-Matches $x 'Stop-Process') -eq 1)
 $r["NO_TASKKILL"]=($x -notmatch '\btaskkill\b')
 $r["ACTUAL_RUNTIME_NOT_TESTER"]=($mq -match 'MQLInfoInteger\(MQL_TESTER\)==1')
 $r["NO_TRADE_API"]=($mq -notmatch '\bCTrade\b|\bOrderSend\s*\(|\bPositionOpen\s*\(|\bBuy\s*\(|\bSell\s*\(')
 $r["ALLOW_LIVE_TRADING_ZERO"]=($x -match 'AllowLiveTrading=0')
 $r["COMMON_PATH_IDENTITY_GATE"]=($x -match 'COMMON_PATH_MISMATCH')
 $r["RUN_NAMESPACE"]=($x -match '\$Prefix="QROS_R2T_"\+\$RunId')
 $r["CERT_KEEP_ZERO_ONLY"]=($x -notmatch 'QDB1\.EXEC\.CERT\s*=\s*1')
 return $r
}
function All-Pass($r){foreach($k in $r.Keys){if(-not [bool]$r[$k]){return $false}};return $true}
$base=Test-Source $t $m
# PS5.1 compatibility: use a native PowerShell object array.
# Do NOT wrap System.Collections.Generic.List[object] with @(...):
# Windows PowerShell 5.1 can throw System.ArgumentException "Los tipos de argumentos no coinciden".
function New-MutationResult([string]$id,[string]$changed,[string]$expected){
 $rr=Test-Source $changed $m
 $caught=(-not [bool]$rr[$expected])
 return [pscustomobject]@{id=$id;expected_rule=$expected;caught=$caught}
}
$mut = @()
$mut += New-MutationResult "M_D04_PROXY_REGISTRY" ('$script:Owned=1'+[Environment]::NewLine+$t) "D04_NO_STARTPROCESS_PROXY_REGISTRY"
$mut += New-MutationResult "M_PS51_GENERIC_LIST_RUNTIME" ('$rows=New-Object System.Collections.Generic.List[object]'+[Environment]::NewLine+$t) "PS51_NO_GENERIC_LIST_RUNTIME"
$mut += New-MutationResult "M_D04_REMOVE_ACTUAL_DISCOVERY" ($t.Replace('Wait-IsoTerminal $iso 20000','@()')) "D04_START_REBINDS_ACTUAL_PROCESS"
$mut += New-MutationResult "M_D04_REMOVE_QUIESCENCE_PROOF" ($t.Replace('return (Assert-IsoStopped $iso 20000 $ThrowOnFail)','return $true')) "D04_STOP_PROVES_QUIESCENCE"
$mut += New-MutationResult "M_D10_REMOVE_PATH_GUARD" ($t.Replace('Is-UnderIso ([string]$r.path) $iso','($true)')) "D10_STOP_PATH_GUARD"
$mut += New-MutationResult "M_BROAD_TASKKILL" ($t+[Environment]::NewLine+'taskkill /IM terminal64.exe /F') "NO_TASKKILL"
$mutPass=$true;foreach($x in $mut){if(-not [bool]$x.caught){$mutPass=$false}}
$decision=if((All-Pass $base) -and $mutPass){"PASS"}else{"FAIL"}
$out=[ordered]@{
 schema="QROS_R2T_V2_STATIC_GATE_1.1"
 utc=(Get-Date).ToUniversalTime().ToString("o")
 decision=$decision
 source_sha256=(Sha $Source)
 mql_sha256=(Sha $Mql)
 parent_defect="D04_PROCESS_LIFETIME_PROXY"
 rules=$base
 mutations=$mut
 candidate3_executed=$false
 deployment_allowed=$false
 cert_arm_allowed=$false
}
$out|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $Report -Encoding UTF8
if($decision -ne "PASS"){Fail "rules or mutations failed" 93}
Write-Host "R2T v2 STATIC GATE PASS"
exit 0
