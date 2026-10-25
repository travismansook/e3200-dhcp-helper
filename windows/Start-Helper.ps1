# Native Windows launcher. Dot-sourcing defines functions without starting anything.
[CmdletBinding()]
param(
    [string]$Config = (Join-Path (Split-Path $PSScriptRoot -Parent) 'config.local.json'),
    [string]$Program = (Join-Path $PSScriptRoot 'vendor\tftpd64.exe'),
    [switch]$ValidateOnly
)

function ConvertFrom-HelperJson {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Json)
    if ($Json -notmatch '^\s*\{') { throw 'Configuration must be a JSON object.' }
    $parsed = ConvertFrom-Json -InputObject $Json -ErrorAction Stop
    $seen = @{}
    # Consume complete escaped string tokens before inspecting property names.
    # ConvertFrom-Json alone can silently overwrite a duplicate key.
    foreach ($token in [regex]::Matches($Json, '"(?:\\.|[^"\\])*"')) {
        $remaining = $Json.Substring($token.Index + $token.Length)
        if ($remaining -notmatch '^\s*:') { continue }
        $decoded = ConvertFrom-Json -InputObject ('{"key":' + $token.Value + '}') -ErrorAction Stop
        $key = [string]$decoded.key
        if ($seen.ContainsKey($key)) { throw "Duplicate configuration field: $key" }
        $seen[$key] = $true
    }
    return $parsed
}

function ConvertTo-HelperIPv4Number {
    param([object]$Value, [string]$Name)
    if ($Value -isnot [string] -or $Value -notmatch '^(0|[1-9][0-9]{0,2})(\.(0|[1-9][0-9]{0,2})){3}$') {
        throw "$Name must be a dotted-decimal IPv4 address without leading zeroes."
    }
    $octets = @($Value.Split('.') | ForEach-Object { [int]$_ })
    if (@($octets | Where-Object { $_ -gt 255 }).Count -ne 0) { throw "$Name contains an invalid IPv4 octet." }
    return [uint64](([uint64]$octets[0] * 16777216) + ([uint64]$octets[1] * 65536) + ([uint64]$octets[2] * 256) + $octets[3])
}

function Get-HelperPrefixLength {
    param([string]$Mask)
    $number = ConvertTo-HelperIPv4Number $Mask 'subnet_mask'
    $bits = [Convert]::ToString([int64]$number, 2).PadLeft(32, '0')
    if ($bits -notmatch '^1{1,30}0{2,31}$') { throw 'subnet_mask must be contiguous and allow usable hosts (/1 through /30).' }
    return $bits.IndexOf('0')
}

