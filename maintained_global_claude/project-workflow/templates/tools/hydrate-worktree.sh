#!/usr/bin/env zsh
# Give a fresh git worktree the untracked data its test suite needs.
#
# LOCAL/macOS ONLY -- never invoke this from a CI recipe. It is zsh (runners
# have no zsh: exit 127) and it provisions from a primary checkout that exists
# only on a developer machine. CI checks out one tree and has nothing to
# hydrate from.
#
# WHY THIS EXISTS: gitignored artifacts (built indexes, caches, large corpora,
# fixtures too big to commit) are absent from a new worktree. Tests that guard
# on them then SKIP instead of running, and a skip and a pass are the same
# observable state. Without this, a worktree's `just ci-fast` runs a strict
# subset of the suite and still reports green -- and two agents comparing test
# counts each get a different number and are each "right".
#
# WHAT IT REFUSES TO DO: report success while doing nothing. Every failure to
# provision a listed artifact is fatal and names the artifact. A worktree that
# cannot be fully provisioned must refuse to exist rather than exist
# half-built: a half-hydrated worktree produces different test results than a
# complete one, which is the exact defect this script exists to prevent, one
# level down. This is the whole reason the script is in the kit -- the pattern
# was rediscovered independently, and fixed one filename at a time, in more
# than one repo.
#
# CONFIGURATION: .agent-workflow/hydrate.manifest, project-owned. One entry per
# line, `<mode> <path>`, path relative to the repo root:
#
#     # comments and blank lines are ignored
#     link  data/corpus/           # symlink: big, read-mostly, shared
#     link  data/index.bin
#     copy  cache/                 # per-worktree copy: the suite WRITES here
#
#   link -- one symlink back to the primary checkout. Use for anything large
#           and read-only. Cheap and instant at any size.
#   copy -- copy-on-write clone where the filesystem supports it (APFS `cp -c`),
#           plain copy otherwise. Use for anything the suite writes to, so one
#           worktree's run cannot overwrite another's outputs. The fallback
#           produces an identical tree and differs only in disk used.
#
#   clone -- ONE copy-on-write clone of a whole directory (APFS clonefile via
#           `cp -cRp`), for a build directory such as a warm cargo `target/debug`
#           (~10^6 files, 100+ GB) so a fresh worktree reuses every third-party
#           dependency instead of recompiling it. Absent in the worktree: cloned
#           from the primary in a single call (never per file). Present: left
#           alone, and said so (a build dir is incomplete the moment cargo writes
#           one unit, so it is judged as a whole, unlike `copy`). There is NO
#           byte-copy fallback: `cp -c` silently degrades to a real copy on a
#           non-APFS volume, so support is checked up front (primary and
#           worktree on the same APFS volume) and the script FAILS LOUD naming
#           the directory when it does not hold. While cloning, the source's
#           `<dir>/.cargo-lock` -- the lock cargo itself holds for the whole of
#           a build in that profile dir -- is held with flock(1), so a build
#           running in the primary cannot be cloned half-written. Needs `flock`
#           (brew install flock) and a `<dir>/.cargo-lock`; both fail loud.
#           Workspace crates still rebuild in the worktree (cargo's fingerprint
#           includes the path); third-party dependencies are reused.
#
#     clone target/debug
#
#   `copy`/`link` directory entries are compared PER ARTIFACT, never as a whole. Guarding a
#   whole directory behind "does it exist" silently no-ops on a directory that
#   exists but is INCOMPLETE -- and incomplete is the normal case, because a
#   worktree acquires the directory the moment the suite writes one file into
#   it. Existing files are always left alone; only absent ones are provisioned.
#
# ENVIRONMENT: HYDRATE_PRIMARY overrides the primary checkout;
# HYDRATE_MANIFEST overrides the manifest path (to try a manifest before it is
# merged into the primary).
#
# USAGE:
#   hydrate-worktree.sh <worktree-path>   provision one worktree
#   hydrate-worktree.sh --all             sweep every registered worktree
#
# Re-run `--all` after creating any worktree, and whenever a gate reports a
# test count you cannot reconcile against the baseline. It is cheap and skips
# anything already present, so sweeping costs nothing.
set -euo pipefail

