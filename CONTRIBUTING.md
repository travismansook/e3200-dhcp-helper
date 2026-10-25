# Contributing

Changes should preserve the one-extender scope and make operational behavior easier to inspect.

Read [how it works](docs/how-it-works.md), [validation](docs/validation.md) and [security](SECURITY.md). Describe the affected platform, expected behavior and whether evidence comes from source review, automated checks or a live trial.

## Run offline checks

```sh
python3 -m unittest discover -s tests -v
```

Windows also provides `windows/Test-Helper.ps1`. CI runs configuration, parser and shell checks without starting a DHCP server.

Use synthetic inputs for parsing, option encoding, timestamp analysis and failure paths. Never add raw household logs, real MACs/serials, IPv6 addresses, screenshots, credentials or private filesystem paths.

For scope or cleanup changes, cover negative cases such as unmatched clients, another listener, a wrong interface/address, inherited settings, malformed input and interrupted shutdown.

Live testing belongs on a LAN you administer, with an explicit address plan and one helper. Record the OS, engine version, extender firmware and observation period. Keep experimental support labeled until backed by evidence.

Do not bundle third-party executables or copy upstream source without checking its license. Report actual commands/results instead of inventing test counts. Security findings follow [SECURITY.md](SECURITY.md).
