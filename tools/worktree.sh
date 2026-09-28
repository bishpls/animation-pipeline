#!/usr/bin/env bash
# A worktree that checks out only what its work needs (charkit/sparse.py): a full checkout is ~1.8 GB of every film's rig
# art and audio, duplicated per worktree; a charkit worktree needs ~0.3 GB. Use this instead of plain `git worktree add`.
#     tools/worktree.sh NAME [--branch B] [--from REF] [--profile core|charkit|full] [--spec SPEC] [PATH ...]
#         -> ../animation-pipeline-NAME on branch B (default NAME, created from REF, default HEAD), with the profile's
#            directories (default core) plus each PATH (e.g. projects/tsuzuku for a film's session)
#     tools/worktree.sh --add PATH [PATH ...]        # in a worktree: check out more (git sparse-checkout add)
#     tools/worktree.sh --slim [--profile P] [PATH ...]  # in an existing worktree: narrow it to a profile (untracked,
#                                                        # ignored and locally modified files stay where they are)
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
cone() { python3 "$ROOT/charkit/sparse.py" "$@"; }

if [ "${1:-}" = "--add" ]; then
  shift; git sparse-checkout add "$@"; exit 0
fi

profile=core; spec=charkit/spec/clawd.json; branch=; from=HEAD; extra=()
if [ "${1:-}" = "--slim" ]; then
  shift
  while [ $# -gt 0 ]; do case "$1" in
    --profile) profile=$2; shift 2;; --spec) spec=$2; shift 2;; *) extra+=("$1"); shift;; esac; done
  dirs=$(cone "$profile" --spec "$spec" "${extra[@]+"${extra[@]}"}")
  [ "$dirs" = FULL ] && { git sparse-checkout disable; exit 0; }
  before=$(du -sk . | cut -f1)
  # shellcheck disable=SC2086
  git sparse-checkout set --cone $dirs
  echo "slimmed: $(( (before - $(du -sk . | cut -f1)) / 1024 )) MB freed"; exit 0
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
echo "$dest ($branch, profile $profile): $(du -sh "$dest" | cut -f1)"
