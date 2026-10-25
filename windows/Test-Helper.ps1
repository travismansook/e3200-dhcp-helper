# Offline tests: no administrator, network access, external binary, or Pester needed.
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'Start-Helper.ps1'
$tokens = $null; $errors = $null
$null = [Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw ($errors | Out-String) }
. $launcher

function Assert-HelperTest {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Assert-HelperRejects {
    param([scriptblock]$Action, [string]$Message)
    try { $null = & $Action } catch { return }
    throw "Expected rejection: $Message"
}
function New-TestConfiguration {
    return @{
        extender_mac = 'AA:BB:CC:DD:EE:FF'; extender_ip = '192.168.1.250'
        server_ip = '192.168.1.240'; gateway = '192.168.1.1'; dns = '192.168.1.1'
        subnet_mask = '255.255.255.0'; interface = 'Ethernet'; lease_minutes = 60
        address_plan_confirmed = $false
    }
}

$good = New-TestConfiguration
$json = $good | ConvertTo-Json -Compress
$fromJson = Test-HelperConfig (ConvertFrom-HelperJson $json)
Assert-HelperTest ($fromJson.dns -eq $good.dns) 'Unique JSON fields must load normally.'
$duplicateDns = $json -replace '"dns"\s*:', '"dns":"8.8.8.8","dns":'
Assert-HelperRejects { ConvertFrom-HelperJson $duplicateDns } 'Duplicate JSON property names.'
$escapedDuplicate = $json -replace '"dns"\s*:', '"d\u006es":"8.8.8.8","dns":'
Assert-HelperRejects { ConvertFrom-HelperJson $escapedDuplicate } 'Escaped duplicate JSON property names.'
$caseDuplicate = $json -replace '"dns"\s*:', '"DNS":"8.8.8.8","dns":'
Assert-HelperRejects { ConvertFrom-HelperJson $caseDuplicate } 'Case aliases cannot bypass the strict schema.'
$duplicateConfirmation = $json -replace '"address_plan_confirmed"\s*:\s*false', '"address_plan_confirmed":false,"address_plan_confirmed":true'
Assert-HelperRejects { ConvertFrom-HelperJson $duplicateConfirmation } 'Duplicate confirmation must not enable startup.'
$escapedUnique = $json -replace '"dns"\s*:', '"d\u006es":'
$decodedUnique = Test-HelperConfig (ConvertFrom-HelperJson $escapedUnique)
Assert-HelperTest ($decodedUnique.dns -eq $good.dns) 'A unique escaped property name must decode normally.'
$quotedValue = ConvertFrom-HelperJson '{"interface":"Ethernet \"dns\": text","dns":"192.168.1.1"}'
Assert-HelperTest ($quotedValue.interface -eq 'Ethernet "dns": text') 'Quoted property-like text inside a string must not be treated as a key.'
Assert-HelperRejects { ConvertFrom-HelperJson ('[' + $json + ']') } 'A one-element root array must not become an accepted object.'
$normalized = Test-HelperConfig $good
Assert-HelperTest ($normalized.extender_mac -eq 'AA:BB:CC:DD:EE:FF') 'MAC normalization failed.'
Assert-HelperTest (-not $normalized.address_plan_confirmed) 'Offline validation must allow an unconfirmed plan.'
Assert-HelperRejects { Test-HelperConfig $good -RequireConfirmed } 'Startup requires explicit confirmation.'
$confirmed = New-TestConfiguration; $confirmed.address_plan_confirmed = $true
$null = Test-HelperConfig $confirmed -RequireConfirmed
foreach ($case in @(
    @('extender_mac', '01:00:00:00:00:01'), @('extender_mac', 'FF:FF:FF:FF:FF:FF'),
    @('extender_mac', '00:00:00:00:00:00'), @('extender_mac', 'AA-BB-CC-DD-EE-FF'),
    @('server_ip', '192.168.2.240'), @('server_ip', '192.168.1.250'),
    @('extender_ip', '192.168.1.0'), @('extender_ip', '192.168.1.255'),
    @('gateway', '192.168.1.240'), @('gateway', '192.168.2.1'),
    @('dns', '224.0.0.1'), @('dns', '127.0.0.1'), @('dns', '192.168.1.255'),
    @('server_ip', '192.168.001.240'),
    @('subnet_mask', '255.0.255.0'), @('subnet_mask', '255.255.255.255'),
    @('lease_minutes', 1), @('lease_minutes', 525601), @('lease_minutes', '60'), @('lease_minutes', 2.5),
    @('address_plan_confirmed', 'true'), @('interface', 'REPLACE_WITH_INTERFACE'),
    @('interface', "Ethernet`nPoolSize=100"), @('extender_ip', "192.168.1.250`r`nPoolSize=100")
)) {
    $bad = New-TestConfiguration; $bad[$case[0]] = $case[1]
    Assert-HelperRejects { Test-HelperConfig $bad } ([string]$case[0] + ': ' + [string]$case[1])
}
$bad = New-TestConfiguration; $bad.extra = 'PoolSize=100'
Assert-HelperRejects { Test-HelperConfig $bad } 'Unknown fields.'
$bad = New-TestConfiguration; $bad.Remove('gateway')
Assert-HelperRejects { Test-HelperConfig $bad } 'Missing fields.'
Assert-HelperRejects { Test-HelperConfig @('not', 'an', 'object') } 'Non-object configuration.'
foreach ($boundary in @(2, 525600)) {
    $valid = New-TestConfiguration; $valid.lease_minutes = $boundary
    $null = Test-HelperConfig $valid
}
$valid = New-TestConfiguration; $valid.extender_mac = 'aa:bb:cc:dd:ee:ff'; $valid.dns = '8.8.8.8'
Assert-HelperTest ((Test-HelperConfig $valid).extender_mac -ceq 'AA:BB:CC:DD:EE:FF') 'Lowercase MAC must normalize.'

$ini = New-HelperIni $good
Assert-HelperTest ($ini -match '(?m)^Services=4\r?$') 'Only DHCP may be enabled.'
Assert-HelperTest ($ini -match '(?m)^PoolSize=0\r?$') 'Dynamic pool must be disabled.'
Assert-HelperTest ($ini -match '(?m)^DHCP LocalIP=192\.168\.1\.240\r?$') 'Bind address mismatch.'
Assert-HelperTest ($ini -match '(?m)^Lease \(minutes\)=60\r?$') 'Lease must remain in minutes.'
Assert-HelperTest ([regex]::Matches($ini, '(?m)^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}=').Count -eq 1) 'INI must contain exactly one static MAC mapping.'
Assert-HelperTest ($ini -match '(?m)^AA:BB:CC:DD:EE:FF=192\.168\.1\.250\r?$') 'Static mapping mismatch.'
Assert-HelperTest ([regex]::Matches($ini, '(?m)^AddOptionNumber[0-9]+=').Count -eq 10) 'Every option number slot must be reset.'
Assert-HelperTest ([regex]::Matches($ini, '(?m)^AddOptionValue[0-9]+=').Count -eq 10) 'Every option value slot must be reset.'
foreach ($i in 3..10) { Assert-HelperTest ($ini -match "(?m)^AddOptionNumber$i=0\r?$") "Option slot $i must be disabled." }
Assert-HelperTest ($ini -match '(?m)^AddOptionNumber1=60\r?$' -and $ini -match '(?m)^AddOptionValue1=s ARCADYAN\r?$') 'Vendor option 60 mismatch.'
$payload = ([regex]::Match($ini, '(?m)^AddOptionValue2=x ([0-9a-f:]+)\r?$')).Groups[1].Value
$bytes = @($payload.Split(':') | ForEach-Object { [Convert]::ToByte($_, 16) })
Assert-HelperTest ($bytes.Count -eq 38) 'Option 125 must contain 38 bytes.'
Assert-HelperTest (($bytes[0..4] -join ',') -eq '0,0,13,233,33') 'Option 125 enterprise or data length mismatch.'
Assert-HelperTest ([Text.Encoding]::ASCII.GetString([byte[]]$bytes[7..12]) -eq '880355') 'Gateway OUI mismatch.'
Assert-HelperTest ([Text.Encoding]::ASCII.GetString([byte[]]$bytes[33..37]) -eq 'G3100') 'Gateway product class mismatch.'
Write-Host 'Windows offline tests passed. No helper, firewall rule, or service was started.'