function Test-HelperConfig {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Configuration, [switch]$RequireConfirmed)
    $allowed = @('extender_mac', 'extender_ip', 'server_ip', 'gateway', 'dns', 'subnet_mask', 'interface', 'lease_minutes', 'address_plan_confirmed')
    $values = @{}
    if ($Configuration -is [System.Collections.IDictionary]) {
        foreach ($key in $Configuration.Keys) {
            if ($key -isnot [string] -or $key -cnotin $allowed) { throw "Unknown configuration field: $key" }
            $values[$key] = $Configuration[$key]
        }
    } elseif ($Configuration -is [pscustomobject]) {
        foreach ($property in $Configuration.PSObject.Properties) {
            if ($property.Name -cnotin $allowed) { throw "Unknown configuration field: $($property.Name)" }
            $values[$property.Name] = $property.Value
        }
    } else { throw 'Configuration must be a JSON object.' }
    foreach ($key in $allowed) { if (-not $values.ContainsKey($key)) { throw "Missing configuration field: $key" } }
    foreach ($key in @('extender_mac', 'extender_ip', 'server_ip', 'gateway', 'dns', 'subnet_mask', 'interface')) {
        if ($values[$key] -isnot [string] -or $values[$key] -match '[\x00-\x1f\x7f]') { throw "$key must be a string without control characters." }
    }
    $mac = $values.extender_mac
    if ($mac -notmatch '^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$') { throw 'extender_mac must contain six colon-separated hexadecimal octets.' }
    if ($mac -eq '00:00:00:00:00:00' -or ([Convert]::ToInt32($mac.Substring(0, 2), 16) -band 1) -ne 0) {
        throw 'extender_mac must be a nonzero unicast MAC address.'
    }
    $numbers = @{}
    foreach ($key in @('extender_ip', 'server_ip', 'gateway', 'dns')) {
        $numbers[$key] = ConvertTo-HelperIPv4Number $values[$key] $key
        $first = [int]$values[$key].Split('.')[0]
        if ($first -eq 0 -or $first -eq 127 -or $first -ge 224) { throw "$key must be a usable unicast IPv4 address." }
    }
    $null = Get-HelperPrefixLength $values.subnet_mask
    $mask = ConvertTo-HelperIPv4Number $values.subnet_mask 'subnet_mask'
    $network = $numbers.server_ip -band $mask
    $broadcast = $network + (4294967295 - $mask)
    foreach ($key in @('extender_ip', 'server_ip', 'gateway')) {
        if (($numbers[$key] -band $mask) -ne $network -or $numbers[$key] -eq $network -or $numbers[$key] -eq $broadcast) {
            throw 'server_ip, extender_ip and gateway must be usable hosts in the same subnet.'
        }
    }
    if (($numbers.dns -band $mask) -eq $network -and ($numbers.dns -eq $network -or $numbers.dns -eq $broadcast)) { throw 'dns cannot be the local network or broadcast address.' }
    if ($numbers.extender_ip -eq $numbers.server_ip -or $numbers.extender_ip -eq $numbers.gateway -or $numbers.server_ip -eq $numbers.gateway) {
        throw 'server_ip, extender_ip and gateway must be distinct.'
    }
    $interface = $values.interface
    if ($interface.Length -lt 1 -or $interface.Length -gt 128 -or $interface.Trim() -ne $interface -or $interface -match '[=\[\]";]' -or $interface -match '^REPLACE(?:_|$)') {
        throw 'interface must be the real Windows adapter alias, without control characters or INI delimiters.'
    }
    $lease = $values.lease_minutes
    if (($lease -isnot [int] -and $lease -isnot [long] -and $lease -isnot [uint32] -and $lease -isnot [uint64] -and $lease -isnot [int16] -and $lease -isnot [byte]) -or $lease -lt 2 -or $lease -gt 525600) {
        throw 'lease_minutes must be an integer from 2 through 525600.'
    }
    if ($values.address_plan_confirmed -isnot [bool]) { throw 'address_plan_confirmed must be a JSON boolean.' }
    if ($RequireConfirmed -and -not $values.address_plan_confirmed) {
        throw 'Confirm the address plan, reserve/exclude the helper and extender addresses, and stop other helpers before setting address_plan_confirmed to true.'
    }
    return [ordered]@{
        extender_mac = $mac.ToUpperInvariant(); extender_ip = $values.extender_ip
        server_ip = $values.server_ip; gateway = $values.gateway; dns = $values.dns
        subnet_mask = $values.subnet_mask; interface = $interface
        lease_minutes = [long]$lease; address_plan_confirmed = $values.address_plan_confirmed
    }
}

