# BigLinux compatibility improvements (biglinux-improve-compatibility)

Makes programs from the AUR, converted .deb and .rpm packages and vendor installers work on BigLinux without manual setup.

The package installs pacman hooks that adjust a third-party program right after pacman installs, upgrades or removes it, systemd drop-ins with BigLinux defaults, and a few helpers that programs packaged for Debian expect.

## Install

It comes with every BigLinux edition. To install it on a system built from the BigLinux repositories:

```sh
sudo pacman -S biglinux-improve-compatibility
```

## Layout

| Path in the package | What it holds |
|---|---|
| `usr/share/libalpm/hooks/` | Pacman hooks: which package triggers what, and when |
| `usr/share/libalpm/scripts/` | The scripts those hooks run |
| `usr/lib/systemd/*/*.d/`, `usr/lib/systemd/*.conf.d/` | Drop-ins that change units and settings of other packages |
| `usr/lib/systemd/system/`, `usr/lib/systemd/user/` | Units of this package |
| `usr/bin/`, `usr/lib/init/`, `lib/lsb/` | Boot helpers and the Debian init-system-helpers |
| `usr/local/bin/` | Wrappers found before `/usr/bin` in `PATH` |
| `etc/` | Linker paths and kernel module options |
| `locale/` | Translation catalogs (source of `usr/share/locale/`) |
| `pkgbuild/` | Recipe and install scriptlet |
| `tests/` | Tests of the repository migration, legacy init and JamesDSP logic |

---

## How a hook works

Pacman reads every `*.hook` in `/usr/share/libalpm/hooks/` at each transaction, in alphabetical order (see `man 5 alpm-hooks`). A hook names the packages or paths that trigger it, the operations (`Install`, `Upgrade`, `Remove`) and when it runs:

- `PostTransaction` hooks set something up once the package files are in place.
- `PreTransaction` hooks undo it before removal, while the files they need (a unit to disable, a menu entry to compare with) still exist.

A `PostTransaction` hook never runs when the transaction fails, and the hooks a package ships are gone once it is removed. Hooks that set something up for a new installation trigger on `Install` alone, so a person who later disables a service or leaves a group is not overridden by the next upgrade.

Every script checks before it acts, so running it again changes nothing.

## Pacman hooks

### Kernel and libraries

| Hook | Runs | What it does |
|---|---|---|
| `biglinux-improve-compatibility` | after kernels, this package, `dav1d` or `rav1e` change, and after a kernel is removed | Links `/usr/src/linux-headers-<version>` to each kernel's headers and removes the links of removed kernels; links libraries under the older sonames prebuilt programs request (`libvpx.so.8`, `libtiff.so.5` and others) |
| `biglinux-improve-compatibility-remove` | before this package is removed | Removes the kernel header links |
| `biglinux-improve-compatibility-pango`, `-pango-remove` | after `pango` or this package changes; before removal | Links `libpangox`, which Pango no longer ships, to `libpangoxft` |
| `biglinux-old-sysvinit-autostart` | after a package installs a file in `/etc/init.d` | Starts SysV init scripts that have no systemd unit (`usr/bin/biglinux-improve-compatibility`) |

### Services of third-party packages

These packages ship a service that stays off after installation. The hooks call `biglinux-improve-compatibility-service enable <unit>` after installation and `disable <unit>` before removal.

| Hook | Package | Unit |
|---|---|---|
| `biglinux-improve-compatibility-cisco-anyconnect` | `cisco-anyconnect` | `vpnagentd.service` |
| `biglinux-improve-compatibility-epson-printer-utility` | `epson-printer-utility` | `ecbd.service` |
| `biglinux-improve-compatibility-lact` | `lact` | `lactd.service` |
| `biglinux-improve-compatibility-nginx` | `nginx` | `nginx.service` |
| `biglinux-improve-compatibility-pcsclite` | `pcsclite` | `pcscd.service` |
| `biglinux-improve-compatibility-php-fpm` | `php-fpm` | `php-fpm.service` |

Each has a `-remove` twin.

### Programs that need setup

