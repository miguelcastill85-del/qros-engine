@echo off
setlocal
title QROS - Recuperacion MT5 de solo lectura
set "QROS_RECOVERY_SELF=%~f0"
set "QROS_RECOVERY_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "QROS_RECOVERY_PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
echo Recuperando archivos QROS y MT5. No cierre su terminal.
echo No se ejecutan estrategias ni se cambian permisos de trading.
echo La busqueda tiene un limite de 12 minutos, mas copia y compresion.
"%QROS_RECOVERY_PS%" -NoLogo -NoProfile -Command "$ErrorActionPreference='Stop'; try { $s=[IO.File]::ReadAllText($env:QROS_RECOVERY_SELF); $m='# QROS_EMBEDDED_POWERSHELL_START'; $i=$s.LastIndexOf($m); if($i -lt 0){throw 'Payload missing'}; & ([scriptblock]::Create($s.Substring($i+$m.Length))) } catch { Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red; exit 1 }"
set "QROS_RECOVERY_RC=%ERRORLEVEL%"
echo.
if "%QROS_RECOVERY_RC%"=="0" (echo Recuperacion finalizada. Adjunta aqui el ZIP indicado.) else (echo Recuperacion con incidencias. Conserva la carpeta y lee el mensaje anterior.)
pause
exit /b %QROS_RECOVERY_RC%
# QROS_EMBEDDED_POWERSHELL_START
Set-StrictMode -Version 3.0
$ErrorActionPreference='Stop'
if($PSVersionTable.PSVersion.Major -lt 5){throw 'Se requiere Windows PowerShell 5 o superior.'}
$run='QROS_RECUPERACION_'+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss')+'_'+[guid]::NewGuid().ToString('N').Substring(0,8)
$destBase=[Environment]::GetFolderPath('Desktop')
if([string]::IsNullOrWhiteSpace($destBase) -or -not [IO.Directory]::Exists($destBase)){$destBase=$env:TEMP}
$out=Join-Path $destBase $run
[IO.Directory]::CreateDirectory($out)|Out-Null
$filesDir=Join-Path $out 'ARCHIVOS'
[IO.Directory]::CreateDirectory($filesDir)|Out-Null
$utf8=New-Object Text.UTF8Encoding($false)
$inventory=New-Object 'System.Collections.Generic.List[object]'
$issues=New-Object 'System.Collections.Generic.List[object]'
$roots=New-Object 'System.Collections.Generic.List[string]'
$seen=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$handled=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$clock=[Diagnostics.Stopwatch]::StartNew()
$script:totalBytes=[long]0
$script:visited=[long]0
$script:limitReached=$false
$script:filesCopied=0
$script:lastProgress=0
$maxFile=[long]64MB
$maxTotal=[long]384MB
$script:logCount=0

