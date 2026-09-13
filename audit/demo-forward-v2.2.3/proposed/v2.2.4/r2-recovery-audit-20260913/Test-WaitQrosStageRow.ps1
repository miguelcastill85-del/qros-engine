# Native component tests only; no MT5, trading, configuration or process termination.
# Run under Windows PowerShell 5.1 to validate the reader before integration.
$ErrorActionPreference='Stop'
Set-StrictMode -Version 3.0
. (Join-Path $PSScriptRoot 'Wait-QrosStageRow.ps1')
$dir=Join-Path ([IO.Path]::GetTempPath()) ('QROS_READER_TEST_'+[guid]::NewGuid().ToString('N'))
[void][IO.Directory]::CreateDirectory($dir)
$file=Join-Path $dir 'result.csv'
$results=New-Object Collections.Generic.List[object]
function Check([string]$name,[scriptblock]$action){
    try{& $action;$results.Add([pscustomobject]@{test=$name;pass=$true})}
    catch{$results.Add([pscustomobject]@{test=$name;pass=$false;error=$_.Exception.Message})}
}
function Put([string]$body){[IO.File]::WriteAllText($file,$body,(New-Object Text.UTF8Encoding($false)))}
Check 'fresh_pass' {
    Put "test_id,status,run_id`nREACQUIRE,PASS,current`n"
    $r=Wait-QrosStageRow $file 'REACQUIRE' 1000 @{run_id='current'}
    if($r.status -cne 'PASS'){throw 'unexpected'}
}
Check 'real_fail' {
    Put "test_id,status`nREACQUIRE,FAIL`n"
    if((Wait-QrosStageRow $file 'REACQUIRE' 1000).status -cne 'FAIL'){throw 'failure hidden'}
}
Check 'stale_probe_timeout' {
    Put "test_id,status`nPROBE,PASS`n"
    $caught=$false
    try{Wait-QrosStageRow $file 'REACQUIRE' 150 | Out-Null}
    catch{if($_.Exception.Message -like 'QROS_STAGE_TIMEOUT_*'){$caught=$true}else{throw}}
    if(!$caught){throw 'stale evidence accepted'}
}
Check 'stale_run_rejected' {
    Put "test_id,status,run_id`nREACQUIRE,PASS,old`n"
    $caught=$false
    try{Wait-QrosStageRow $file 'REACQUIRE' 1000 @{run_id='current'} | Out-Null}
    catch{if($_.Exception.Message -eq 'QROS_EVIDENCE_BINDING_run_id'){$caught=$true}else{throw}}
    if(!$caught){throw 'old run accepted'}
}
Check 'duplicate_rejected' {
    Put "test_id,status`nREACQUIRE,PASS`nREACQUIRE,PASS`n"
    $caught=$false
    try{Wait-QrosStageRow $file 'REACQUIRE' 1000 | Out-Null}
    catch{if($_.Exception.Message -eq 'QROS_DUPLICATE_STAGE_ROWS'){$caught=$true}else{throw}}
    if(!$caught){throw 'duplicate accepted'}
}
Check 'stale_then_fresh_real_writer' {
    Put "test_id,status`nPROBE,PASS`n"
    $job=Start-Job -ArgumentList $file -ScriptBlock {
        param($target)
        Start-Sleep -Milliseconds 400
        # Retry exclusive acquisition because the reader may briefly own the file.
        $sw=[Diagnostics.Stopwatch]::StartNew()
        do{
            $h=$null
            try{
                $h=[IO.File]::Open($target,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
                $b=[Text.Encoding]::UTF8.GetBytes("test_id,status`nREACQUIRE,PASS`n")
                $h.Write($b,0,$b.Length);$h.Flush();return
            }catch [IO.IOException]{Start-Sleep -Milliseconds 25}
            finally{if($null -ne $h){$h.Dispose()}}
        }while($sw.ElapsedMilliseconds -lt 5000)
        throw 'writer timeout'
    }
    try{
        $r=Wait-QrosStageRow $file 'REACQUIRE' 15000
        if($r.status -cne 'PASS'){throw 'new result missed'}
    }finally{
        $done=Wait-Job $job -Timeout 20
        if($null -eq $done){throw 'writer job did not finish'}
        Receive-Job $job -ErrorAction Stop | Out-Null
        Remove-Job $job
    }
}
# Preserve test directory for inspection; never remove arbitrary paths.
$results | ConvertTo-Json -Depth 5
Write-Host ('Test files: '+$dir)
if(@($results | Where-Object {!$_.pass}).Count -gt 0){exit 1}
exit 0