| Hook | Runs | What it does |
|---|---|---|
| `biglinux-docker`, `-docker-remove` | after `docker` is installed; before removal | Adds every person to the `docker` group and starts Docker; undoes it |
| `biglinux-virtualbox`, `-virtualbox-remove` | after `virtualbox` is installed; after removal | Adds every person to `vboxusers`, which VirtualBox requires for USB devices, and loads the modules; undoes it |
| `z-biglinux-virt-manager-config-install`, `-remove` | after `libvirt`, `virt-manager` or `biglinux-virt-manager-config` is installed; before `libvirt` or `biglinux-virt-manager-config` is removed | Group membership, a default network that avoids the host's subnet, bridging and libvirtd at boot; the removal restores the network saved before the change. The `z-` prefix runs it after the libvirt packages' own hooks |
| `biglinux-improve-compatibility-corectrl`, `-corectrl-remove` | after `corectrl` is installed; before removal | AMD GPU kernel parameter, a polkit rule per person and autostart; the removal keeps files a person changed |
| `biglinux-improve-compatibility-distrobox`, `-distrobox-remove` | after `distrobox` changes; before removal | Adjusts two distrobox scripts and sets the BigLinux Arch image as default container |
| `biglinux-improve-compatibility-netspeed` | after the network speed widget changes | Declares the package structure its metadata omits, so Plasma 6 lists it |
| `biglinux-osprober` | after `os-prober` changes | Keeps Timeshift btrfs snapshots out of the GRUB menu |
| `biglinux-rtl88x2bu`, `-rtl88x2bu-remove` | after `rtl88x2bu-dkms-git` is installed; after removal | Blacklists the in-kernel `rtw88_8822bu` driver in favor of the DKMS one |
| `code-insiders-focus-wayland-install`, `-remove` | after `code-insiders-bin` changes; before this package is removed | Points the VS Code Insiders menu entry at its `/usr/local/bin` wrapper |
| `biglinux-improve-compatibility-repositories` | after this package changes | Keeps `pacman.conf` on the current BigLinux repositories; the script's header lists every rule |

## Settings for other packages

Drop-ins change a unit or a setting of another package without editing its files, so `pacman -Qkk` stays clean and the change survives that package's upgrades. Drop-ins are merged by file name across `/etc`, `/run` and `/usr/lib`, and every drop-in overrides the main file: to change one of these settings locally, use `systemctl edit` for a unit, or a file in `/etc/systemd/logind.conf.d/` named `50-biglinux.conf` or sorting after it.

| Drop-in under `usr/lib/systemd/` | Setting |
|---|---|
| `system/user@.service.d/50-biglinux.conf` | `TimeoutStopSec=5s`: logout and shutdown wait at most 5 seconds for a user's processes |
| `system/NetworkManager.service.d/50-biglinux.conf` | `Type=simple`: units ordered after NetworkManager, the display manager among them, do not wait for its D-Bus name |
| `user/plasma-plasmashell.service.d/50-biglinux.conf` | `StartLimitBurst=20`: applying a theme restarts plasmashell several times |
| `user/plasma-kwin_wayland.service.d/50-biglinux.conf` | `Nice=-11` for the compositor |
| `logind.conf.d/50-biglinux.conf` | `KillUserProcesses=yes`, `UserStopDelaySec=0` |

## Other parts

- `biglinux-auto-pstate.service` picks the `passive` Intel or `guided` AMD pstate mode at boot unless the kernel command line sets one.
- `biglinux-improve-compatibility.service` runs `usr/bin/biglinux-improve-compatibility` at boot.
- `glibc2-41-fix.path` and `.service` mark the Warsaw banking module executable-stack again whenever it changes, since glibc 2.41 refuses to load it otherwise.
- `suspend-bluetooth-fix.service` turns Bluetooth off around sleep on MediaTek MT7921 cards, which otherwise freeze when suspending.
- `jamesdsp-autostart.service`, `usr/bin/biglinux-jamesdsp-autostart` and the WirePlumber script under `usr/share/wireplumber/` start JamesDSP when its autostart option is on and keep its virtual sink from becoming the default output.
- `usr/local/bin/code`, `code-insiders` and `code-oss` raise the running VS Code window on KDE Wayland, which Electron does not do when a file is opened in it (needs `kdotool-git`); `usr/local/bin/libreoffice` sets LibreOffice's toolkit for the BigLinux desktop.
- `usr/bin/jnlp-check` opens `.jnlp` files with Java 8, offering to install it when missing.
- `usr/bin/deb-systemd-helper`, `deb-systemd-invoke`, `invoke-rc.d`, `service`, `update-rc.d`, `usr/lib/init/` and `lib/lsb/` come from Debian's init-system-helpers and lsb-base (copyright in `usr/share/doc/init-system-helpers/`), for the maintainer scripts of converted .deb packages.
- `etc/ld.so.conf.d/ubuntu-compatibility.conf` adds the Debian multiarch library paths; `etc/modprobe.d/` turns on NVIDIA kernel modesetting and keeps the `ntfs3` driver off.

## Add a hook

1. Write the hook in `usr/share/libalpm/hooks/` and, unless the action fits on one short line, a script in `usr/share/libalpm/scripts/` whose header says what it changes, why and which hook runs it.
2. Make the script check before it acts, and let a failure print its error: pacman shows it after the transaction.
3. Undo the change in a `-remove` hook that runs `PreTransaction`, while the package's files still exist.
4. To change a unit or setting of another package, ship a drop-in instead of editing its file.
5. Add the hook to the tables above.

## Translations

Only `usr/bin/jnlp-check` shows text. Its catalogs live in `locale/`, one per language of the BigLinux language set; compile each into `usr/share/locale/<lang>/LC_MESSAGES/biglinux-improve-compatibility.mo` with `msgfmt --check`.

## Tests

```sh
python -m unittest discover -s tests
```
