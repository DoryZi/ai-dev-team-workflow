#!/usr/bin/env bash
set -euo pipefail

# Sync agents, skills, and conventions from the main ai_will_replace_you repo,
# and the /review skill from the ai-code-review-demo submodule.
#
# Run from the ai-dev-team-workflow/ directory.
#
# Usage:
#   ./sync-from-source.sh                    # copy files
#   ./sync-from-source.sh --dry-run          # list what would be copied

SOURCE_REPO="${SOURCE_REPO:-$(cd "$(dirname "$0")/../.." && pwd)}"
DEST_DIR="$(cd "$(dirname "$0")" && pwd)"
REVIEW_REPO="${SOURCE_REPO}/open-source-repos/ai-code-reviewer"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

# ── File mapping: source (relative to SOURCE_REPO) → dest (relative to DEST_DIR) ──

declare -A FILES=(
    # Agents
    [".claude/agents/sde.md"]=".claude/agents/sde.md"
    [".claude/agents/test-eng.md"]=".claude/agents/test-eng.md"

    # Skills
    [".claude/skills/dev-tdd/SKILL.md"]=".claude/skills/dev-tdd/SKILL.md"
    [".claude/skills/dev-fast/SKILL.md"]=".claude/skills/dev-fast/SKILL.md"
    [".claude/skills/run-tests/SKILL.md"]=".claude/skills/run-tests/SKILL.md"
    [".claude/skills/python-reviewer/SKILL.md"]=".claude/skills/python-reviewer/SKILL.md"

    # Conventions
    ["conventions/python-coding.md"]="conventions/python-coding.md"
)

# ── Files from the ai-code-review-demo repo ──

declare -A REVIEW_FILES=(
    [".claude/skills/review/SKILL.md"]=".claude/skills/review/SKILL.md"
)

# ── Helper ──

copy_file() {
    local src_path="$1" dest_rel="$2" label="$3"
    local dest_path="${DEST_DIR}/${dest_rel}"

    if [[ ! -f "$src_path" ]]; then
        echo "SKIP (not found): ${label}"
        skipped=$((skipped + 1))
        return
    fi

    if $DRY_RUN; then
        echo "WOULD COPY: ${label} → ${dest_rel}"
    else
        mkdir -p "$(dirname "$dest_path")"
        cp "$src_path" "$dest_path"
        echo "COPIED: ${label} → ${dest_rel}"
    fi
    copied=$((copied + 1))
}

# ── Sync ──

copied=0
skipped=0

echo "=== Syncing from main repo: ${SOURCE_REPO} ==="
for src_rel in "${!FILES[@]}"; do
    copy_file "${SOURCE_REPO}/${src_rel}" "${FILES[$src_rel]}" "$src_rel"
done

echo ""
echo "=== Syncing from ai-code-review-demo: ${REVIEW_REPO} ==="
for src_rel in "${!REVIEW_FILES[@]}"; do
    copy_file "${REVIEW_REPO}/${src_rel}" "${REVIEW_FILES[$src_rel]}" "ai-code-review-demo:${src_rel}"
done

echo ""
if $DRY_RUN; then
    echo "Dry run: ${copied} files would be copied, ${skipped} skipped"
else
    echo "Done: ${copied} files copied, ${skipped} skipped"
fi
