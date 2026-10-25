# Linux setup — experimental

Linux runtime support is experimental. Validate the foreground helper before installing or enabling a persistent service.

## Dependencies

On Debian or Ubuntu, `dnsmasq-base` provides the executable without installing the distribution's general dnsmasq service:

```sh
sudo apt update
sudo apt install python3 dnsmasq-base
python3 --version
dnsmasq --version
ip -br -4 address
```

Use Python 3.10+. Identify the physical wired interface and configure its stable helper address using your normal network settings. Keep the original router's DHCP enabled and confirm both selected addresses are excluded from its dynamic pool.

## Foreground trial

```sh
python3 e3200_helper.py init --output config.local.json
```

Edit the local JSON, replace every placeholder and confirm the plan before starting:

```sh
python3 e3200_helper.py check --config config.local.json
python3 e3200_helper.py render --config config.local.json --format dnsmasq
sudo python3 e3200_helper.py run --config config.local.json
```

Verify lease acceptance, renewal, extender restart and unrelated-client behavior. Stop the foreground helper before installing a service.

The host firewall must allow DHCP traffic on the selected physical interface: client UDP 68 to helper UDP 67, including bootstrap/broadcast traffic, and replies from UDP 67 to 68. Scripts leave firewall policies unchanged. A loaded, incompatible dnsmasq AppArmor profile causes a stop rather than an automatic policy change.

## Optional Ubuntu systemd service

Read the installer and its reported paths before activation. Follow its supported command-line options; only use persistence after a successful foreground trial.

```sh
sudo bash unix/install-linux-service.sh --config /absolute/path/to/config.local.json
# Explicitly enable/start after reviewing the installed unit:
sudo bash unix/install-linux-service.sh --config /absolute/path/to/config.local.json --start
```

The no-`--start` invocation leaves the service disabled. Keep the host connected and awake. After activation, verify startup following a host restart and check the journal.

Uninstall the owned service with:

```sh
sudo bash unix/uninstall-linux-service.sh
```

Stopping/uninstalling the helper does not restore an earlier helper or change the router's DHCP configuration. Review the script's output for retained files and cleanup.

Offline checks do not establish a Linux field result. Record your actual OS, dnsmasq version, extender firmware and test duration using the [validation checklist](validation.md).
