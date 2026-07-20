# Migrate `/Volumes/external` from Journaled HFS+ to APFS

> **⚠️ THIS FILE LIVES ON THE VOLUME BEING MIGRATED.**
> Copy it to the internal disk before you start — the volume will be
> unmounted during conversion and you will not be able to read this:
> ```sh
> cp /Volumes/external/dev/fsa/migrate.md ~/migrate.md
> ```

**Status:** ✅ **completed 2026-07-20.** Written 2026-07-18.
Verified post-conversion: `File System Personality: APFS`, `Solid State: Yes`.
Sparse files 10G apparent → 16K actual; 500 MB CoW clone in 0.003 s vs 18.9 s
to write it. Sections 5–7 retained for rollback and follow-up work.

> **⚠️ NEVER hardcode a BSD disk identifier in this file.**
> USB disk numbers are assigned at attach time and shift on every replug and
> reboot. This document originally hardcoded `/dev/disk4s2`; by the time it was
> run the drive had moved to `disk6s2`, and `disk4` had become the *synthesized
> APFS container for this very drive*. A stale `eraseDisk /dev/disk4` does not
> error — it erases whatever is at that node now. **Always re-derive:**
>
> ```sh
> diskutil list external physical    # find the drive, note its identifier
> ```

---

## 1. Why convert

Measured facts about this specific volume (all verified, not assumed):

| Property | Value |
|---|---|
| Device node | **not stable — look it up** (`diskutil list external physical`) |
| Filesystem | Journaled HFS+ → **APFS** as of 2026-07-20 |
| **Solid State** | **Yes** |
| Protocol | USB |
| Size / used / free | 2.0 TB / 118 GB / 1.7 TB |

**The SSD finding is what settles it.** APFS is optimized for flash and
fragments badly on rotational media with no defragmentation story — on a
spinning disk, HFS+ would have been a defensible choice. This is flash, so
that objection does not apply, and HFS+ retains essentially no advantage.

Three concrete wins, in order of how much they matter here:

### 1.1 Sparse files — this one is costing you today

HFS+ has **no sparse file support at all**. APFS does.

