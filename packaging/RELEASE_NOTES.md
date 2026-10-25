Download the file for your computer below. **These are ready-to-open builds; you do not need to build the project, install Python, or edit JSON.**

| Computer | Download | Open after extracting/installing |
|---|---|---|
| Windows 10/11, 64-bit | **E3200-Helper-Windows-x64.zip** | **Open E3200 Helper.cmd** |
| Mac with Apple Silicon (M1 or newer) | **E3200-Helper-macOS-AppleSilicon.zip** | **Open E3200 Helper.command** |
| Intel Mac | **E3200-Helper-macOS-Intel.zip** | **Open E3200 Helper.command** |
| Ubuntu 22.04 or newer, Intel/AMD 64-bit | **E3200-Helper-Ubuntu-amd64.deb** | Install it, then open **E3200 DHCP Helper** from Applications |

Keep the entire extracted folder together. The guided setup opens in a terminal and asks for your extender's MAC address, chosen address and lease duration. It reads this computer's active Ethernet settings for you, then asks you to verify that the selected addresses cannot conflict with other devices. It does not change your router's DHCP pool.

Windows asks permission to fetch its pinned Tftpd64 dependency from the official release on first use. macOS includes dnsmasq and its corresponding source/license files. Ubuntu obtains dnsmasq-base through its normal package dependencies. Administrator approval is needed when the helper starts.

Keep the computer awake and helper open. After the E3200 accepts its lease, use its assigned address to open its settings page. Start with a one-hour lease; longer leases do not eliminate renewal or restart requests.

**Preview release:** packaged startup and offline checks are separate from live extender testing. Linux remains experimental, including potential AppArmor startup restrictions. These community builds are unsigned, so Windows/macOS may ask you to review an unfamiliar download. Mac builds require macOS 15 or newer.

Use the named program downloads above. GitHub's automatically added **Source code** archives are for people who want the scripts.

[Simple setup guide](https://github.com/travismansook/e3200-dhcp-helper/blob/main/docs/downloads.md) · [What the helper fixes](https://github.com/travismansook/e3200-dhcp-helper#readme) · [Validation and limits](https://github.com/travismansook/e3200-dhcp-helper/blob/main/docs/validation.md)

SHA256SUMS.txt lists checksums for the four program downloads. The helper changes DHCP compatibility for one configured extender; it does not provide full vendor-supported CHR30A/E3200 integration.
