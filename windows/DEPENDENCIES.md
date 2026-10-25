# Windows dependency and operation

The native Windows launcher requires Windows PowerShell 5.1 and its built-in networking/firewall modules. Python is not required. No service or startup task is installed.

## Obtain Tftpd64

Download **[tftpd64_portable_v4.74.zip](https://github.com/PJO2/tftpd64/releases/download/v4.74/tftpd64_portable_v4.74.zip)** from the [official release](https://github.com/PJO2/tftpd64/releases/tag/v4.74). Extract it so `windows/vendor/tftpd64.exe` exists. Use this project's wrapper to select the intended DHCP-only configuration.

| File | SHA-256 |
|---|---|
| Portable ZIP | `3ad38a71c0d7d42915429f8f02945e27bcf88161ad1028980d1364af8f76bf22` |
| Extracted executable | `43a8a79001510fa969ae31521aef550ff4c9c7771e903792b60a499ecf48b388` |

Check files using `Get-FileHash -Algorithm SHA256 -LiteralPath PATH`. Digests apply to different files. Retain upstream license notices. Another executable/version is rejected; nothing is downloaded automatically.

## Validate and run

Copy `config.example.json` to `config.local.json`. Enter your actual wired adapter alias, stable helper address, mask, gateway and extender MAC. The connection must already be Private. Confirm address exclusions before setting `address_plan_confirmed` to `true`.

```powershell
.\windows\Start-Helper.ps1 -Config .\config.local.json -ValidateOnly
.\windows\Test-Helper.ps1
```

These offline paths do not need a binary, administrator access or network activity. They write no files.

In an Administrator terminal:

```powershell
.\windows\Start-Helper.cmd -Config .\config.local.json
```

`-Program PATH` can select the same pinned executable elsewhere. Keep the terminal and Tftpd64 open. Close Tftpd64 to stop; keep its generated pool/service configuration unchanged.

## Scope, firewall and logs

The INI selects DHCP only (`Services=4`), a zero dynamic pool and one static mapping, and resets all ten option slots. Existing static registry mappings in both registry views are checked for conflicts.

The launcher adds its own inbound firewall rule scoped to the executable, Private profile, selected interface and UDP 68→67. It removes that rule on ordinary exit. It does not change addresses, routes, network profiles, registry state or other services. Existing outbound-blocking policies may need a separately reviewed narrow allowance.

Runtime INIs and launcher transcripts stay under `.runtime/` with restricted local permissions. Transcripts do not export Tftpd64's DHCP tab. Runtime files and vendor binaries are ignored by Git.

After a forced termination, close this helper's Tftpd64 window, inspect `Get-NetFirewallRule -Name 'E3200-DHCP-Helper-*'` and remove only this run's rule if it remains. Keep the computer awake and available for DHCP. Test actual acceptance, renewal and restart recovery independently of offline checks.
