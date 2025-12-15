#!/usr/bin/env bash
set -euo pipefail

# Updates agentic configuration from central repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LATEST_VERSION=$(cat "$REPO_ROOT/VERSION")

# Source utilities
source "$SCRIPT_DIR/lib/version-manager.sh"

# Dynamically discover available extras from core directory
# Commands: all .md files in core/commands/claude/ EXCEPT core files (spec, agentic-*, o_spec)
discover_available_commands() {
  local cmds=()
  for f in "$REPO_ROOT/core/commands/claude/"*.md; do
    [[ ! -f "$f" ]] && continue
    local name=$(basename "$f" .md)
    # Skip core commands (always installed during setup, not extras)
    case "$name" in
      spec|agentic|agentic-*|o_spec) continue ;;
    esac
    cmds+=("$name")
  done
  echo "${cmds[@]}"
}

# Skills: all directories in core/skills/
discover_available_skills() {
  local skills=()
  for d in "$REPO_ROOT/core/skills/"*/; do
    [[ ! -d "$d" ]] && continue
    local name=$(basename "$d")
    skills+=("$name")
  done
  echo "${skills[@]}"
}

# Discover extras dynamically (no hardcoded lists!)
AVAILABLE_CMDS=($(discover_available_commands))
AVAILABLE_SKILLS=($(discover_available_skills))

# Defaults
FORCE=false
INSTALL_EXTRAS=false

usage() {
  cat <<EOF
Usage: update-config.sh [OPTIONS] [target_path]

Update agentic configuration to latest version from central repository.

Options:
  --force                Force update of copied files without prompting
  --extras               Install project-agnostic commands and skills
                         (orc, spawn, squash, pull_request, gh_pr_review, etc.)
  -h, --help             Show this help message

Notes:
  - Symlinked files update automatically
  - Copied files (.agent/config.yml, AGENTS.md) require manual review
  - If target_path not specified, uses current directory
EOF
}

# Parse arguments
TARGET_PATH="."
while [[ $# -gt 0 ]]; do
  case $1 in
    --force)
      FORCE=true
      shift
      ;;
    --extras)
      INSTALL_EXTRAS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "🔴 ERROR: Unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      TARGET_PATH="$1"
      shift
      ;;
  esac
done

