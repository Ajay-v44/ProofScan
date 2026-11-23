[CmdletBinding(DefaultParameterSetName='File')]
param(
    [Parameter(ParameterSetName='File', Mandatory)][string]$TicketFile,
    [Parameter(ParameterSetName='File', Mandatory)][string]$OutputFile,
    [Parameter(ParameterSetName='Text', Mandatory)][string]$TicketJson
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'The ProofScan Windows collector requires Windows.' }
if ($PSCmdlet.ParameterSetName -eq 'File') {
    if ((Get-Item -LiteralPath $TicketFile).Length -gt 4096) { throw 'The scan ticket is too large.' }
    $TicketJson = Get-Content -LiteralPath $TicketFile -Raw -Encoding UTF8
}
if ($TicketJson.Length -gt 4096) { throw 'The scan ticket is too large.' }
$ticket = ConvertFrom-Json -InputObject $TicketJson
$scanId = [guid]::Empty
if (-not [guid]::TryParse([string]$ticket.scan_id, [ref]$scanId) -or $ticket.challenge -cnotmatch '^[A-Za-z0-9_-]{43}$') {
    throw 'The file does not contain a ProofScan scan ticket.'
}
$expires = if ($ticket.expires_at -is [datetime]) { [DateTimeOffset]$ticket.expires_at } else {
    [DateTimeOffset]::Parse($ticket.expires_at.ToString())
}
if ($expires -le [DateTimeOffset]::UtcNow) {
    throw 'This ticket has expired. Download a fresh ticket from your seller page.'
}

function Read-Metric {
    param([string]$Class, [string[]]$Properties, [string]$Namespace = 'root/cimv2')
    try {
        Get-CimInstance -Namespace $Namespace -ClassName $Class -Property $Properties -OperationTimeoutSec 4
    } catch {
        Write-Verbose "$Class is unavailable on this device."
    }
}

function Clean-Label([string]$Value) {
    $clean = $Value.Trim()
    if ($clean.Length -gt 0) { $clean.Substring(0, [Math]::Min(120, $clean.Length)) }
}

$machine = Read-Metric Win32_ComputerSystem @('Model','Manufacturer','TotalPhysicalMemory') | Select-Object -First 1
$modules = @(Read-Metric Win32_PhysicalMemory @('Capacity'))
$installed = ($modules | Measure-Object -Property Capacity -Sum).Sum
if (-not $installed -and $machine) { $installed = $machine.TotalPhysicalMemory }
$capacity = if ($installed -gt 0) { [int][Math]::Max(1, [Math]::Round($installed / 1GB)) } else { $null }
$cpu = @(Read-Metric Win32_Processor @('Name') | ForEach-Object { Clean-Label $_.Name } | Select-Object -First 16)
$gpu = @(Read-Metric Win32_VideoController @('Name') | ForEach-Object { Clean-Label $_.Name } | Select-Object -First 16)
$drives = @(Read-Metric Win32_DiskDrive @('Model','Size','InterfaceType') | Where-Object {
    $_.Size -ge 1000000000 -and $_.InterfaceType -ne 'USB'
} | Select-Object -First 32 | ForEach-Object {
    @{ model = Clean-Label $_.Model; capacity_gb = [int][Math]::Round($_.Size / 1000000000) }
})

$design = @{}
Read-Metric BatteryStaticData @('InstanceName','DesignedCapacity') 'root/wmi' | ForEach-Object {
    if ($_.InstanceName -and $_.DesignedCapacity -gt 0 -and $_.DesignedCapacity -lt 1000000) {
        $design[$_.InstanceName] = $_.DesignedCapacity
    }
}
$healthValues = @(Read-Metric BatteryFullChargedCapacity @('InstanceName','FullChargedCapacity') 'root/wmi' | ForEach-Object {
    if ($_.InstanceName -and $design.ContainsKey($_.InstanceName) -and $_.FullChargedCapacity -gt 0 -and $_.FullChargedCapacity -lt 1000000) {
        [int][Math]::Min(100, [Math]::Round(100 * $_.FullChargedCapacity / $design[$_.InstanceName]))
    }
})
$battery = if ($healthValues.Count -eq 1) { $healthValues[0] } else { $null }
if ($cpu.Count -eq 0 -and $null -eq $capacity -and $drives.Count -eq 0) {
    throw 'Windows did not return any supported hardware readings.'
}
$manufacturer = if ($machine) { Clean-Label $machine.Manufacturer } else { $null }
$model = if ($machine) { Clean-Label $machine.Model } else { $null }
$payload = [ordered]@{
    scan_id = $scanId.ToString()
    challenge = $ticket.challenge
    platform = 'windows'
    hardware = [ordered]@{
        manufacturer = $manufacturer
        model = $model
        cpu = $cpu
        gpu = $gpu
        memory_gib = $capacity
        drives = $drives
        battery_health_percent = $battery
    }
}
$json = ConvertTo-Json -InputObject $payload -Depth 5 -Compress
if ($PSCmdlet.ParameterSetName -eq 'Text') {
    $json
} else {
    [IO.File]::WriteAllText($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputFile), $json, [Text.UTF8Encoding]::new($false))
}
