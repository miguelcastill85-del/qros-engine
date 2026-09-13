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
function Start-Child([string]$mode){
    $exe=Join-Path $PSHOME 'powershell.exe'
    $script=Join-Path $PSScriptRoot 'Lock-Child.ps1'
    # These arguments are generated paths/tokens. No commands from input files.
    $childArgs=@('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',
        '-File',('"'+$script+'"'),'-Root',('"'+$root+'"'),'-Token',$token,'-Mode',$mode)
    $p=Start-Process -FilePath $exe -ArgumentList $childArgs -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root ($mode+'.stdout.txt')) `
        -RedirectStandardError (Join-Path $root ($mode+'.stderr.txt'))
    $children.Add($p)
    return $p
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
    Check 'fresh_pass' {
        Put "test_id,status,run_id`nREACQUIRE,PASS,$token`n"
        if((Wait-QrosStageRow $file 'REACQUIRE' 1000 @{run_id=$token}).status -cne 'PASS'){throw 'BAD_RESULT'}
    }
    Check 'real_fail_preserved' {
        Put "test_id,status`nREACQUIRE,FAIL`n"
        if((Wait-QrosStageRow $file 'REACQUIRE' 1000).status -cne 'FAIL'){throw 'FAIL_HIDDEN'}
    }
    Check 'stale_probe_rejected' {
        Put "test_id,status`nPROBE,PASS`n"
        Reject {Wait-QrosStageRow $file 'REACQUIRE' 150} 'QROS_STAGE_TIMEOUT_*'
    }
    Check 'wrong_run_rejected' {
        Put "test_id,status,run_id`nREACQUIRE,PASS,old`n"
        Reject {Wait-QrosStageRow $file 'REACQUIRE' 1000 @{run_id=$token}} 'QROS_EVIDENCE_BINDING_run_id'
    }
    Check 'duplicate_stage_rejected' {
        Put "test_id,status`nREACQUIRE,PASS`nREACQUIRE,PASS`n"
        Reject {Wait-QrosStageRow $file 'REACQUIRE' 1000} 'QROS_DUPLICATE_STAGE_ROWS'
    }
    Check 'incomplete_row_rejected' {
        Put "test_id,status`nREACQUIRE,PASS"
        Reject {Wait-QrosStageRow $file 'REACQUIRE' 150} 'QROS_STAGE_TIMEOUT_*'
    }
    Check 'invalid_status_rejected' {
        Put "test_id,status`nREACQUIRE,UNKNOWN`n"
        Reject {Wait-QrosStageRow $file 'REACQUIRE' 1000} 'QROS_EVIDENCE_STATUS'
    }
    Check 'missing_token_rejected' {
        Put "test_id,status`nREACQUIRE,PASS`n"
        Reject {Wait-QrosStageRow $file 'REACQUIRE' 1000 @{owner_token=$token}} 'QROS_EVIDENCE_BINDING_owner_token'
    }
    Check 'stale_then_fresh_different_process' {
        Put "test_id,status,run_id`nPROBE,PASS,$token`n"
        $writer=Start-Child 'Writer'
        $r=Wait-QrosStageRow $file 'REACQUIRE' 30000 @{run_id=$token}
        if($r.status -cne 'PASS'){throw 'FRESH_ROW_MISSED'}
        if(!$writer.WaitForExit(10000)){throw 'WRITER_DID_NOT_EXIT'}
        if($writer.ExitCode -ne 0){throw 'WRITER_FAILED'}
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
            if(!$denied){throw 'SECOND_PROCESS_NOT_DENIED'}
            [IO.File]::WriteAllText((Join-Path $root 'release.txt'),$token)
            if(!$holder.WaitForExit(15000)){throw 'RELEASE_EXIT_TIMEOUT'}
            if($holder.ExitCode -ne 0){throw 'HOLDER_EXIT_FAILED'}
            $released=Wait-Json 'released.json'
            if($released.run_id -cne $token -or $released.owner_token -cne $token -or
               $released.epoch -ne 1 -or $released.pid -ne $holder.Id -or
               $released.file_identity -cne $initialId){throw 'RELEASE_BINDING'}
            $h=[IO.File]::Open($lock,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
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
    if(@($rows|Where-Object {!$_.pass}).Count -eq 0 -and $rows.Count -eq 10){$exitCode=0}
}catch{$fatal=$_.Exception.Message}
finally{
    foreach($child in $children){
        try{
            if(!$child.WaitForExit(50000)){$fatal='OWNED_HELPER_EXIT_UNCONFIRMED';$exitCode=1}
        }catch{$fatal='OWNED_HELPER_STATUS_UNAVAILABLE';$exitCode=1}
    }
    $receipt=[ordered]@{schema='QROS_COMPONENT_DIAGNOSTIC_1';run_id=$token;start_utc=$started;
        end_utc=[DateTime]::UtcNow.ToString('o');scope='POWERSHELL_READER_AND_WINDOWS_LOCK_ONLY';
        decision=$(if($exitCode -eq 0){'COMPONENT_TESTS_PASS'}else{'COMPONENT_TESTS_FAIL'});
        powershell=$PSVersionTable.PSVersion.ToString();tests=@($rows.ToArray());fatal=$fatal;
        diagnostic_source_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant();
        reader_sha256=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'Wait-QrosStageRow.ps1') -Algorithm SHA256).Hash.ToLowerInvariant();
        r2_native_qualified=$false;candidate3_executed=$false;mt5_accessed=$false;
        cert_modified=$false;deployment_allowed=$false}
    foreach($name in @('ready.json','released.json','Writer.stdout.txt','Writer.stderr.txt','Lock.stdout.txt','Lock.stderr.txt')){
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
