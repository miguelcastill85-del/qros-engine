# Engineering component only. Dot-sourcing defines a reader; it launches nothing.
# NOT a qualified R2 runner or a new qualifier release. Native tests are pending.
# Replaces the one-shot First/Read-Rows path for stage-transition polling.
# Same-stage replay still requires fresh role files and producer identity binding.
function Wait-QrosStageRow {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$LiteralPath,
        [Parameter(Mandatory=$true)][string]$TestId,
        [ValidateRange(1,600000)][int]$TimeoutMs=15000,
        [hashtable]$ExpectedFields=@{},
        [ValidateRange(128,10485760)][int]$MaxBytes=1048576
    )
    $clock=[Diagnostics.Stopwatch]::StartNew()
    $lastReason='MISSING'
    do {
        $handle=$null
        $text=$null
        try {
            $handle=[IO.File]::Open($LiteralPath,[IO.FileMode]::Open,
                [IO.FileAccess]::Read,[IO.FileShare]::None)
            $length=$handle.Length
            if($length -gt $MaxBytes){throw 'QROS_EVIDENCE_OVERSIZE'}
            if($length -gt 0){
                $bytes=New-Object byte[] ([int]$length)
                $offset=0
                while($offset -lt $bytes.Length){
                    $count=$handle.Read($bytes,$offset,$bytes.Length-$offset)
                    if($count -le 0){break}
                    $offset+=$count
                }
                if($offset -eq $bytes.Length){
                    $decoder=New-Object Text.UTF8Encoding($false,$true)
                    $text=$decoder.GetString($bytes).TrimStart([char]0xFEFF)
                }else{$lastReason='SHORT_READ'}
            }else{$lastReason='EMPTY'}
        } catch [IO.IOException] {
            $lastReason='MISSING_OR_BUSY'
        } finally {
            if($null -ne $handle){$handle.Dispose()}
        }
        if($null -ne $text -and $text.EndsWith("`n")){
            $rows=@()
            try{$rows=@($text | ConvertFrom-Csv -ErrorAction Stop)}
            catch{$lastReason='CSV_INCOMPLETE'}
            $matches=@($rows | Where-Object {
                $p=$_.PSObject.Properties['test_id']
                $null -ne $p -and [string]$p.Value -ceq $TestId
            })
            if($matches.Count -gt 1){throw 'QROS_DUPLICATE_STAGE_ROWS'}
            if($matches.Count -eq 1){
                $row=$matches[0]
                foreach($key in $ExpectedFields.Keys){
                    $property=$row.PSObject.Properties[$key]
                    if($null -eq $property -or
                        [string]$property.Value -cne [string]$ExpectedFields[$key]){
                        throw ('QROS_EVIDENCE_BINDING_'+$key)
                    }
                }
                $status=$row.PSObject.Properties['status']
                if($null -eq $status -or @('PASS','FAIL') -cnotcontains [string]$status.Value){
                    throw 'QROS_EVIDENCE_STATUS'
                }
                # Return FAIL immediately too. Never wait until a FAIL turns PASS.
                if($clock.ElapsedMilliseconds -ge $TimeoutMs){break}
                return $row
            }
            $lastReason='EXPECTED_STAGE_NOT_YET_PRESENT'
        }
        $remaining=$TimeoutMs-$clock.ElapsedMilliseconds
        if($remaining -le 0){break}
        Start-Sleep -Milliseconds ([int][Math]::Min(125,$remaining))
    }while($clock.ElapsedMilliseconds -lt $TimeoutMs)
    throw ('QROS_STAGE_TIMEOUT_'+$TestId+'_'+$lastReason)
}
