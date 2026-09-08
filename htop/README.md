# Managed htop config

Two variants, deployed by `install_dotfiles` (see `install/install_functions.sh`)
based on `uname -s`:

- `htoprc.linux` → Linux (`uname -s` != `Darwin`)
- `htoprc.macos` → macOS (`uname -s` == `Darwin`)

Both symlink to `~/.config/htop/htoprc` via `ensure_symlink` (force-replaced on
every `setup.sh` run, so the repo stays the source of truth and the target is
always re-pointed at the correct variant for the current OS).

`htoprc.linux` was seeded from this Linux box's prior unmanaged
`~/.config/htop/htoprc` (preserved in git history) and then edited to the
wanted settings.

## Field IDs (`fields=`, `sort_key=`, `tree_sort_key=`)

**Important gotcha, found the hard way during validation:** htop's `fields=`
line does NOT store the raw `ProcessField` enum values. `Settings.c`
(`readFields`/`writeFields`, and the same for `sort_key`/`tree_sort_key`)
adds 1 when reading and subtracts 1 when writing:

```c
// This "+1" is for compatibility with the older enum format.
int id = atoi(ids[i]) + 1;
if (id > 0 && id < LAST_PROCESSFIELD && Process_fields[id].name) { ... }
...
// This "-1" is for compatibility with the older enum format.
fprintf(fd, "%s%d", sep, (int) fields[i] - 1);
```

So the number that belongs in the file is **`ProcessField enum value - 1`**.
Get this wrong and htop doesn't error — it just silently drops the field
(`Process_fields[id].name` is null for the shifted, nonexistent ID) on the
next interactive save, which is exactly the kind of silent breakage this
config is meant to avoid. Concretely, writing the raw enum value for `NICE`
(`19`) makes htop read it as id `20` (a gap between `NICE` and `STARTTIME`),
which has no name and gets dropped — confirmed by round-tripping a live
htop process through this box's real deployed config (see Validation below).

There is no local htop source checkout on this box (`~/bin/htop_src` doesn't
exist — `install/install_htop.sh`, which builds it there on Linux via
`install_if_missing htop install_htop` in `setup.sh`, was never run here
since this box's apt-installed `/usr/bin/htop` already satisfies that gate),
so the enum values themselves
were verified against the upstream `htop-dev/htop` GitHub source at tag
`3.0.5` (matching `htop --version` on this box, package `htop 3.0.5-7build2`
from Ubuntu jammy):

- Portable fields: `Process.h`
- Linux-only fields (`PLATFORM_PROCESS_FIELDS`): `linux/ProcessField.h`
- Darwin-only fields (`PLATFORM_PROCESS_FIELDS`): `darwin/ProcessField.h`

| Name | Enum value | Stored (enum-1) | Source |
|---|---|---|---|
| PID | 1 | 0 | Process.h |
| COMM (Command) | 2 | 1 | Process.h |
| STATE | 3 | 2 | Process.h |
| PRIORITY | 18 | 17 | Process.h |
| NICE | 19 | 18 | Process.h |
| M_VIRT | 39 | 38 | Process.h |
| M_RESIDENT | 40 | 39 | Process.h |
| M_SHARE | 41 | 40 | linux/ProcessField.h — **Linux-only** |
| PERCENT_CPU | 47 | 46 | Process.h |
| PERCENT_MEM | 48 | 47 | Process.h |
| USER | 49 | 48 | Process.h |
| TIME | 50 | 49 | Process.h |
| NLWP | 51 | 50 | Process.h |
| IO_READ_RATE | 110 | 109 | linux/ProcessField.h — **Linux-only** |
| IO_WRITE_RATE | 111 | 110 | linux/ProcessField.h — **Linux-only** |

Important catch #2: `M_SHARE` (shared memory) is **not portable** either —
it's a Linux `PLATFORM_PROCESS_FIELDS` entry, same as the IO rate fields.
`darwin/ProcessField.h` only defines `TRANSLATED = 100` for its platform
slot; it has no shared-memory field at all (Darwin/Mach doesn't expose this
the way procfs does). So the macOS variant drops M_SHARE along with the two
IO_* fields and the DiskIO/NetworkIO meters — it is not "identical minus the
two IO columns", it's minus three columns (M_SHARE, IO_READ_RATE,
IO_WRITE_RATE) and two meters.

`fields=` used here (already offset by -1, see above):

