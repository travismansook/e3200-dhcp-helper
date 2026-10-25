# Windows setup

**For the simpler download-and-open version, use the [Windows download guide](downloads.md#windows).** The steps below describe running the source scripts yourself.

The native launcher uses Windows PowerShell 5.1 and Tftpd64. Python is not required.

## 1. Obtain the dependency

Download the **64-bit portable v4.74 ZIP** from the [official Tftpd64 release](https://github.com/PJO2/tftpd64/releases/tag/v4.74). Extract it so `windows/vendor/tftpd64.exe` exists. The launcher checks the executable hash before starting it.

See [dependency details and SHA-256 values](../windows/DEPENDENCIES.md). Launch the executable through the wrapper, which selects DHCP only and restricts its scope.

## 2. Configure the plan

From PowerShell in the repository:

```powershell
Copy-Item .\config.example.json .\config.local.json
Get-NetAdapter
Get-NetIPConfiguration
```

Edit the local JSON. Use your physical wired adapter's actual alias for `interface`, its stable address for `server_ip` and your extender's MAC for `extender_mac`. Check address exclusions and existing leases before setting `address_plan_confirmed` to `true`.

The wired connection must already be marked **Private**, with the configured IPv4/mask and router gateway. The launcher does not change these settings.

## 3. Validate offline

```powershell
.\windows\Start-Helper.cmd -Config .\config.local.json -ValidateOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows\Test-Helper.ps1
```

Validation writes no files and requires no administrator access, external binary or network access. It cannot establish that addresses are unused or that the extender will accept an offer.

The wrapper selects an execution policy for its own process only. It does not change the computer's saved PowerShell policy.

## 4. Start

Open an Administrator terminal, return to the repository and run:

```powershell
.\windows\Start-Helper.cmd -Config .\config.local.json
```

Keep both the launcher terminal and Tftpd64 window open. Close Tftpd64 to stop the helper. Its generated pool and service settings should remain unchanged.

The wrapper stops on another DHCP listener, an interface mismatch or unexpected saved static mappings. Resolve the reported condition instead of bypassing it. It changes neither the registry nor machine-wide execution policy.

## 5. Verify and stop

Observe the extender's accepted lease, renewal and recovery after a controlled restart. Confirm the router still serves unrelated clients.

On normal exit, the wrapper removes its own temporary inbound firewall rule. After a forced termination, inspect its remaining process and rules as described in [dependency and cleanup details](../windows/DEPENDENCIES.md). Keep runtime files private.

The original prototype's field result is documented in [validation](validation.md); the generalized launcher requires its own runtime validation.