function Issue([string]$path,[string]$reason){
 if($issues.Count -lt 2000){$issues.Add([pscustomobject]@{path=$path;reason=$reason})}
}
function JsonFile([string]$name,$value){
 [IO.File]::WriteAllText((Join-Path $out $name),(ConvertTo-Json -InputObject $value -Depth 8),$utf8)
}
function AddRoot([string]$path){
 if(-not [string]::IsNullOrWhiteSpace($path) -and [IO.Directory]::Exists($path)){$roots.Add($path)}
}
function ProcessSnapshot {
 $rows=New-Object 'System.Collections.Generic.List[object]'
 try {
  $ps=Get-CimInstance Win32_Process -Filter "Name='terminal64.exe' OR Name='terminal.exe' OR Name='metatester64.exe' OR Name='metaeditor64.exe'"
  foreach($proc in $ps){
   $rows.Add([pscustomobject]@{pid=$proc.ProcessId;parent_pid=$proc.ParentProcessId;name=$proc.Name;path=$proc.ExecutablePath;created=$proc.CreationDate;observed_utc=[DateTime]::UtcNow.ToString('o')})
   if([string]::IsNullOrEmpty($proc.ExecutablePath)){Issue ('PID '+$proc.ProcessId) 'ExecutablePath not accessible; process mapping incomplete.'}
  }
 } catch {Issue 'ProcessSnapshot' $_.Exception.Message}
 return ,($rows.ToArray())
}
function OpenRead([string]$path){
 return [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
}
function HashRead([string]$path){
 $stream=$null;$sha=$null
 try{$stream=OpenRead $path;$sha=[Security.Cryptography.SHA256]::Create();return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
 finally{if($null -ne $stream){$stream.Dispose()};if($null -ne $sha){$sha.Dispose()}}
}
function Capture([IO.FileInfo]$file,[string]$kind){
 if(-not $handled.Add($file.FullName)){return}
 if(($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or (([int]$file.Attributes -band 0x401000) -ne 0)){Issue $file.FullName 'Reparse/offline/cloud placeholder skipped.';return}
 if($file.Length -gt $maxFile -or ($script:totalBytes+$file.Length) -gt $maxTotal){Issue $file.FullName 'Size budget exceeded; file not copied.';return}
 if($script:filesCopied -ge 12000){Issue $file.FullName 'File count budget exceeded.';return}
 $src=$null;$dst=$null;$target=$null
 try{
  $beforeLen=$file.Length;$beforeTime=$file.LastWriteTimeUtc
  $id=($inventory.Count+1).ToString('D6')
  $target=Join-Path $filesDir ($id+'_'+$file.Name)
  $src=OpenRead $file.FullName
  $dst=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
  $buffer=New-Object byte[] 65536
  $copied=[long]0
  while(($n=$src.Read($buffer,0,$buffer.Length)) -gt 0){
   if($copied+$n -gt $maxFile -or $script:totalBytes+$n -gt $maxTotal){throw 'Copy budget exceeded during read.'}
   $dst.Write($buffer,0,$n);$copied+=$n;$script:totalBytes+=$n
  }
  $dst.Dispose();$dst=$null;$src.Dispose();$src=$null
  $snapshotHash=HashRead $target
  $sourceHash=HashRead $file.FullName
  $file.Refresh()
  $stable=($sourceHash -eq $snapshotHash -and $file.Length -eq $beforeLen -and $file.LastWriteTimeUtc -eq $beforeTime)
  $state='STABLE_DOUBLE_READ'
  if(-not $stable){$state='UNSTABLE_NOT_AUTHORITY';Issue $file.FullName 'Source changed while copying. Snapshot is not canonical.'}
  $inventory.Add([pscustomobject]@{source=$file.FullName;copy=('ARCHIVOS/'+[IO.Path]::GetFileName($target));kind=$kind;bytes=$copied;sha256=$snapshotHash;source_second_read_sha256=$sourceHash;status=$state;source_lastwrite_utc=$beforeTime.ToString('o');captured_utc=[DateTime]::UtcNow.ToString('o')})
  $script:filesCopied++
 }catch{Issue $file.FullName $_.Exception.Message;if($null -ne $target){Issue $target 'Possible partial copy. Not in verified inventory.'}}
 finally{if($null -ne $dst){$dst.Dispose()};if($null -ne $src){$src.Dispose()}}
}
function LogExtract([IO.FileInfo]$file){
 if(-not $handled.Add($file.FullName)){return}
 if($file.Length -gt 20MB){Issue $file.FullName 'Log larger than 20 MB skipped.';return}
 $stream=$null;$reader=$null
 try{
  $stream=OpenRead $file.FullName
  $reader=New-Object IO.StreamReader($stream,[Text.Encoding]::UTF8,$true)
  $lines=New-Object 'System.Collections.Generic.Queue[string]'
  while(($line=$reader.ReadLine()) -ne $null){
   if($line -match '(?i)QROS|Darwinex|expert|\bloaded\b|\bremoved\b|fence|CERT|initializ'){
    if($line -match '(?i)password|passwd|pwd\s*[:=]|secret|api[_ -]?key|access[_ -]?token'){$line='[LINE OMITTED: possible credential]'}
    if($line.Length -gt 3000){$line=$line.Substring(0,3000)+' [TRUNCATED]'}
    $lines.Enqueue($line);if($lines.Count -gt 500){$null=$lines.Dequeue()}
   }
  }
  $name='LOG_EXTRACT_'+($inventory.Count+1).ToString('D6')+'.txt'
  $target=Join-Path $out $name
  [IO.File]::WriteAllLines($target,$lines.ToArray(),$utf8)
  $inventory.Add([pscustomobject]@{source=$file.FullName;copy=$name;kind='FILTERED_LOG_NOT_ORIGINAL';bytes=([IO.FileInfo]$target).Length;sha256=(HashRead $target);status='BEST_EFFORT_WHILE_ACTIVE';captured_utc=[DateTime]::UtcNow.ToString('o')})
 }catch{Issue $file.FullName $_.Exception.Message}
 finally{if($null -ne $reader){$reader.Dispose()}elseif($null -ne $stream){$stream.Dispose()}}
}
function Walk([string]$root){
 $stack=New-Object 'System.Collections.Generic.Stack[string]'
 $stack.Push($root)
 while($stack.Count -gt 0){
  if($clock.Elapsed.TotalSeconds -gt 720 -or $script:visited -ge 400000){$script:limitReached=$true;return}
  $dir=$stack.Pop()
  if(-not $seen.Add($dir)){continue}
  if($dir.StartsWith($out,[StringComparison]::OrdinalIgnoreCase)){continue}
  try{
   $di=New-Object IO.DirectoryInfo($dir)
   if(($di.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Issue $dir 'Reparse directory skipped.';continue}
   foreach($entry in $di.EnumerateFileSystemInfos()){
    $script:visited++
    if($clock.Elapsed.TotalSeconds -gt 720 -or $script:visited -ge 400000){$script:limitReached=$true;return}
    if(($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){continue}
    if($entry.Name -match '^QROS_RECUPERACION_'){continue}
    if(($entry.Attributes -band [IO.FileAttributes]::Directory) -ne 0){
     if($entry.Name -notmatch '^(?i:Windows|WinSxS|System Volume Information|\$Recycle.Bin|node_modules|\.git|\.venv|__pycache__|Cache|Caches|WebCache|GPUCache|bases|history|ticks)$'){$stack.Push($entry.FullName)}
     continue
    }
    $path=$entry.FullName;$ext=$entry.Extension.ToLowerInvariant()
    if($path -eq $env:QROS_RECOVERY_SELF){continue}
    # Never read saved account credentials, terminal configuration or global-variable databases.
    if($entry.Name -match '(?i)^(accounts|servers|terminal|common)\.(dat|ini)$|\.key$|\.pfx$|\.pem$|gvariables\.dat$'){continue}
    $mql=($path -match '(?i)[\\/]MQL5[\\/](Experts|Include|Scripts|Presets|Profiles)[\\/]')
    $project=($path -match '(?i)QROS|QDB1|RUNNER_NATIVE_ENV|NATIVE_RUNTIME_PHASEA|R2_QUALIFIER')
    if($entry.Name -match '(?i)FULL_HISTORY|TICKS|tickdata|\.part\d+|part\d+-of-'){continue}
    if($mql -and $ext -in @('.mq5','.mqh','.ex5','.set','.chr','.tpl')){Capture $entry 'MQL_SOURCE_BINARY_PRESET_OR_CHART';continue}
    if($project -and $ext -in @('.mq5','.mqh','.ex5','.set','.ps1','.bat','.json','.md','.csv','.zip','.rar','.7z')){Capture $entry 'QROS_PROJECT_ARTIFACT';continue}
    if($ext -eq '.log' -and $path -match '(?i)MetaQuotes|MetaTrader|Darwinex|MQL5|QROS' -and $entry.LastWriteTimeUtc -gt [DateTime]::UtcNow.AddDays(-14) -and $script:logCount -lt 40){LogExtract $entry;$script:logCount++}
   }
  }catch{Issue $dir $_.Exception.Message}
  if($clock.Elapsed.TotalSeconds-$script:lastProgress -gt 10){
   Write-Host ('Revisados: '+$script:visited+' | Copiados: '+$script:filesCopied+' | Segundos: '+[int]$clock.Elapsed.TotalSeconds)
   $script:lastProgress=$clock.Elapsed.TotalSeconds
  }
 }
}
$fatal=$null
try{
 Write-Host ('Destino: '+$out) -ForegroundColor Cyan
 $before=ProcessSnapshot
 JsonFile 'PROCESOS_ANTES.json' @($before)
 foreach($proc in $before){if(-not [string]::IsNullOrEmpty($proc.path)){AddRoot ([IO.Path]::GetDirectoryName($proc.path))}}
 AddRoot (Join-Path $env:APPDATA 'MetaQuotes\Terminal')
 AddRoot (Join-Path $env:APPDATA 'MetaQuotes\Tester')
 AddRoot (Join-Path $env:LOCALAPPDATA 'MetaQuotes')
 foreach($d in @([Environment]::GetFolderPath('Desktop'),[Environment]::GetFolderPath('MyDocuments'),(Join-Path $env:USERPROFILE 'Downloads'))){AddRoot $d}
 # Priority pass: known terminal data and active portable installations.
 foreach($root in $roots){Walk $root;if($script:limitReached){break}}
 # Broader discovery: fixed local disks only; no network disks, links or permission elevation.
 if(-not $script:limitReached){foreach($drive in [IO.DriveInfo]::GetDrives()){
  if($drive.IsReady -and $drive.DriveType -eq [IO.DriveType]::Fixed){Walk $drive.RootDirectory.FullName}
  if($script:limitReached){break}
 }}
}catch{$fatal=$_.Exception.Message;Issue 'TOP_LEVEL' $fatal}
finally{
 JsonFile 'PROCESOS_DESPUES.json' @(ProcessSnapshot)
 JsonFile 'INVENTARIO.json' @($inventory.ToArray())
 JsonFile 'INCIDENCIAS.json' @($issues.ToArray())
 JsonFile 'RECIBO.json' ([ordered]@{run_id=$run;purpose='READ_ONLY_RECOVERY_NOT_NATIVE_QUALIFICATION';powershell=$PSVersionTable.PSVersion.ToString();elapsed_seconds=[int]$clock.Elapsed.TotalSeconds;entries_visited=$script:visited;files_copied=$script:filesCopied;bytes_copied=$script:totalBytes;search_limit_reached=$script:limitReached;search_complete_claimed=$false;fatal_error=$fatal;candidate_executed=$false;mt5_started_or_stopped=$false;cert_modified=$false;orders_sent=0;network_upload=$false;active_strategy_identity='NOT_PROVEN_REQUIRES_LOG_PROFILE_SOURCE_CORRELATION';roots_prioritized=$roots.ToArray()})
 [IO.File]::WriteAllText((Join-Path $out 'LEEME.txt'),@'
QROS - Recuperacion de solo lectura.
Adjunta el ZIP a la conversacion. No se sube automaticamente.
Incluye codigo, ejecutables, parametros, perfiles y extractos de logs encontrados.
INVENTARIO.json vincula cada copia con su ruta original y SHA-256.
UNSTABLE_NOT_AUTHORITY: el archivo cambio durante la lectura; no es fuente canonica.
Los logs son extractos filtrados de una sesion activa, no copias forenses completas.
No se han leido deliberadamente cuentas/passwords guardados, archivos de claves,
configuracion del terminal ni base de Global Variables. Codigo y presets pueden
contener informacion escrita por su autor; el ZIP es privado y no se publica solo.
No se modifico la instalacion MT5 ni CERT; no se abrieron ni cerraron operaciones.
Encontrar un EX5 no recupera su codigo fuente ni demuestra que este activo.
Perfiles y logs requieren correlacion; pueden reflejar configuraciones anteriores.
No se inspecciono memoria del proceso. Tampoco se ejecuto un EA diagnostico.
La busqueda excluye enlaces, datos historicos/ticks y carpetas de sistema/cache.
Limites: 12 minutos de busqueda, 400000 entradas, 12000 copias, 64 MB por archivo,
384 MB de copias. INCIDENCIAS registra limites, inaccesibles y archivos cambiantes.
La carpeta puede conservar copias parciales tras un fallo; solo el inventario
identifica las copias verificadas. No es un certificado R2 ni un permiso de trading.
'@,$utf8)
}
try{
 Add-Type -AssemblyName System.IO.Compression.FileSystem
 $zip=$out+'.zip'
 [IO.Compression.ZipFile]::CreateFromDirectory($out,$zip,[IO.Compression.CompressionLevel]::Optimal,$false)
 $zipHash=HashRead $zip
 [IO.File]::WriteAllText(($zip+'.sha256'),($zipHash+'  '+[IO.Path]::GetFileName($zip)), $utf8)
 Write-Host ''
 Write-Host ('ZIP PARA ADJUNTAR: '+$zip) -ForegroundColor Green
 Write-Host ('SHA-256: '+$zipHash)
 if($script:filesCopied -eq 0){Write-Host 'No se copiaron fuentes. Adjunta igualmente el ZIP de diagnostico.' -ForegroundColor Yellow}
 if($script:limitReached){Write-Host 'Busqueda parcial por limite. La cobertura esta registrada.' -ForegroundColor Yellow}
 if($null -ne $fatal){exit 2}
 exit 0
}catch{Write-Host ('No se pudo comprimir: '+$_.Exception.Message) -ForegroundColor Red;Write-Host ('Conserva la carpeta: '+$out);exit 1}