This is not abstract. `parot-core`'s container build path
(`crates/core/src/container/build.rs`, commit `223309a` "retire serial path
— unify on 1×index parallel stitch") deliberately pre-sizes a **sparse**
`<out>.tmp` via `set_len` and pwrite-stitches each shard into it. The entire
point was to cut peak build disk from ~2×index to ~1×index.

On HFS+ that file is not sparse — it fully allocates on `set_len`. **The
optimization the code was written for does not work on this volume.** You
are paying the ~2× peak disk the commit was meant to eliminate.

### 1.2 Copy-on-write clones

APFS `cp -c` duplicates a directory instantly, at zero additional space,
via copy-on-write. HFS+ cannot do this.

Direct payoff: a warm 25 GB `target/` can be cloned per parallel agent in
roughly zero time and zero bytes, instead of each agent paying a full cold
build. Cargo takes an *exclusive lock* on `target/` during compilation, so
N agents sharing one target dir do not run in parallel — they queue. CoW
clones are the clean fix. (See §7.)

### 1.3 Metadata concurrency

HFS+ serializes metadata operations on a single global catalog B-tree lock.
APFS uses finer-grained locking. A cargo `target/` is hundreds of thousands
of small files and parallel builds hammer exactly that path.

Also gained: snapshots, better crash consistency, space sharing between
volumes in a container.

---

## 2. Pre-flight — do these first, in order

### 2.1 Push all unpushed work ⚠️ HIGHEST RISK ITEM

`parot-core` is currently **21 commits ahead of `origin/main`, unpushed.**
Uncommitted and unpushed work is the only genuinely irreplaceable data on
this volume. Everything else is either regenerable or on a remote.

```sh
cd /Volumes/external/dev/fsa/parot-core
git status --short          # must be clean, or commit/stash first
git push origin main
```

Sweep every other repo on the volume for the same:

```sh
for d in /Volumes/external/dev/*/*/.git; do
  r="${d%/.git}"
  printf '\n== %s\n' "$r"
  git -C "$r" status --short
  git -C "$r" log --oneline @{u}..HEAD 2>/dev/null | head -5
done
```

Anything printed is at risk. Resolve it before continuing.

### 2.2 Shrink the backup by deleting regenerable data

Measured on this volume:

| Category | Size | Regenerable? |
|---|---|---|
| Cargo `target/` dirs | **31 GB** | yes, fully |
| `node_modules` / `.venv` | **5.3 GB** | yes, fully |
| `/Volumes/external/sccache` | 254 MB | yes, it's a cache |
| Everything else | ~82 GB | **back this up** |

Dropping ~36 GB of build artifacts brings the real backup from 118 GB to
roughly **82 GB**, which *does* fit in the internal disk's 115 GB free —
though with only ~33 GB headroom, which is tight. A second external drive is
more comfortable if you have one.

```sh
# Optional but recommended — all of this rebuilds on demand.
fd -t d -d 4 '^target$'       /Volumes/external/dev -x rm -rf
fd -t d -d 5 '^node_modules$' /Volumes/external/dev -x rm -rf
fd -t d -d 5 '^\.venv$'       /Volumes/external/dev -x rm -rf
rm -rf /Volumes/external/sccache
```

### 2.3 Quiesce everything touching the volume

```sh
# Stop parot daemons (they hold corpora by mmap and keep the volume busy)
parot prune --stop-running     # after this branch lands; else `parot down <corpus>`

# Confirm nothing is running from the volume
pgrep -fl '__serve'

# Find any remaining open files on the volume
lsof +D /Volumes/external 2>/dev/null | head -20
```

Close editors, terminals `cd`'d into the volume, Docker, Spotlight indexing,
Time Machine, and any Claude Code sessions with a cwd on it. **Including the
session you are reading this from.**

### 2.4 Take the backup

```sh
# Adjust the destination; ~/ext-backup only works if you did §2.2 first
rsync -aHAX --info=progress2 /Volumes/external/ ~/ext-backup/
```

`-H` preserves hard links, `-A` ACLs, `-X` extended attributes. Do not skip
these — macOS metadata lives in xattrs.

Verify the backup is real before trusting it:

```sh
du -sh ~/ext-backup
diff -rq /Volumes/external ~/ext-backup 2>&1 | head -20   # expect no output
```

---

## 3. Convert

`diskutil apfs convert` exists on your macOS 26.5.1 and is documented as
**"Nondestructively convert from HFS to APFS"** — it is the same mechanism
Apple used for the High Sierra migration, not a third-party tool.

```sh
# 1. Re-derive the identifier — NEVER reuse one written down earlier.
diskutil list external physical
#    Find the `Apple_HFS external` row; note its IDENTIFIER (e.g. disk6s2).

# 2. Convert that partition.
VOL=disk6s2                       # ← replace from step 1 every single time
diskutil unmount /Volumes/external
sudo diskutil apfs convert "/dev/$VOL"
```

**During conversion:**
- Do **not** unplug the drive. It is USB — a disconnect mid-convert is the
  main realistic way to lose the volume.
- Keep the machine on AC power and disable sleep:
  `caffeinate -dimsu` in a spare terminal.
- Expect minutes, not hours, at 118 GB — but do not interrupt it regardless.

If `convert` refuses (it can, on volumes with certain legacy attributes),
fall back to §5.

---

## 4. Verify

```sh
diskutil info /Volumes/external | rg -i 'file system|personality|solid state'
# expect: APFS
```

Prove the two features you converted for actually work:

```sh
# Sparse files — should report far less disk used than apparent size
cd /Volumes/external && mkfile -n 10g sparse.test
ls -lh sparse.test          # apparent: 10G
du -h  sparse.test          # actual: should be ~0, NOT 10G
rm sparse.test

# Copy-on-write clones — should be instant and ~free
mkdir -p /Volumes/external/cow-test && dd if=/dev/urandom of=/Volumes/external/cow-test/f bs=1m count=500
time cp -c -R /Volumes/external/cow-test /Volumes/external/cow-test-clone   # expect ~0s
rm -rf /Volumes/external/cow-test /Volumes/external/cow-test-clone
```

If `du` on the sparse file reports 10G, the conversion did not take and you
should stop and investigate before restoring anything.

Then restore and rebuild:

```sh
# Only if you deleted them in §2.2 — they regenerate
cd /Volumes/external/dev/fsa/parot-core && cargo build
```

---

## 5. Fallback: erase and restore

Safer in the sense that it produces a pristine filesystem, slower in that it
requires a full restore. Use if `convert` refuses or fails.

```sh
# DESTRUCTIVE — the backup from §2.4 must be verified first.
# Re-derive the WHOLE-DISK identifier; do not reuse any number from this file.
diskutil list external physical
DISK=disk6                        # ← the whole disk, NOT the partition, NOT a
                                  #   synthesized container. Replace every time.
diskutil info "/dev/$DISK" | rg -i 'device location|media name|disk size'
#    ^ confirm this is the external 2 TB drive BEFORE the next line.

diskutil eraseDisk APFS external "/dev/$DISK"
rsync -aHAX --info=progress2 ~/ext-backup/ /Volumes/external/
```

`eraseDisk` targets the **whole disk**, not the partition. Post-conversion there
is also a *synthesized* container disk backed by this drive — erasing that is not
the same operation. Only the `(external, physical)` entry is the right target.

---

## 6. Rollback

There is no in-place "convert back". If APFS somehow behaves worse for your
workload, the path back is `diskutil eraseDisk JHFS+ external "/dev/$DISK"` —
deriving `$DISK` exactly as in §5, never from memory — followed by an rsync
restore. Keep the §2.4 backup until you have run normally on APFS for at least
a week (i.e. until **2026-07-27**).

---

## 7. After migrating — capture the wins

### 7.1 Parallel agents without cargo lock contention

The problem: cargo takes an **exclusive lock on `target/` during
compilation**. N agents sharing one target dir serialize; you get the
coordination cost of N agents with the throughput of one.

With APFS, clone a warm target dir per agent for free:

```sh
cp -c -R /Volumes/external/dev/fsa/parot-core/target \
         /Volumes/external/.targets/agent-1
CARGO_TARGET_DIR=/Volumes/external/.targets/agent-1 cargo nextest run …
```

### 7.2 sccache settings (already applied 2026-07-18)

Set in `~/dotfiles/shell/.aliases-and-envs.zsh`:

```sh
export SCCACHE_DIR=/Volumes/external/sccache
export SCCACHE_CACHE_SIZE=100G
export CARGO_INCREMENTAL=0
```

`CARGO_INCREMENTAL=0` is **required**, not cosmetic: sccache cannot cache
incremental compilations and silently skips them. Measured before the change
— 3495 of ~4456 calls rejected with reason `incremental`, Rust cache hit rate
**1.39%** against a cache that was 100% full at its old 1 GiB cap.

Tradeoff worth revisiting: incremental compilation is better for a single
tree with tight edit-compile loops; sccache is better across many trees,
worktrees, and parallel agents. If your day-to-day shifts back to solo
iteration in one tree, scope `CARGO_INCREMENTAL=0` to agent/CI runs instead
of exporting it globally.

### 7.3 Re-measure the sparse-file win

After conversion, a `--doc-index full` build should show materially lower
peak disk than before, since `build.rs`'s sparse pre-size will finally do
what it was written to do. Worth confirming with `df` sampled during a large
build — it validates that the migration paid for itself.

---

## Risk summary

| Risk | Likelihood | Mitigation |
|---|---|---|
| Unpushed commits lost | **High if skipped** | §2.1 — push everything first |
| USB disconnect mid-convert | Low | Do not touch the cable; AC power; `caffeinate` |
| `convert` refuses | Low–moderate | §5 erase-and-restore fallback |
| Backup doesn't fit internally | Moderate | §2.2 drops ~36 GB of regenerable data |
| Conversion silently no-ops | Low | §4 sparse-file test catches it |

**Do not start this while work is in flight on the volume.** At time of
writing there is uncommitted `parot-core` work and running agents on it.