function New-HelperIni {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Configuration)
    $c = Test-HelperConfig -Configuration $Configuration
    $lines = @(
        '[TFTPD32]', 'Services=4', "DHCP LocalIP=$($c.server_ip)",
        'DHCP Ping=0', 'DHCP Double Answer=0', 'PersistantLeases=0', 'UnicastBOOTP=0',
        'Enable IPv4=1', 'Enable IPv6=0', 'UseEventLog=0', 'TftpLogFile=', 'SaveSyslogFile=',
        '', '[DHCP]', "IP_Pool=$($c.extender_ip)", 'PoolSize=0',
        "Lease (minutes)=$($c.lease_minutes)", "Gateway=$($c.gateway)", "Mask=$($c.subnet_mask)",
        "DNS=$($c.dns)", 'DNS2=', 'WINS=', 'BootFile=', 'Option42=', 'Option120=', 'DomainName=', 'Lease_NumLeases=0',
        'AddOptionNumber1=60', 'AddOptionValue1=s ARCADYAN',
        'AddOptionNumber2=125',
        'AddOptionValue2=x 00:00:0d:e9:21:04:06:38:38:30:33:35:35:05:10:47:30:30:30:30:30:30:30:30:30:30:30:30:30:30:30:06:05:47:33:31:30:30'
    )
    for ($i = 3; $i -le 10; $i++) { $lines += "AddOptionNumber$i=0"; $lines += "AddOptionValue$i=" }
    $lines += "$($c.extender_mac)=$($c.extender_ip)"
    return ($lines -join "`r`n") + "`r`n"
}

function Assert-HelperRegistrySafe {
    param([string]$ExtenderMac)
    # Unknown MACs may fall back to this registry key even with an isolated INI.
    foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
        $root = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, $view)
        $key = $null
        try {
            $key = $root.OpenSubKey('SOFTWARE\TFTPD32\DHCP')
            if ($null -ne $key) {
                foreach ($name in $key.GetValueNames()) {
                    if ($name -match '^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$' -and $name -ne $ExtenderMac) {
                        throw "Another static Tftpd32 registry mapping exists ($name). No registry settings were changed."
                    }
                }
            }
        } finally { if ($null -ne $key) { $key.Dispose() }; $root.Dispose() }
    }
}

