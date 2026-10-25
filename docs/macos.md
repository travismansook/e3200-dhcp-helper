# macOS setup

**For the simpler download-and-open version, use the [Mac download guide](downloads.md#macos).** That download includes Python and dnsmasq; the steps below describe running the source scripts yourself.

Use Python 3.10+, dnsmasq and a stable wired LAN connection. The original Mac configuration was syntax-checked with Homebrew dnsmasq 2.93; the public runner is generalized code.

## Prepare

Using Homebrew:

```sh
brew install python dnsmasq
python3 --version
dnsmasq --version
networksetup -listallhardwareports
```

Identify the wired adapter's device name, such as `en0` or `en5`. Do not assume Ethernet is always `en0`. Its IPv4 address/mask and default gateway must match your plan.

Keep the router's DHCP enabled, exclude the helper/extender addresses and stop any previous helper. The scoped runner should run independently of any generic `brew services` dnsmasq instance.

## Configure and inspect

```sh
python3 e3200_helper.py init --output config.local.json
```

Edit the JSON, replacing all examples. Start with `lease_minutes: 60` and confirm the address plan before serving.

```sh
python3 e3200_helper.py check --config config.local.json
python3 e3200_helper.py render --config config.local.json --format dnsmasq
```

The output should contain one static host mapping, a static-only range, an ignore rule for unmatched clients and the two required vendor options.

## Run

```sh
sudo python3 e3200_helper.py run --config config.local.json
```

Ensure the selected interpreter is Python 3.10+. Stop using Ctrl+C and verify the helper has stopped before starting another instance. Keep the Mac awake, connected and available for lease renewal or reacquisition.

Wired operation is preferred. Any explicit wireless opt-in offered by the runner is experimental; sleep, roaming or an interface/address change can interrupt helper availability. No launch daemon or automatic startup is installed by this guide.

The host firewall must permit DHCP on the intended LAN interface. The runner does not disable a firewall or change its policies. Review a failed preflight before retrying.

Follow the [validation checklist](validation.md). A syntax check is separate from a successful network trial.
