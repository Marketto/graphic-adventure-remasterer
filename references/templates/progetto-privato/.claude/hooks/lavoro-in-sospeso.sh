#!/bin/bash
# Stop hook: before the agent ends its turn, flag uncommitted or unpushed work.
# Blocks at most once per turn (stop_hook_active), never loops.
input=$(cat)
case "$input" in *'"stop_hook_active":true'*|*'"stop_hook_active": true'*) exit 0;; esac
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
changes=$(git status --porcelain 2>/dev/null)
unpushed=""
if git symbolic-ref -q HEAD >/dev/null; then            # detached HEAD: ignore
  if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    unpushed=$(git log --oneline '@{u}..HEAD' 2>/dev/null)
  else
    # no upstream: only commits that are on no remote branch count
    # (a new branch created from origin/main without own commits is not pending work)
    unpushed=$(git log --oneline HEAD --not --remotes 2>/dev/null)
  fi
fi
[ -z "$changes$unpushed" ] && exit 0
reason="Lavoro in sospeso."
[ -n "$changes" ] && reason="$reason Modifiche non committate: $(echo "$changes" | head -10 | tr '\n' ' ')"
[ -n "$unpushed" ] && reason="$reason Commit non inviati: $(echo "$unpushed" | head -5 | tr '\n' ' ')"
reason="$reason Chiudi con la skill chiusura-lavoro; se il lavoro non è finito, dillo all'utente invece di committare."
python3 -c 'import json,sys; print(json.dumps({"decision":"block","reason":sys.argv[1]}))' "$reason"