PRIMARY=${HYDRATE_PRIMARY:-$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null | sed 's:/\.git$::')}
[[ -n $PRIMARY && -d $PRIMARY ]] || {
  print -u2 "hydrate: cannot locate the primary checkout (run inside the repo, or set HYDRATE_PRIMARY)"
  exit 2
}
MANIFEST=${HYDRATE_MANIFEST:-$PRIMARY/.agent-workflow/hydrate.manifest}

# A project with no manifest has no untracked artifacts to provision. That is a
# legitimate absence, not a failure -- but say so out loud, so "nothing to do"
# can never be mistaken for "provisioned successfully".
[[ -f $MANIFEST ]] || {
  print "hydrate: no .agent-workflow/hydrate.manifest -- this project provisions nothing. Doing nothing."
  exit 0
}

if [[ ${1:-} == --all ]]; then
  self=${0:A}
  git -C $PRIMARY worktree list --porcelain | awk '/^worktree /{print $2}' | while read -r wt; do
    [[ $wt == $PRIMARY ]] && continue
    $self $wt
  done
  exit 0
fi

WT=${1:?usage: hydrate-worktree.sh <worktree-path> | --all}
[[ -d $WT ]] || { print -u2 "hydrate: no such worktree: $WT"; exit 2 }
[[ ${WT:A} == ${PRIMARY:A} ]] && { print -u2 "hydrate: refusing to hydrate the primary checkout"; exit 2 }

typeset -i linked=0 cloned=0 present=0 missing=0 dirs_cloned=0

# NOTE: `(( n++ ))` evaluates to the OLD value, so it returns nonzero status on
# the first increment and `set -e` would kill the run. Use plain assignment.

fail_missing() {  # never `|| true` a provisioning failure -- see the header
  print -u2 "  ✗ MISSING IN PRIMARY: $1"
  missing=$(( missing + 1 ))
}

do_link() {
  # Strip a trailing slash exactly as do_copy does. `link data/corpus/` is the
  # header's own example, and without this `${rel:h}` and the `ln` target both
  # carry the empty trailing component: ln dies with ".../corpus//corpus".
  local rel=${1%/}
  [[ -e $PRIMARY/$rel ]] || { fail_missing $rel; return 0 }
  if [[ -e $WT/$rel || -L $WT/$rel ]]; then
    print "  = $rel (present)"; present=$(( present + 1 )); return 0
  fi
  mkdir -p ${WT}/${rel:h}
  ln -s $PRIMARY/$rel $WT/$rel
  print "  → $rel (symlink)"
  linked=$(( linked + 1 ))
}

