#!/usr/bin/env bash
set -euo pipefail

# Updates agentic configuration from central repository

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
LATEST_VERSION=$(cat "$REPO_ROOT/VERSION")

# Source utilities
source "$SCRIPT_DIR/lib/version-manager.sh"

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
      echo "🔵 Force updating templates..."
      [[ "$HAS_CONFIG_CHANGES" == true ]] && cp "$TEMPLATE_DIR/.agent/config.yml.template" "$TARGET_PATH/.agent/config.yml"
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
  mkdir -p "$TARGET_PATH/.claude/commands"
  CMDS_INSTALLED=0
  for cmd in orc spawn squash squash_commit pull_request gh_pr_review; do
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
  mkdir -p "$TARGET_PATH/.claude/skills"
  SKILLS_INSTALLED=0
  for skill in agent-orchestrator-manager single-file-uv-scripter command-writer skill-writer git-find-fork; do
    if [[ -d "$REPO_ROOT/core/skills/$skill" ]]; then
      if [[ ! -L "$TARGET_PATH/.claude/skills/$skill" ]]; then
        ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
        echo "  ✓ $skill"
        ((SKILLS_INSTALLED++)) || true
      fi
    fi
  done
  [[ $SKILLS_INSTALLED -eq 0 ]] && echo "  (all skills already installed)"

  # Update config to track extras installation
  jq '.extras_installed = true' \
     "$TARGET_PATH/.agentic-config.json" > "$TARGET_PATH/.agentic-config.json.tmp"
  mv "$TARGET_PATH/.agentic-config.json.tmp" "$TARGET_PATH/.agentic-config.json"
  echo "🟢 Extras installed"
fi

echo ""
echo "🟢 Update complete!"