function New-HelperRuntimeDirectory {
    $path = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime'
    $driveRoot = [IO.Path]::GetPathRoot($path)
    if ($driveRoot.StartsWith('\\') -or (New-Object IO.DriveInfo($driveRoot)).DriveType -eq [IO.DriveType]::Network) { throw 'Use a local filesystem checkout for the private runtime directory.' }
    if (Test-Path -LiteralPath $path) {
        $item = Get-Item -LiteralPath $path -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw '.runtime must be a normal local directory.' }
    } else { $null = New-Item -ItemType Directory -Path $path }
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($principal in @($sid, [Security.Principal.SecurityIdentifier]'S-1-5-18', [Security.Principal.SecurityIdentifier]'S-1-5-32-544')) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($principal, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $null = $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $path -AclObject $acl
    $run = Join-Path $path ('windows-' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $run
    return $run
}

function Invoke-HelperMain {
    [CmdletBinding()]
    param([string]$ConfigPath, [string]$ProgramPath, [switch]$ValidateOnly)
    $ErrorActionPreference = 'Stop'
    $raw = ConvertFrom-HelperJson -Json (Get-Content -LiteralPath $ConfigPath -Raw)
    $c = Test-HelperConfig -Configuration $raw -RequireConfirmed:(-not $ValidateOnly)
    $ini = New-HelperIni -Configuration $c
    if ($ValidateOnly) { Write-Output $ini; return }

    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run Start-Helper.cmd from an Administrator terminal.' }
    $binary = (Resolve-Path -LiteralPath $ProgramPath).ProviderPath
    if ((Get-Item -LiteralPath $binary).PSIsContainer -or (Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash -ne '43a8a79001510fa969ae31521aef550ff4c9c7771e903792b60a499ecf48b388') {
        throw 'The executable must match the pinned official Tftpd64 v4.74 portable binary. See windows/DEPENDENCIES.md.'
    }
    if (Get-Process -Name 'tftpd64', 'tftpd32', 'tftpd64_svc', 'tftpd32_svc' -ErrorAction SilentlyContinue) { throw 'Another Tftpd32/Tftpd64 instance is running; it was not stopped.' }
    if (@(Get-NetUDPEndpoint | Where-Object { $_.LocalPort -eq 67 }).Count -ne 0) { throw 'UDP67 is already in use; the existing service was not changed.' }
    $adapters = @(Get-NetAdapter -IncludeHidden | Where-Object { $_.Name -eq $c.interface })
    if ($adapters.Count -ne 1) { throw 'The configured Windows adapter alias does not identify one adapter.' }
    $adapter = $adapters[0]
    if ($adapter.Status -ne 'Up' -or -not $adapter.HardwareInterface -or ([string]$adapter.MediaType -ne '802.3' -and [int]$adapter.NdisPhysicalMedium -ne 14)) { throw 'Use an active physical wired Ethernet adapter.' }
    $addresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 | Where-Object { $_.IPAddress -eq $c.server_ip -and $_.AddressState -eq 'Preferred' })
    if ($addresses.Count -ne 1 -or $addresses[0].PrefixLength -ne (Get-HelperPrefixLength $c.subnet_mask)) { throw 'The selected Ethernet adapter must already have server_ip with the configured subnet mask.' }
    $routes = @(Get-NetRoute -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' | Where-Object { $_.NextHop -eq $c.gateway })
    if ($routes.Count -eq 0) { throw 'The selected Ethernet gateway must already match the configured router.' }
    $profiles = @(Get-NetConnectionProfile -InterfaceIndex $adapter.ifIndex)
    if ($profiles.Count -ne 1 -or $profiles[0].NetworkCategory -ne 'Private') { throw 'The wired home connection must already be marked Private. No profile was changed.' }
    Assert-HelperRegistrySafe -ExtenderMac $c.extender_mac

    $oldIniEnvironment = $env:TFTP_INI
    $firewallRule = 'E3200-DHCP-Helper-' + [guid]::NewGuid().ToString('N')
    $ruleCreated = $false; $process = $null; $transcriptStarted = $false
    try {
        $runtime = New-HelperRuntimeDirectory
        Start-Transcript -LiteralPath (Join-Path $runtime 'helper.log') | Out-Null
        $transcriptStarted = $true
        $iniPath = Join-Path $runtime 'tftpd32.ini'
        [IO.File]::WriteAllText($iniPath, $ini, [Text.Encoding]::ASCII)
        $env:TFTP_INI = $iniPath
        New-NetFirewallRule -Name $firewallRule -DisplayName 'Temporary E3200 DHCP helper' -Direction Inbound -Action Allow -Program $binary -Protocol UDP -LocalPort 67 -RemotePort 68 -Profile Private -InterfaceAlias $adapter.Name | Out-Null
        $ruleCreated = $true
        Write-Host "Starting DHCP for $($c.extender_mac) at $($c.extender_ip); gateway $($c.gateway)."
        Write-Host "Runtime configuration and launcher log: $runtime"
        Write-Host 'Keep this console and Tftpd64 open. Close Tftpd64 to stop. Do not change its pool or services.'
        $process = Start-Process -FilePath $binary -WorkingDirectory $runtime -PassThru
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) { throw "Tftpd64 exited with code $($process.ExitCode)." }
    } finally {
        $env:TFTP_INI = $oldIniEnvironment
        if ($null -ne $process) {
            try { $process.Refresh(); if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() } }
            catch { Write-Warning 'Check that this helper Tftpd64 window has closed.' }
        }
        if ($ruleCreated) {
            try { Remove-NetFirewallRule -Name $firewallRule -ErrorAction Stop }
            catch { Write-Warning "Remove the temporary firewall rule manually: $firewallRule" }
        }
        if ($transcriptStarted) { try { Stop-Transcript | Out-Null } catch { } }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-HelperMain -ConfigPath $Config -ProgramPath $Program -ValidateOnly:$ValidateOnly }
    catch { Write-Error ('Helper stopped: ' + $_.Exception.Message) -ErrorAction Continue; exit 1 }
}
