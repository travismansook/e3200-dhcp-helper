# Download, open, and follow the questions

Use the **[Releases page](https://github.com/travismansook/e3200-dhcp-helper/releases)**. Choose one of the named program downloads below. You do not need to build anything, install Python, or edit JSON.

These are preview builds: packaged startup tests are separate from live testing with an extender. The original Windows prototype obtained a lease; the generalized launchers need more field validation. Linux remains experimental.

## Windows

1. Download **E3200-Helper-Windows-x64.zip** for a 64-bit Windows 10/11 PC.
2. Right-click the ZIP and choose **Extract All**. Open the extracted folder.
3. Double-click **Open E3200 Helper.cmd**. Keep the `program` folder next to it.
4. Windows asks for administrator approval. The guided setup opens in a console.
5. Choose the connected Ethernet adapter, enter the E3200's MAC/address, and review the lease and address-plan questions.
6. On first use, approve downloading Tftpd64 from its official GitHub release. The launcher checks both download and executable checksums.

Keep the setup console and Tftpd64 window open while serving. Close Tftpd64 to stop; the existing Windows wrapper removes its temporary firewall rule on normal exit. Closing the console forcibly can prevent normal cleanup; see the [cleanup instructions](../windows/DEPENDENCIES.md).

The home Ethernet network must already be marked Private. The helper reports a mismatch rather than changing the network profile or router.

## macOS

1. Under **Apple menu → About This Mac**, check whether the Mac says **Chip** (Apple Silicon/M1 or newer) or **Processor** (Intel).
2. Download **E3200-Helper-macOS-AppleSilicon.zip** or **E3200-Helper-macOS-Intel.zip** accordingly. These builds require **macOS 15 or newer**.
3. Extract the ZIP and keep the entire folder together.
4. Open **Open E3200 Helper.command**. Terminal opens the guided setup.
5. Use a working Ethernet connection and answer the questions. No Homebrew or Python installation is needed.
6. When starting, macOS requests administrator access in Terminal. Password typing may not display characters.

Keep Terminal open while serving. Press **Control+C** to stop the helper normally. The package contains the DHCP engine, its corresponding source archive, build instructions and licenses.

These community builds are unsigned and not notarized. macOS may require your manual review before opening them. No launcher disables Gatekeeper or modifies security settings. Use the source guide if your OS does not allow a community download.

## Ubuntu

1. Download **E3200-Helper-Ubuntu-amd64.deb** for Ubuntu **22.04 or newer**, on a 64-bit Intel/AMD computer.
2. Open the file with your software/package installer and install it. It obtains the normal `dnsmasq-base`, `iproute2` and `sudo` dependencies.
3. Open **E3200 DHCP Helper** from Applications. A terminal opens the guided setup.
4. Answer the questions and approve administrator access when starting.

Python is included. Installing the package does **not** start DHCP, add a boot service, or replace the router's DHCP server. Keep the terminal open while serving; press **Control+C** to stop.

Linux runtime support is experimental. A preflight may stop if the machine has an incompatible dnsmasq AppArmor profile or another DHCP listener. The package does not disable AppArmor or alter firewall policies. Investigate the reported condition using the [source Linux guide](linux.md) instead of bypassing it.

## What the questions mean

- **Adapter:** the active Ethernet connection on your home LAN. Its current address and router gateway are filled in for you.
- **E3200 MAC:** the extender's own device address, from its label or settings. Do not enter a phone's MAC or a CHR30A's MAC.
- **E3200 IP:** a free address you have set aside so the router will not assign it to someone else. A suggestion is not an availability test.
- **Lease:** start with one hour to check renewal. You can later choose 24 hours or 365 days. A long lease still needs a helper for renewal or a new request after restart.
- **Address-plan confirmation:** check existing leases/manual assignments, keep the helper computer's address stable, and reserve/exclude the chosen addresses. The launcher does not change the router for you.

The setup saves these details privately on the helper computer, so later launches can reuse them. To change them, choose **SETUP** when the saved settings are shown.

After the extender accepts its lease, open its assigned address in a browser on your home network. For example, an extender configured as `192.168.1.250` can be reached at `https://192.168.1.250`.

## Choosing the correct download

Download the ZIP or Ubuntu installer with **E3200-Helper** in its name. GitHub's automatically generated **Source code** downloads contain the scripts; they are not the ready-to-open programs.

Windows/macOS may identify unsigned community software as unfamiliar. The release includes **SHA256SUMS.txt** for the program downloads and **build-info.json** inside each package. Review the source and build record if needed; the project does not supply a trusted code-signing identity.

For contributors: release builds run on native Windows, Apple Silicon, Intel Mac and Ubuntu CI runners. Bump `VERSION` to publish a new version, or run the **Build downloadable programs** workflow manually. Published version assets are not silently replaced.
