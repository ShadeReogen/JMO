#!/usr/bin/env bash
# Pulls the latest remote default branch, preserving config.json.
# Stdout protocol (read by settings.py):
#   STATUS: <text>   — update the on-screen action label
#   DONE             — pull succeeded; caller should restart
#   FAILED: <text>   — pull failed; details appended to 'fail' and pushed

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$REPO_DIR/config.json"
FAIL_FILE="$REPO_DIR/fail"
BACKUP="/tmp/jmo_config_backup.json"
ERR_TMP="/tmp/jmo_update_err"
BRANCH=""

cd "$REPO_DIR"

fail() {
    local msg="${1:-Unknown error}"
    echo "FAILED: $msg"

    # Restore user config regardless
    [ -f "$BACKUP" ] && cp "$BACKUP" "$CONFIG"

    # Write fail file
    {
        printf "Update failed: %s\n\n" "$(date)"
        printf "%s\n" "$msg"
    } > "$FAIL_FILE"

    # Push fail file to origin (best-effort)
    git add "$FAIL_FILE" 2>/dev/null
    git commit -m "Update failed: $(date +%Y-%m-%d)" 2>/dev/null || true
    [ -n "$BRANCH" ] && git push origin "$BRANCH" 2>/dev/null || true

    exit 1
}

echo "STATUS: Backing up settings..."
cp "$CONFIG" "$BACKUP" 2>"$ERR_TMP" || { echo "FAILED: Cannot backup config: $(cat "$ERR_TMP")"; exit 1; }

echo "STATUS: Preparing..."
git checkout HEAD -- config.json 2>"$ERR_TMP"
[ $? -ne 0 ] && fail "Cannot reset config.json: $(cat "$ERR_TMP")"

echo "STATUS: Detecting branch..."
# Ask remote for its HEAD — works without local tracking refs
BRANCH=$(git ls-remote --symref origin HEAD 2>/dev/null \
    | grep '^ref:' \
    | sed 's@^ref: refs/heads/@@; s/[[:space:]].*$//')

# Fallback to local branch name
if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
fi
# Last resort
if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
    BRANCH="main"
fi

echo "STATUS: Fetching ($BRANCH)..."
git fetch origin "$BRANCH" 2>"$ERR_TMP"
[ $? -ne 0 ] && fail "Fetch failed: $(cat "$ERR_TMP")"

echo "STATUS: Merging..."
git merge "origin/$BRANCH" 2>"$ERR_TMP"
[ $? -ne 0 ] && fail "Merge failed: $(cat "$ERR_TMP")"

echo "STATUS: Restoring settings..."
cp "$BACKUP" "$CONFIG" 2>"$ERR_TMP"
[ $? -ne 0 ] && fail "Cannot restore config: $(cat "$ERR_TMP")"

echo "DONE"
exit 0
