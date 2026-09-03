# Managed htop config

Two variants, deployed by `install_dotfiles` (see `install/install_functions.sh`)
based on `uname -s`:

- `htoprc.linux` → Linux (`uname -s` != `Darwin`)
- `htoprc.macos` → macOS (`uname -s` == `Darwin`)

Both symlink to `~/.config/htop/htoprc` via `ensure_symlink`, force-replaced on
every `setup.sh` run so the repo stays the source of truth.

`htoprc.linux` was seeded from this Linux box's prior unmanaged
`~/.config/htop/htoprc` (preserved in git history) and then edited to the
wanted settings.

## Field IDs (`fields=`)

htop 3.x's `fields=` line is a list of numeric `ProcessField` IDs — there is
no local htop source checkout on this box (`~/bin/htop_src` doesn't exist,
`install_htop.sh` was never run here), so the IDs below were verified against
the upstream `htop-dev/htop` GitHub source at tag `3.0.5` (matching
`htop --version` on this box):

- Portable fields: `Process.h`
- Linux-only fields (`PLATFORM_PROCESS_FIELDS`): `linux/ProcessField.h`
- Darwin-only fields (`PLATFORM_PROCESS_FIELDS`): `darwin/ProcessField.h`

| Name | ID | Source |
|---|---|---|
| PID | 1 | Process.h |
| COMM (Command) | 2 | Process.h |
| STATE | 3 | Process.h |
| PRIORITY | 18 | Process.h |
| NICE | 19 | Process.h |
| M_VIRT | 39 | Process.h |
| M_RESIDENT | 40 | Process.h |
| M_SHARE | 41 | linux/ProcessField.h — **Linux-only** |
| PERCENT_CPU | 47 | Process.h |
| PERCENT_MEM | 48 | Process.h |
| USER | 49 | Process.h |
| TIME | 50 | Process.h |
| NLWP | 51 | Process.h |
| IO_READ_RATE | 110 | linux/ProcessField.h — **Linux-only** |
| IO_WRITE_RATE | 111 | linux/ProcessField.h — **Linux-only** |

Important catch: `M_SHARE` (shared memory) is **not portable** — it's a Linux
`PLATFORM_PROCESS_FIELDS` entry, same as the IO rate fields. `darwin/ProcessField.h`
only defines `TRANSLATED = 100` for its platform slot; it has no shared-memory
field at all (Darwin/Mach doesn't expose this the way procfs does). So the
macOS variant drops M_SHARE along with the two IO_* fields and DiskIO/NetworkIO
meters — it is not "identical minus the two IO columns", it's minus three
columns (M_SHARE, IO_READ_RATE, IO_WRITE_RATE) and the two IO meters.

`fields=` used here:

- Linux: `1 49 18 19 39 40 41 51 3 47 48 110 111 50 2`
  → PID USER PRIORITY NICE M_VIRT M_RESIDENT M_SHARE NLWP STATE PERCENT_CPU PERCENT_MEM IO_READ_RATE IO_WRITE_RATE TIME Command
- macOS: `1 49 18 19 39 40 51 3 47 48 50 2`
  → PID USER PRIORITY NICE M_VIRT M_RESIDENT NLWP STATE PERCENT_CPU PERCENT_MEM TIME Command

`sort_key=47` (PERCENT_CPU), `sort_direction=-1` → sorted by CPU% descending.

## Meters

Meter class names (`Meter.h` / `*Meter.c` `.name` fields) and mode IDs
(`Meter.h` `MeterModeId`: `BAR=1`, `TEXT=2`, `GRAPH=3`, `LED=4`) were verified
the same way against the `3.0.5` source.

- Left: `CPU` (single averaged bar — the plain `CPU` meter class, distinct
  from the per-core `AllCPUs`/`LeftCPUs`/`RightCPUs` classes), `Memory`,
  `Swap`, and on Linux only, `DiskIO`, `NetworkIO`. All bar mode (`1`).
- Right: `Tasks`, `LoadAverage`, `Uptime` — all text mode (`2`), same as
  htop's own defaults for these.

## Not verified on this box

This is a Linux VM — there is no macOS or htop-on-Darwin available here, so
`htoprc.macos` was never actually launched through htop. The field/meter IDs
are as verified above from the darwin/portable headers, but the *deployed,
htop-normalised* macOS file has not been confirmed the way the Linux one was
(see validation step in the install notes / PR). Verify on the laptop after
`setup.sh` runs there — a dropped meter or column would show up immediately
as a shorter row / missing panel.