# Function to clean up orphaned symlinks
cleanup_orphan_symlinks() {
  local target="$1"
  local dir="$2"
  local removed=0

  if [[ -d "$target/$dir" ]]; then
    for link in "$target/$dir"/*; do
      if [[ -L "$link" && ! -e "$link" ]]; then
        rm "$link"
        echo "  🟡 Removed orphan: $(basename "$link")"
        ((removed++)) || true
      fi
    done
  fi
  echo "$removed"
}

# Function to migrate customizations to PROJECT_AGENTS.md
migrate_to_project_agents() {
  local target="$1"
  local agents_file="$target/AGENTS.md"
  local project_file="$target/PROJECT_AGENTS.md"

  # Skip if PROJECT_AGENTS.md already exists
  [[ -f "$project_file" ]] && return 0

  # Skip if AGENTS.md doesn't exist
  [[ ! -f "$agents_file" ]] && return 0

  # Check if AGENTS.md has customization marker
  local marker_line=$(grep -n "CUSTOMIZE BELOW THIS LINE" "$agents_file" 2>/dev/null | cut -d: -f1)
  [[ -z "$marker_line" ]] && return 0

  # Extract content after marker (skip marker line + 1 comment line)
  local total_lines=$(wc -l < "$agents_file")
  local content_start=$((marker_line + 2))

  # Skip if no content after marker
  [[ $content_start -ge $total_lines ]] && return 0

  # Extract content and check if it's substantial (not just comments)
  local custom_content=$(tail -n +$content_start "$agents_file" | grep -v '^$' | grep -v '^<!--' | head -20)
  [[ -z "$custom_content" ]] && return 0

  # Has real customizations - migrate
  echo "🔵 Migrating customizations to PROJECT_AGENTS.md..."
  tail -n +$content_start "$agents_file" > "$project_file"
  echo "🟢 Migration complete: customizations preserved in PROJECT_AGENTS.md"

  return 0
}

# Validate
if [[ ! -d "$TARGET_PATH" ]]; then
  echo "🔴 ERROR: Directory does not exist: $TARGET_PATH" >&2
  exit 1
fi

TARGET_PATH="$(cd "$TARGET_PATH" && pwd)"

# Check if centralized config exists
if [[ ! -f "$TARGET_PATH/.agentic-config.json" ]]; then
  echo "🔴 ERROR: No centralized configuration found" >&2
  echo "   Run setup-config.sh or migrate-existing.sh first" >&2
  exit 1
fi

CURRENT_VERSION=$(check_version "$TARGET_PATH")
echo "🔵 Agentic Configuration Update"
echo "   Current version: $CURRENT_VERSION"
echo "   Latest version:  $LATEST_VERSION"

# Fix Codex symlink if needed (run even if versions match)
if [[ -L "$TARGET_PATH/.codex/prompts/spec.md" ]]; then
  CURRENT_TARGET=$(readlink "$TARGET_PATH/.codex/prompts/spec.md")
  if [[ "$CURRENT_TARGET" == *"spec-command.md" ]]; then
    echo "🔵 Fixing Codex spec symlink..."
    ln -sf "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
    echo "  ✓ Updated Codex symlink to use proper command file"
  fi
fi

if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" && "$INSTALL_EXTRAS" == false ]]; then
  echo "🟢 Already up to date!"
  echo "   Tip: Use --extras to install project-agnostic commands and skills"
  exit 0
fi

if [[ "$CURRENT_VERSION" == "$LATEST_VERSION" && "$INSTALL_EXTRAS" == true ]]; then
  echo "🟢 Version up to date, installing extras..."
fi

# Get project type from config
PROJECT_TYPE=$(jq -r '.project_type' "$TARGET_PATH/.agentic-config.json")
TEMPLATE_DIR="$REPO_ROOT/templates/$PROJECT_TYPE"

# Only run version update flow if there's actually a version change
if [[ "$CURRENT_VERSION" != "$LATEST_VERSION" ]]; then
  # Check if updates are opt-in
  AUTO_CHECK=$(jq -r '.auto_check // true' "$TARGET_PATH/.agentic-config.json" 2>/dev/null || echo "true")
  if [[ "$AUTO_CHECK" == "false" ]]; then
    echo "🟡 Auto-check disabled for this project"
    echo "   To enable: jq '.auto_check = true' .agentic-config.json > tmp && mv tmp .agentic-config.json"
  fi

  echo ""
  echo "🔵 Update available: $CURRENT_VERSION → $LATEST_VERSION"
  echo ""
  echo "Symlinked files will update automatically:"
  echo "  - agents/ (workflows)"
  echo "  - .claude/commands/spec.md"
  echo "  - .gemini/commands/spec.toml"
  echo "  - .codex/prompts/spec.md"
  echo ""

  # Check for changes in templates
  echo "Checking for template updates..."
  HAS_CONFIG_CHANGES=false
  HAS_AGENTS_CHANGES=false

  if [[ -f "$TEMPLATE_DIR/.agent/config.yml.template" ]]; then
    if ! diff -q "$TARGET_PATH/.agent/config.yml" "$TEMPLATE_DIR/.agent/config.yml.template" >/dev/null 2>&1; then
      HAS_CONFIG_CHANGES=true
    fi
  fi

  if [[ -f "$TEMPLATE_DIR/AGENTS.md.template" ]]; then
    # Check first 20 lines (template section) for changes
    if ! diff -q <(head -20 "$TARGET_PATH/AGENTS.md") <(head -20 "$TEMPLATE_DIR/AGENTS.md.template") >/dev/null 2>&1; then
      HAS_AGENTS_CHANGES=true
    fi
  fi

  if [[ "$HAS_CONFIG_CHANGES" == false && "$HAS_AGENTS_CHANGES" == false ]]; then
    echo "🟢 No template changes detected"
  else
    echo ""
    [[ "$HAS_CONFIG_CHANGES" == true ]] && echo "📄 .agent/config.yml has updates"
    [[ "$HAS_AGENTS_CHANGES" == true ]] && echo "📄 AGENTS.md template has updates"
    echo ""

    if [[ "$FORCE" == true ]]; then
      # Migrate customizations to PROJECT_AGENTS.md if needed
      migrate_to_project_agents "$TARGET_PATH"

      echo "🔵 Force updating templates..."
      [[ "$HAS_CONFIG_CHANGES" == true ]] && cp "$TEMPLATE_DIR/.agent/config.yml.template" "$TARGET_PATH/.agent/config.yml"
      [[ "$HAS_AGENTS_CHANGES" == true ]] && cp "$TEMPLATE_DIR/AGENTS.md.template" "$TARGET_PATH/AGENTS.md"
      echo "🟢 Templates updated"
    else
      echo "To view changes:"
      [[ "$HAS_CONFIG_CHANGES" == true ]] && echo "  diff $TARGET_PATH/.agent/config.yml $TEMPLATE_DIR/.agent/config.yml.template"
      [[ "$HAS_AGENTS_CHANGES" == true ]] && echo "  diff $TARGET_PATH/AGENTS.md $TEMPLATE_DIR/AGENTS.md.template"
      echo ""
      echo "To update:"
      echo "  update-config.sh --force $TARGET_PATH"
      echo ""
      echo "Or manually merge changes from templates"
    fi
  fi

  # Update version tracking
  if [[ "$FORCE" == true || "$HAS_CONFIG_CHANGES" == false ]]; then
    echo "🔵 Updating version tracking..."
    jq --arg version "$LATEST_VERSION" \
       --arg timestamp "$(date -Iseconds 2>/dev/null || date +%Y-%m-%dT%H:%M:%S%z)" \
       '.version = $version | .updated_at = $timestamp' \
       "$TARGET_PATH/.agentic-config.json" > "$TARGET_PATH/.agentic-config.json.tmp"
    mv "$TARGET_PATH/.agentic-config.json.tmp" "$TARGET_PATH/.agentic-config.json"
    echo "🟢 Version updated to $LATEST_VERSION"
  fi
fi

# Install extras if requested
if [[ "$INSTALL_EXTRAS" == true ]]; then
  echo ""
  echo "🔵 Installing project-agnostic commands..."
  echo "   Available: ${AVAILABLE_CMDS[*]}"
  mkdir -p "$TARGET_PATH/.claude/commands"
  CMDS_INSTALLED=0
  for cmd in "${AVAILABLE_CMDS[@]}"; do
    if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" ]]; then
      if [[ ! -L "$TARGET_PATH/.claude/commands/$cmd.md" ]]; then
        ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
        echo "  ✓ $cmd.md"
        ((CMDS_INSTALLED++)) || true
      fi
    fi
  done
  [[ $CMDS_INSTALLED -eq 0 ]] && echo "  (all commands already installed)"

  echo "🔵 Installing project-agnostic skills..."
  echo "   Available: ${AVAILABLE_SKILLS[*]}"
  mkdir -p "$TARGET_PATH/.claude/skills"
  SKILLS_INSTALLED=0
  for skill in "${AVAILABLE_SKILLS[@]}"; do
    if [[ -d "$REPO_ROOT/core/skills/$skill" ]]; then
      if [[ ! -L "$TARGET_PATH/.claude/skills/$skill" ]]; then
        ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
        echo "  ✓ $skill"
        ((SKILLS_INSTALLED++)) || true
      fi
    fi
  done
  [[ $SKILLS_INSTALLED -eq 0 ]] && echo "  (all skills already installed)"

  # Clean up orphaned symlinks
  echo "🔵 Cleaning up orphaned symlinks..."
  ORPHANS=$(cleanup_orphan_symlinks "$TARGET_PATH" ".claude/commands")
  if [[ $ORPHANS -gt 0 ]]; then
    echo "  Cleaned $ORPHANS orphan command symlink(s)"
  else
    echo "  (no orphans found)"
  fi

  ORPHANS=$(cleanup_orphan_symlinks "$TARGET_PATH" ".claude/skills")
  if [[ $ORPHANS -gt 0 ]]; then
    echo "  Cleaned $ORPHANS orphan skill symlink(s)"
  fi

  # Update config to track extras installation
  jq '.extras_installed = true' \
     "$TARGET_PATH/.agentic-config.json" > "$TARGET_PATH/.agentic-config.json.tmp"
  mv "$TARGET_PATH/.agentic-config.json.tmp" "$TARGET_PATH/.agentic-config.json"
  echo "🟢 Extras installed"
fi

echo ""
echo "🟢 Update complete!"
