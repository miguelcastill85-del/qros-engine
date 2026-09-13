# Diagnostic only. No MT5 paths, terminal commands, account access or trading code.
# All writes go to a new temporary test directory and one ZIP on the Desktop.
$ErrorActionPreference='Stop'
Set-StrictMode -Version 3.0
$token=[guid]::NewGuid().ToString('N')
$root=Join-Path ([IO.Path]::GetTempPath()) ('QROS_COMPONENT_TEST_'+$token)
if(Test-Path -LiteralPath $root){throw 'TEST_DIRECTORY_ALREADY_EXISTS'}
[void][IO.Directory]::CreateDirectory($root)
$evidence=Join-Path $root 'evidence'
[void][IO.Directory]::CreateDirectory($evidence)
$rows=New-Object Collections.Generic.List[object]
$children=New-Object Collections.Generic.List[object]
$fatal=$null
$exitCode=1
$zip=$null
$started=[DateTime]::UtcNow.ToString('o')
function Check([string]$name,[scriptblock]$action){
    try{& $action;$rows.Add([pscustomobject]@{test=$name;pass=$true})}
    catch{$rows.Add([pscustomobject]@{test=$name;pass=$false;error=$_.Exception.Message})}
}
function Reject([scriptblock]$action,[string]$pattern){
    try{& $action|Out-Null}catch{
        if($_.Exception.Message -like $pattern){return}
        throw
    }
    throw 'NEGATIVE_CONTROL_ACCEPTED'
}
function Put([string]$body){[IO.File]::WriteAllText((Join-Path $root 'result.csv'),$body,(New-Object Text.UTF8Encoding($false)))}
function Record-Q([string]$event,$payload){
    [ordered]@{event=$event;utc=[DateTime]::UtcNow.ToString('o');run_id=$token;payload=$payload}|
        ConvertTo-Json -Compress -Depth 12|Add-Content -LiteralPath (Join-Path $evidence 'OBSERVATIONS.jsonl') -Encoding UTF8
}
function Start-Child([string]$mode){
    if(@('Writer','Lock','ExitZero','ExitSeven','DelayedExit') -cnotcontains $mode){throw 'CHILD_MODE'}
    $info=New-Object Diagnostics.ProcessStartInfo
    $info.FileName=Join-Path $PSHOME 'powershell.exe'
    $childScript=Join-Path $PSScriptRoot 'Lock-Child.ps1'
    $info.Arguments='-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+$childScript+'" -Root "'+$root+'" -Token '+$token+' -Mode '+$mode
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true
    $info.RedirectStandardError=$true
    $p=New-Object Diagnostics.Process
    $p.StartInfo=$info
    if(!$p.Start()){throw 'PROCESS_START_FALSE'}
    # Keep the original Process and its native handle, never rebind by PID.
    $children.Add($p)
    $p|Add-Member -NotePropertyName QrosMode -NotePropertyValue $mode
    $p|Add-Member -NotePropertyName QrosOut -NotePropertyValue ($p.StandardOutput.ReadToEndAsync())
    $p|Add-Member -NotePropertyName QrosErr -NotePropertyValue ($p.StandardError.ReadToEndAsync())
    $handle=$p.Handle
    $p|Add-Member -NotePropertyName QrosStartUtc -NotePropertyValue ($p.StartTime.ToUniversalTime().ToString('o'))
    Record-Q 'PROCESS_START' ([ordered]@{mode=$mode;pid=$p.Id;start_utc=$p.QrosStartUtc;
        executable=$info.FileName;handle=$handle.ToInt64();launcher='Diagnostics.Process.Start'})
    return $p
}
function Observe-Child($p,[int]$timeout){
    $o=[ordered]@{mode=$p.QrosMode;pid=$p.Id;start_utc=$p.QrosStartUtc;wait_completed=$false;
        has_exited=$false;exit_code=$null;exit_code_type=$null;streams_complete=$false;error=$null}
    try{
        $o.wait_completed=$p.WaitForExit($timeout)
        if($o.wait_completed){
            $o.has_exited=$p.HasExited
            $raw=$p.ExitCode
            $o.exit_code=$raw
            if($null -ne $raw){$o.exit_code_type=$raw.GetType().FullName}
            if(!$p.QrosOut.Wait(10000) -or !$p.QrosErr.Wait(10000)){throw 'STREAM_DRAIN_TIMEOUT'}
            [IO.File]::WriteAllText((Join-Path $evidence ($p.QrosMode+'.stdout.txt')),[string]$p.QrosOut.Result)
            [IO.File]::WriteAllText((Join-Path $evidence ($p.QrosMode+'.stderr.txt')),[string]$p.QrosErr.Result)
            $o.streams_complete=$true
        }
    }catch{$o.error=$_.Exception.Message}
    # Always persist raw values BEFORE interpreting success/failure.
    Record-Q 'PROCESS_OBSERVATION' $o
    return [pscustomobject]$o
}
function Assert-QrosExit($o,[int]$expected){
    if($null -ne $o.error){throw ('PROCESS_OBSERVATION_ERROR_'+$o.error)}
    if($o.wait_completed -isnot [bool] -or !$o.wait_completed -or
       $o.has_exited -isnot [bool] -or !$o.has_exited){throw 'PROCESS_EXIT_UNCONFIRMED'}
    if($null -eq $o.exit_code -or $o.exit_code -isnot [int]){throw 'PROCESS_EXIT_CODE_UNAVAILABLE'}
    if($o.exit_code -ne $expected){throw ('PROCESS_NONEXPECTED_EXIT_'+$o.exit_code)}
    if($o.streams_complete -isnot [bool] -or !$o.streams_complete){throw 'PROCESS_STREAMS_UNCONFIRMED'}
}
function Wait-Json([string]$name,[int]$timeout=15000){
    $clock=[Diagnostics.Stopwatch]::StartNew()
    do{
        try{
            $value=Get-Content -LiteralPath (Join-Path $root $name) -Raw -ErrorAction Stop|ConvertFrom-Json -ErrorAction Stop
            if($null -ne $value){return $value}
        }catch [IO.IOException]{}catch [System.Management.Automation.ItemNotFoundException]{}
        catch [System.ArgumentException]{}
        Start-Sleep -Milliseconds 50
    }while($clock.ElapsedMilliseconds -lt $timeout)
    throw ('JSON_TIMEOUT_'+$name)
}
try{
    if($env:OS -cne 'Windows_NT' -or $PSVersionTable.PSVersion.Major -ne 5 -or
        $PSVersionTable.PSVersion.Minor -ne 1){throw 'WINDOWS_POWERSHELL_5_1_REQUIRED'}
    $drive=New-Object IO.DriveInfo([IO.Path]::GetPathRoot($root))
    if($drive.DriveFormat -cne 'NTFS'){throw 'NTFS_REQUIRED_FOR_THIS_FILE_ID_DIAGNOSTIC'}
    $manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'PACKAGE_MANIFEST.json') -Raw|ConvertFrom-Json
    foreach($entry in $manifest.files){
        if([IO.Path]::GetFileName([string]$entry.name) -cne [string]$entry.name){throw 'MANIFEST_NAME'}
        $actual=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $entry.name) -Algorithm SHA256).Hash.ToLowerInvariant()
        if($actual -cne [string]$entry.sha256){throw ('MANIFEST_HASH_'+$entry.name)}
    }
    # Parse before importing or launching any package script.
    foreach($name in @('Wait-QrosStageRow.ps1','Lock-Child.ps1','Test-Components.ps1')){
        $parseTokens=$null;$parseErrors=$null
        [void][Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$parseTokens,[ref]$parseErrors)
        if(@($parseErrors).Count -ne 0){throw ('AST_PARSE_'+$name)}
    }
    . (Join-Path $PSScriptRoot 'Wait-QrosStageRow.ps1')
    Add-Type -Path (Join-Path $PSScriptRoot 'NativeFileIdentity.cs')
    $file=Join-Path $root 'result.csv'
    Check 'process_exit_zero_control' {
        $p=Start-Child 'ExitZero'
        Assert-QrosExit (Observe-Child $p 30000) 0
    }
    Check 'process_exit_seven_control' {
        $p=Start-Child 'ExitSeven'
        $observed=Observe-Child $p 30000
        Assert-QrosExit $observed 7
        Reject {Assert-QrosExit $observed 0} 'PROCESS_NONEXPECTED_EXIT_7'
    }
    Check 'process_timeout_control' {
        $p=Start-Child 'DelayedExit'
        $early=Observe-Child $p 1
        if($early.wait_completed){throw 'TIMEOUT_CONTROL_DID_NOT_TIME_OUT'}
        Reject {Assert-QrosExit $early 0} 'PROCESS_EXIT_UNCONFIRMED'
        Assert-QrosExit (Observe-Child $p 30000) 0
    }
    Check 'exit_validator_negative_controls' {
        foreach($value in @($null,'0',$false,7)){
            $o=[pscustomobject]@{wait_completed=$true;has_exited=$true;exit_code=$value;streams_complete=$true;error=$null}
            if($value -is [int]){Reject {Assert-QrosExit $o 0} 'PROCESS_NONEXPECTED_EXIT_7'}
            else{Reject {Assert-QrosExit $o 0} 'PROCESS_EXIT_CODE_UNAVAILABLE'}
        }
        $o=[pscustomobject]@{wait_completed=$true;has_exited=$true;exit_code=0;streams_complete=$false;error=$null}
        Reject {Assert-QrosExit $o 0} 'PROCESS_STREAMS_UNCONFIRMED'
        $o.streams_complete=$true;$o.error='INJECTED'
        Reject {Assert-QrosExit $o 0} 'PROCESS_OBSERVATION_ERROR_INJECTED'
    }
    if(@($rows|Where-Object {!$_.pass}).Count -gt 0){throw 'PROCESS_CONTROLS_NOT_QUALIFIED'}
    Check 'stale_then_fresh_different_process' {
        Put "test_id,status,run_id`nPROBE,PASS,$token`n"
        $writer=Start-Child 'Writer'
        $r=Wait-QrosStageRow $file 'REACQUIRE' 30000 @{run_id=$token}
        if($r.status -cne 'PASS'){throw 'FRESH_ROW_MISSED'}
        Record-Q 'FRESH_ROW_ACCEPTED' $r
        Assert-QrosExit (Observe-Child $writer 10000) 0
    }
    Check 'two_process_exclusive_release_reacquire' {
        $lock=Join-Path $root 'lock.bin'
        $h=[IO.File]::Open($lock,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        try{$initialId=[QrosNativeFileIdentity]::Read($h.SafeFileHandle)}finally{$h.Dispose()}
        $holder=Start-Child 'Lock'
        try{
            $ready=Wait-Json 'ready.json' 30000
            $holder.Refresh()
            if($holder.HasExited -or $ready.pid -ne $holder.Id -or $ready.run_id -cne $token -or
                $ready.owner_token -cne $token -or $ready.epoch -ne 1 -or $ready.lock_path -cne $lock -or
                $ready.file_identity -cne $initialId -or
                $ready.start_utc -cne $holder.StartTime.ToUniversalTime().ToString('o')){throw 'HOLDER_BINDING'}
            $attempt=[DateTime]::UtcNow.ToString('o')
            $denied=$false;$probe=$null;$win32=0
            try{$probe=[IO.File]::Open($lock,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
            catch [IO.IOException]{
                $win32=$_.Exception.HResult -band 0xffff
                if($win32 -ne 32){throw}
                $denied=$true
            }finally{if($null -ne $probe){$probe.Dispose()}}
            Record-Q 'LOCK_PROBE' ([ordered]@{denied=$denied;win32_error=$win32;attempt_utc=$attempt;initial_file_id=$initialId;holder=$ready;probe_pid=$PID;lock_path=$lock})
            if(!$denied){throw 'SECOND_PROCESS_NOT_DENIED'}
            [IO.File]::WriteAllText((Join-Path $root 'release.txt'),$token)
            Assert-QrosExit (Observe-Child $holder 15000) 0
            $released=Wait-Json 'released.json'
            Record-Q 'HOLDER_RELEASE' $released
            if($released.run_id -cne $token -or $released.owner_token -cne $token -or
               $released.epoch -ne 1 -or $released.pid -ne $holder.Id -or
               $released.file_identity -cne $initialId){throw 'RELEASE_BINDING'}
            $h=[IO.File]::Open($lock,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
            Record-Q 'REACQUIRE_OPENED' ([ordered]@{lock_path=$lock;utc=[DateTime]::UtcNow.ToString('o')})
            try{
                $reacquiredId=[QrosNativeFileIdentity]::Read($h.SafeFileHandle)
                $bytes=New-Object byte[] 32
                if($h.Length -ne 32 -or $h.Read($bytes,0,32) -ne 32 -or
                    [Text.Encoding]::ASCII.GetString($bytes) -cne $token -or
                    $reacquiredId -cne $initialId){throw 'REACQUIRE_ID_OR_TOKEN'}
            }finally{$h.Dispose()}
            [ordered]@{scope='POWERSHELL_TWO_PROCESS_ONLY_NOT_MT5';run_id=$token;
                initial_file_id=$initialId;holder=$ready;probe_pid=$PID;
                attempt_utc=$attempt;win32_error=$win32;release=$released;
                reacquired_file_id=$reacquiredId;reacquired_utc=[DateTime]::UtcNow.ToString('o');
                r2_native_qualified=$false}|ConvertTo-Json -Depth 8|
                Set-Content -LiteralPath (Join-Path $evidence 'LOCK_OBSERVATION.json') -Encoding UTF8
        }finally{
            # Only a token command to our helper. No termination of any process.
            [IO.File]::WriteAllText((Join-Path $root 'release.txt'),$token)
        }
    }
    if(@($rows|Where-Object {!$_.pass}).Count -eq 0 -and $rows.Count -eq 6){$exitCode=0}
}catch{$fatal=$_.Exception.Message}
finally{
    foreach($child in $children){
        try{
            $final=Observe-Child $child 50000
            if(!$final.wait_completed -or $null -ne $final.error){$fatal='OWNED_HELPER_EXIT_UNCONFIRMED';$exitCode=1}
            if($final.wait_completed){$child.Dispose()}
        }catch{$fatal='OWNED_HELPER_STATUS_UNAVAILABLE';$exitCode=1}
    }
    $receipt=[ordered]@{schema='QROS_COMPONENT_PROCESS_OBSERVATION_1';run_id=$token;start_utc=$started;
        end_utc=[DateTime]::UtcNow.ToString('o');scope='PROCESS_OBSERVATION_AND_TWO_PENDING_COMPONENT_TESTS';
        inherited_native_passes=8;inherited_receipt_archive_sha256='18aed649ebaf3eb02c4d9bc4eceb209cd079331bc34136ba80689f733cebe456';
        decision=$(if($exitCode -eq 0){'COMPONENT_TESTS_PASS'}else{'COMPONENT_TESTS_FAIL'});
        powershell=$PSVersionTable.PSVersion.ToString();tests=@($rows.ToArray());fatal=$fatal;
        diagnostic_source_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
        package_manifest_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'PACKAGE_MANIFEST.json') -Algorithm SHA256).Hash.ToLowerInvariant();
        reader_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'Wait-QrosStageRow.ps1') -Algorithm SHA256).Hash.ToLowerInvariant();
        r2_native_qualified=$false;candidate3_executed=$false;mt5_accessed=$false;
        cert_modified=$false;deployment_allowed=$false}
    foreach($name in @('ready.json','released.json','result.csv')){
        $path=Join-Path $root $name
        if(Test-Path -LiteralPath $path){
            try{Copy-Item -LiteralPath $path -Destination (Join-Path $evidence $name) -ErrorAction Stop}
            catch{
                $exitCode=1;$receipt.decision='COMPONENT_TESTS_FAIL';$receipt.fatal='EVIDENCE_COPY_FAILED'
                [IO.File]::AppendAllText((Join-Path $evidence 'PACKAGING_ERRORS.txt'),$name+': '+$_.Exception.Message+[Environment]::NewLine)
            }
        }
    }
    $receipt|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $evidence 'COMPONENT_RECEIPT.json') -Encoding UTF8
    try{
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $desktop=[Environment]::GetFolderPath('Desktop')
        if([string]::IsNullOrWhiteSpace($desktop)){throw 'DESKTOP_UNAVAILABLE'}
        $zip=Join-Path $desktop ('QROS_COMPONENT_EVIDENCE_'+$token+'.zip')
        [IO.Compression.ZipFile]::CreateFromDirectory($evidence,$zip)
        $archive=[IO.Compression.ZipFile]::OpenRead($zip)
        try{
            $expectedFiles=@(Get-ChildItem -LiteralPath $evidence -File)
            if($archive.Entries.Count -ne $expectedFiles.Count){throw 'ZIP_ENTRY_COUNT'}
            foreach($item in $expectedFiles){
                $entry=$archive.GetEntry($item.Name)
                if($null -eq $entry -or $entry.Length -ne $item.Length){throw 'ZIP_ENTRY_SIZE'}
                $stream=$entry.Open();$sha=[Security.Cryptography.SHA256]::Create()
                try{$zipHash=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')}
                finally{$sha.Dispose();$stream.Dispose()}
                if($zipHash -cne (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash){throw 'ZIP_ENTRY_HASH'}
            }
        }finally{$archive.Dispose()}
        Write-Host ('RESULTADO: '+$receipt.decision)
        Write-Host ('ZIP PARA ADJUNTAR: '+$zip)
        Write-Host ('SHA256: '+(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash)
    }catch{
        $exitCode=2
        Write-Host ('ERROR AL COMPRIMIR: '+$_.Exception.Message)
        Write-Host ('EVIDENCIA CONSERVADA: '+$evidence)
    }
}
exit $exitCode
