#!/usr/bin/env bash
# Compare bake cost on this branch against main for a fixed set of cases.
#
#   bash tools/bench_matrix.sh [work_dir]        # default /private/tmp/blastfx-bench
#
# Needs desktop Blender (Mantaflow). Each case bakes only the first N frames so the
# whole run stays short. It adds a temporary git worktree of main under work_dir and
# copies tools/bake_benchmark.py into it; nothing in your checkout is changed.
#
# NOTE: main and this branch differ in physics (the burst-speed fix changes the
# blast itself), so the frame counts match but the sims are not identical. Read the
# numbers as "what does a bake cost now", not as a pure speed-up measurement.
set -euo pipefail

BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
WORK="${1:-/private/tmp/blastfx-bench}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
MAIN_TREE="$WORK/main_tree"

# preset  quality  frames
CASES=(
  "small PREVIEW 60"
  "small DRAFT 60"
  "medium PREVIEW 60"
  "medium DRAFT 60"
  "nuclear_groundburst PREVIEW 60"
  "nuclear_groundburst DRAFT 60"
)

mkdir -p "$WORK"
if [ ! -d "$MAIN_TREE" ]; then
  git -C "$REPO" worktree add --detach "$MAIN_TREE" main >/dev/null
fi
cp "$REPO/tools/bake_benchmark.py" "$MAIN_TREE/tools/bake_benchmark.py"

run_case() {  # label tree preset quality frames
  local label="$1" tree="$2" preset="$3" quality="$4" frames="$5"
  local out="$WORK/$label"
  rm -rf "$out"; mkdir -p "$out"
  echo ">>> $label  $preset $quality ($frames frames)"
  ( cd "$tree" && "$BLENDER" --background --factory-startup \
      --python tools/bake_benchmark.py -- "$preset" "$quality" "$out" "$frames" ) \
      > "$out/run.log" 2>&1 || echo "    FAILED, see $out/run.log"
  rm -rf "$out"/blastfx_cache "$out"/*.blend1 2>/dev/null || true  # keep disk use down
}

for case in "${CASES[@]}"; do
  read -r preset quality frames <<<"$case"
  run_case "branch" "$REPO" "$preset" "$quality" "$frames"
  mv "$WORK/branch/bench_${preset}_${quality}.json" "$WORK/branch_${preset}_${quality}.json" 2>/dev/null || true
  run_case "main" "$MAIN_TREE" "$preset" "$quality" "$frames"
  mv "$WORK/main/bench_${preset}_${quality}.json" "$WORK/main_${preset}_${quality}.json" 2>/dev/null || true
done

python3 - "$WORK" <<'EOF'
import json, sys, glob, os
work = sys.argv[1]
rows = []
for path in sorted(glob.glob(os.path.join(work, "branch_*.json"))):
    tag = os.path.basename(path)[len("branch_"):-len(".json")]
    b = json.load(open(path))
    mpath = os.path.join(work, f"main_{tag}.json")
    m = json.load(open(mpath)) if os.path.exists(mpath) else None
    rows.append((tag, m, b))
print(f"\n{'case':32} {'main s':>8} {'branch s':>9} {'main MB':>8} {'br MB':>7} {'main cache':>11} {'br cache':>9}")
for tag, m, b in rows:
    f = lambda d, k, div=1: ("-" if d is None else f"{d[k]/div:.1f}")
    print(f"{tag:32} {f(m,'bake_seconds'):>8} {f(b,'bake_seconds'):>9} "
          f"{f(m,'peak_rss_mb'):>8} {f(b,'peak_rss_mb'):>7} "
          f"{f(m,'cache_bytes',1e6)+' MB':>11} {f(b,'cache_bytes',1e6)+' MB':>9}")
print("\nFull JSON per case in", work)
EOF