- Linux: `0 48 17 18 38 39 40 50 2 46 47 109 110 49 1`
  → PID USER PRIORITY NICE M_VIRT M_RESIDENT M_SHARE NLWP STATE PERCENT_CPU PERCENT_MEM IO_READ_RATE IO_WRITE_RATE TIME Command
- macOS: `0 48 17 18 38 39 50 2 46 47 49 1`
  → PID USER PRIORITY NICE M_VIRT M_RESIDENT NLWP STATE PERCENT_CPU PERCENT_MEM TIME Command

`sort_key=46` → enum 47 = PERCENT_CPU, `sort_direction=-1` → sorted by CPU%
descending. (`tree_sort_key=0` → enum 1 = PID, htop's own default — sorting
by CPU wasn't requested for tree order specifically, only for the flat list.)

## Meters

Meter class names (`Meter.h` / `*Meter.c` `.name` fields, not offset — this
convention is specific to `fields=`/`sort_key=`) and mode IDs (`Meter.h`
`MeterModeId`: `BAR=1`, `TEXT=2`, `GRAPH=3`, `LED=4`) were verified the same
way against the `3.0.5` source, then confirmed on-screen (see Validation).

Per-core meters are deliberate: seeing every core separately is how you tell
whether a parallel job is actually saturating the box. The plain `CPU` class
(one averaged bar) was tried and rejected — it hides exactly that.

- Linux: `LeftCPUs4` heads the left column (the lower half of the cores, four
  bars per row) and `RightCPUs4` heads the right (the upper half, four per
  row), so the header shows 8 columns of per-core bars — 8 rows on the
  64-thread VM. Below them: `Memory`, `Swap`, `DiskIO`, `NetworkIO` on the
  left, `Tasks`, `LoadAverage`, `Uptime` on the right.
- macOS: `LeftCPUs`/`RightCPUs` (one bar per row, half the cores each side),
  then `Memory`, `Swap` on the left and `Tasks`, `LoadAverage`, `Uptime` on
  the right.
- Modes: every CPU/memory/IO meter is bar mode (`1`); `Tasks`, `LoadAverage`,
  `Uptime` are text mode (`2`), same as htop's own defaults for these.

## Validation performed

1. Deployed on this box via `install_dotfiles`; `readlink -f ~/.config/htop/htoprc`
   resolves into the repo (`.../dotfiles/htop/htoprc.linux`).
2. Launched the real deployed config through a live htop (pty-driven, not just
   `timeout`+SIGTERM — htop only calls `Settings_write()` if
   `settings->changed`, so a plain launch-and-kill never touches the file;
   toggling a setting twice, net no-op, forces a genuine save). First attempt
   used raw enum values and htop's own rewrite silently dropped `NICE`,
   `TPGID`, `STARTTIME`, and `PERCENT_NORM_CPU` from a broader test list —
   that's what surfaced the -1 offset bug above. After applying the offset,
   the deployed file's `fields=`/`sort_key=`/`tree_sort_key=`/meters lines
   round-tripped byte-for-byte identical through a forced settings-changed
   save — nothing dropped. A screen capture of the running session (stripped
   of ANSI codes) confirmed the on-screen header reads exactly:
   `PID USER PRI NI VIRT RES SHR NLWP S CPU% MEM% DISK READ DISK WRITE TIME+ Command`,
   with tree view active and every meter (`LeftCPUs4`/`Memory`/`Swap`/`DiskIO`/
   `NetworkIO` on the left, `RightCPUs4`/`Tasks`/`LoadAverage`/`Uptime` on the
   right) rendering correctly: per-core bars labelled `0[...]` through
   `63[...]`, plus `Mem[...]`, `Swp[...]`, `Dis[...]`, `Net[rx:.../tx:...]`.
3. htop's own rewrite trims the file's leading comment down to its standard
   two lines on every interactive save (cosmetic normalization, not a
   dropped setting) — expected per htop's `Settings_write`, harmless.
4. `bash -n` / `zsh -n` on `install/install_functions.sh` — both clean.

## Not verified on this box

This is a Linux VM — there is no macOS or htop-on-Darwin available here, so
`htoprc.macos` was never actually launched through htop; only the field IDs
were checked against the `darwin/ProcessField.h` / portable `Process.h`
source (all its fields are portable, so the same -1 offset applies, but this
has not been round-tripped through a real Darwin htop binary). Verify on the
laptop after `setup.sh` runs there — a dropped meter or column would show up
immediately as a shorter row / missing panel, the same way it did here before
the offset fix.