do_copy() {
  local rel=${1%/}
  [[ -e $PRIMARY/$rel ]] || { fail_missing $rel; return 0 }
  if [[ -f $PRIMARY/$rel ]]; then
    copy_one $rel; return 0
  fi
  mkdir -p $WT/$rel
  # The `D` glob qualifier is deliberate: zsh skips dot-entries by default, and
  # omitting it silently misses whole classes of file while reporting a clean
  # sweep. `.` restricts to regular files -- a symlink here would point back at
  # the primary and defeat the per-worktree isolation `copy` exists for.
  local src rel2
  for src in ${PRIMARY}/${rel}/**/*(D.N); do
    rel2=${src#${PRIMARY}/}
    copy_one $rel2
  done
}

copy_one() {
  local rel=$1
  if [[ -e $WT/$rel || -L $WT/$rel ]]; then
    print "  = $rel (present)"; present=$(( present + 1 )); return 0
  fi
  mkdir -p ${WT}/${rel:h}
  # `cp -c` is an APFS copy-on-write clone: instant, zero bytes. The fallback
  # is a plain copy -- the SAME resulting file, only slower and using disk.
  # This is a performance fallback, not a correctness one.
  cp -c $PRIMARY/$rel $WT/$rel 2>/dev/null || cp $PRIMARY/$rel $WT/$rel
  print "  → $rel (copy)"
  cloned=$(( cloned + 1 ))
}

# Filesystem type of the volume holding $1 (from `mount`, via the device df reports).
fstype_of() {
  local dev
  dev=$(df -P $1 | awk 'NR==2{print $1}')
  /sbin/mount | awk -v d="$dev" '$1==d{ if (match($0, /\([a-z0-9_]+[,)]/)) print substr($0, RSTART+1, RLENGTH-2) }'
}

die_clone() {  # clone failures are fatal and never degrade to a byte copy
  print -u2 "hydrate: clone $1: $2"
  print -u2 "hydrate: refusing to byte-copy a build directory (100+ GB); fix the cause or delete the manifest line."
  exit 2
}

do_clone() {
  local rel=${1%/}
  [[ -d $PRIMARY/$rel ]] || { fail_missing $rel; return 0 }
  if [[ -e $WT/$rel || -L $WT/$rel ]]; then
    print "  = $rel (present, left alone)"; present=$(( present + 1 )); return 0
  fi
  mkdir -p ${WT}/${rel:h}
  # `cp -c` falls back to a real copy on non-APFS volumes and across volumes:
  # prove clonefile can work BEFORE starting.
  local sfs wfs
  sfs=$(fstype_of $PRIMARY/$rel); wfs=$(fstype_of ${WT}/${rel:h})
  [[ $sfs == apfs && $wfs == apfs ]] || die_clone $rel "clonefile needs APFS on both sides (primary: ${sfs:-unknown}, worktree: ${wfs:-unknown})"
  [[ $(stat -f %d $PRIMARY/$rel) == $(stat -f %d ${WT}/${rel:h}) ]] || die_clone $rel "primary and worktree are on different volumes; clonefile cannot cross volumes"
  command -v flock >/dev/null || die_clone $rel "flock is not installed (needed to hold cargo's lock on $rel/.cargo-lock while cloning); install it: brew install flock"
  [[ -f $PRIMARY/$rel/.cargo-lock ]] || die_clone $rel "$PRIMARY/$rel/.cargo-lock does not exist; this is not a cargo profile directory, so there is no lock to hold"
  print "  … $rel (cloning; waits for any build running in the primary)"
  # -w: a build held for 30 min is a fault to report, not to wait out silently.
  flock -w 1800 $PRIMARY/$rel/.cargo-lock cp -cRp $PRIMARY/$rel $WT/$rel || {
    rm -rf $WT/$rel  # never leave a partial clone that a rerun would call "present"
    die_clone $rel "cp -cRp (under flock) failed"
  }
  print "  → $rel (clone)"
  dirs_cloned=$(( dirs_cloned + 1 ))
}

print "▸ hydrating ${WT:t}"
# NOTE: the loop variable is `artifact`, never `path`. In zsh `path` is the
# special array tied to $PATH; reading a manifest line into it silently
# destroys PATH and the next `mkdir` dies with "command not found".
while read -r mode artifact _rest; do
  [[ -z $mode || $mode == \#* ]] && continue
  case $mode in
    link) do_link $artifact ;;
    copy) do_copy $artifact ;;
    clone) do_clone $artifact ;;
    *) print -u2 "hydrate: unknown mode '$mode' in $MANIFEST (want: link | copy | clone)"; exit 2 ;;
  esac
done < $MANIFEST

print "▸ ${WT:t}: $linked linked, $cloned copied, $dirs_cloned cloned, $present already present"

# THE POINT OF THE WHOLE SCRIPT. A provisioning script that swallows a missing
# artifact and exits 0 hands back a worktree whose suite skips tests, and the
# agent discovers it several steps later as an unrelated-looking failure that
# names neither this script nor the real cause.
(( missing == 0 )) || {
  print -u2 "▸ REFUSING: $missing artifact(s) listed in the manifest are absent from the primary checkout."
  print -u2 "▸ This worktree is HALF-BUILT and its test counts will not match the baseline."
  print -u2 "▸ Restore them under $PRIMARY, or delete their lines from $MANIFEST."
  exit 1
}
print "▸ done"
