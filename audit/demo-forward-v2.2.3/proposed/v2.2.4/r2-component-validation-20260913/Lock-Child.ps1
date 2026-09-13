param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Token,
      [ValidateSet('Lock','Writer')][string]$Mode='Lock')
$ErrorActionPreference='Stop'
Set-StrictMode -Version 3.0
if($Token -notmatch '^[a-f0-9]{32}$'){throw 'TOKEN_FORMAT'}
$expected=Join-Path ([IO.Path]::GetTempPath()) ('QROS_COMPONENT_TEST_'+$Token)
if(![String]::Equals([IO.Path]::GetFullPath($Root),[IO.Path]::GetFullPath($expected),[StringComparison]::OrdinalIgnoreCase)){throw 'ROOT_GUARD'}
if((Get-Item -LiteralPath $Root).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'REPARSE_ROOT'}
if($Mode -ceq 'Writer'){
    Start-Sleep -Milliseconds 500
    $clock=[Diagnostics.Stopwatch]::StartNew()
    do{
        $writer=$null
        try{
            $writer=[IO.File]::Open((Join-Path $Root 'result.csv'),[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
            $data=[Text.Encoding]::UTF8.GetBytes("test_id,status,run_id`nREACQUIRE,PASS,$Token`n")
            $writer.Write($data,0,$data.Length);$writer.Flush($true)
            exit 0
        }catch [IO.IOException]{Start-Sleep -Milliseconds 25}
        finally{if($null -ne $writer){$writer.Dispose()}}
    }while($clock.ElapsedMilliseconds -lt 5000)
    throw 'WRITER_TIMEOUT'
}
Add-Type -Path (Join-Path $PSScriptRoot 'NativeFileIdentity.cs')
$h=$null
$clock=[Diagnostics.Stopwatch]::StartNew()
try{
    $lock=Join-Path $Root 'lock.bin'
    if((Get-Item -LiteralPath $lock).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'REPARSE_LOCK'}
    $h=[IO.File]::Open($lock,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $bytes=[Text.Encoding]::ASCII.GetBytes($Token)
    $h.SetLength(0);$h.Write($bytes,0,$bytes.Length);$h.Flush($true)
    $identity=[QrosNativeFileIdentity]::Read($h.SafeFileHandle)
    $me=[Diagnostics.Process]::GetCurrentProcess()
    $ready=[ordered]@{run_id=$Token;pid=$PID;start_utc=$me.StartTime.ToUniversalTime().ToString('o');
        lock_path=$lock;file_identity=$identity;owner_token=$Token;epoch=1;
        acquired_utc=[DateTime]::UtcNow.ToString('o');clock_ms=$clock.ElapsedMilliseconds}
    $ready|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Root 'ready.tmp') -Encoding UTF8
    Move-Item -LiteralPath (Join-Path $Root 'ready.tmp') -Destination (Join-Path $Root 'ready.json') -ErrorAction Stop
    $release=Join-Path $Root 'release.txt'
    while($clock.ElapsedMilliseconds -lt 45000){
        if(Test-Path -LiteralPath $release){
            if([IO.File]::ReadAllText($release) -cne $Token){throw 'RELEASE_NOT_OWNER'}
            $h.Dispose();$h=$null
            [ordered]@{run_id=$Token;owner_token=$Token;epoch=1;pid=$PID;
                file_identity=$identity;released_utc=[DateTime]::UtcNow.ToString('o')}|
                ConvertTo-Json|Set-Content -LiteralPath (Join-Path $Root 'released.json') -Encoding UTF8
            exit 0
        }
        Start-Sleep -Milliseconds 50
    }
    throw 'OWNER_DEADLINE_NO_RELEASE'
}finally{if($null -ne $h){$h.Dispose()}}
