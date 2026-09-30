#!/usr/bin/env bash
# A worktree that checks out only what its work needs (charkit/sparse.py): a full checkout is ~1.8 GB of every film's rig
# art and audio, duplicated per worktree; a charkit worktree needs ~0.3 GB. Use this instead of plain `git worktree add`.
#     tools/worktree.sh NAME [--branch B] [--from REF] [--profile core|charkit|full] [--spec SPEC] [PATH ...]
#         -> ../animation-pipeline-NAME on branch B (default NAME, created from REF, default HEAD), with the profile's
#            directories (default core) plus each PATH (e.g. projects/tsuzuku for a film's session)
#     tools/worktree.sh --add PATH [PATH ...]        # in a worktree: check out more (git sparse-checkout add)
#     tools/worktree.sh --slim [--profile P] [--force] [PATH ...]  # in an existing worktree: narrow it to a profile.
#         Git deletes directories outside the new cone that hold only ignored files (build outputs, caches), so --slim
#         lists every untracked or ignored path outside the cone and stops unless --force. Pass the cone's directories
#         to git as separate words: zsh does not split an unquoted $var, which once left `charkit` out of a cone.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
# the profiles (charkit/sparse.py), read from HEAD when this worktree doesn't check charkit/ out
cone() {
  if [ -f "$ROOT/charkit/sparse.py" ]; then python3 "$ROOT/charkit/sparse.py" "$@"
  else CHARKIT_ROOT="$ROOT" python3 <(git show HEAD:charkit/sparse.py) "$@"; fi
}

if [ "${1:-}" = "--add" ]; then
  shift; git sparse-checkout add "$@"; exit 0
fi

profile=core; spec=charkit/spec/clawd.json; branch=; from=HEAD; extra=()
if [ "${1:-}" = "--slim" ]; then
  shift
  force=0
  while [ $# -gt 0 ]; do case "$1" in
    --profile) profile=$2; shift 2;; --spec) spec=$2; shift 2;; --force) force=1; shift;; *) extra+=("$1"); shift;; esac; done
  dirs=$(cone "$profile" --spec "$spec" "${extra[@]+"${extra[@]}"}")
  [ "$dirs" = FULL ] && { git sparse-checkout disable; exit 0; }
  # git removes directories outside the new cone that hold only ignored files (build outputs, caches): list any
  # untracked or ignored path outside the cone first, and stop unless --force
  outside=$(git status --porcelain --ignored | grep -E '^(!!|\?\?) ' | cut -c4- | while read -r p; do
    p=${p%/}
    keep=0; case "$p" in */*) ;; *) keep=1;; esac          # top-level files stay in cone mode
    for d in $dirs; do case "$p" in "$d"|"$d"/*) keep=1; break;; esac; done
    if [ $keep = 0 ]; then echo "$p"; fi; done)
  if [ -n "$outside" ] && [ "$force" != 1 ]; then
    echo "slim would delete these untracked / ignored paths outside the cone (move them, or rerun with --force):" >&2
    echo "$outside" | sed 's/^/  /' >&2; exit 1
  fi
  before=$(du -sk . | cut -f1)
  # shellcheck disable=SC2086
  git sparse-checkout set --cone $dirs
  echo "slimmed: $(( before / 1024 )) MB -> $(( $(du -sk . | cut -f1) / 1024 )) MB"; exit 0
fi

name=${1:?usage: tools/worktree.sh NAME [--branch B] [--from REF] [--profile core|charkit|full] [PATH ...]}; shift
while [ $# -gt 0 ]; do case "$1" in
  --branch) branch=$2; shift 2;; --from) from=$2; shift 2;; --profile) profile=$2; shift 2;;
  --spec) spec=$2; shift 2;; *) extra+=("$1"); shift;; esac; done
branch=${branch:-$name}
dest="$(dirname "$ROOT")/animation-pipeline-$name"
[ -e "$dest" ] && { echo "exists: $dest" >&2; exit 1; }
if git show-ref --verify --quiet "refs/heads/$branch"; then
  git worktree add --no-checkout "$dest" "$branch"
else
  git worktree add --no-checkout -b "$branch" "$dest" "$from"
fi
dirs=$(cone "$profile" --spec "$spec" "${extra[@]+"${extra[@]}"}")
if [ "$dirs" != FULL ]; then
  # shellcheck disable=SC2086
  git -C "$dest" sparse-checkout set --cone $dirs
fi
git -C "$dest" checkout -q "$branch"
# (no generated inputs to copy: charkit/out/i3d, TRELLIS's output, was the only one, and no build reads it since the
# sheet-only outfit masks, decision 8)
# the boxes' configs (gitignored, so a checkout lacks them): copied from this worktree, or the main one
for f in "$ROOT"/infra/gcp/*.env; do
  [ -e "$f" ] && [ -d "$dest/infra/gcp" ] && cp -n "$f" "$dest/infra/gcp/"
done
echo "$dest ($branch, profile $profile): $(du -sh "$dest" | cut -f1)"
