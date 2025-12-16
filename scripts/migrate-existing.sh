#!/usr/bin/env bash
set -euo pipefail

# Migrates manually-installed agentic configuration to centralized system

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(cat "$REPO_ROOT/VERSION")

# Source utilities
source "$SCRIPT_DIR/lib/detect-project-type.sh"
source "$SCRIPT_DIR/lib/version-manager.sh"

# Defaults
DRY_RUN=false
FORCE=false

usage() {
  cat <<EOF
Usage: migrate-existing.sh [OPTIONS] <target_path>

Migrate manually-installed agentic configuration to centralized system.

Options:
  --dry-run              Show what would be done without making changes
  --force                Skip confirmation prompts
  -h, --help             Show this help message

This script:
  1. Detects current manual installation
  2. Creates backup of existing files
  3. Converts local files to symlink pattern
  4. Preserves customizations in AGENTS.md
  5. Registers installation in central registry
EOF
}

# Parse arguments
TARGET_PATH=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "ERROR: Unknown option: $1" >&2
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
if [[ -z "$TARGET_PATH" ]]; then
  echo "ERROR: target_path required" >&2
  usage
  exit 1
fi

if [[ ! -d "$TARGET_PATH" ]]; then
  echo "ERROR: Directory does not exist: $TARGET_PATH" >&2
  exit 1
fi

TARGET_PATH="$(cd "$TARGET_PATH" && pwd)"

echo "Agentic Configuration Migration v$VERSION"
echo "   Target: $TARGET_PATH"

# Check if already centralized
if [[ -L "$TARGET_PATH/agents" && -f "$TARGET_PATH/.agentic-config.json" ]]; then
  EXISTING_VERSION=$(check_version "$TARGET_PATH")
  echo "Already centralized (version: $EXISTING_VERSION)"
  echo "   Use update-config.sh to sync latest changes"
  exit 0
fi

# Detect manual installation
HAS_AGENTS=false
HAS_AGENT_DIR=false
HAS_AGENTS_MD=false

[[ -d "$TARGET_PATH/agents" ]] && HAS_AGENTS=true
[[ -d "$TARGET_PATH/.agent" ]] && HAS_AGENT_DIR=true
[[ -f "$TARGET_PATH/AGENTS.md" ]] && HAS_AGENTS_MD=true

if [[ "$HAS_AGENTS" == false && "$HAS_AGENT_DIR" == false ]]; then
  echo "WARNING: No agentic configuration detected"
  echo "   Use setup-config.sh for new installation"
  exit 0
fi

# Auto-detect project type
PROJECT_TYPE=$(detect_project_type "$TARGET_PATH")
echo "   Detected type: $PROJECT_TYPE"

# Confirm migration
if [[ "$FORCE" != true && "$DRY_RUN" != true ]]; then
  echo ""
  echo "Migration will:"
  echo "  - Backup existing files to .agentic-config.backup.$(date +%s)"
  echo "  - Replace agents/ with symlink to central repo"
  echo "  - Preserve AGENTS.md customizations"
  echo "  - Register installation in central registry"
  echo ""
  read -p "Proceed with migration? [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled"
    exit 0
  fi
fi

# Create backup
BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)"
echo "Creating backup: $BACKUP_DIR"
if [[ "$DRY_RUN" != true ]]; then
  mkdir -p "$BACKUP_DIR"
  [[ -d "$TARGET_PATH/agents" ]] && cp -r "$TARGET_PATH/agents" "$BACKUP_DIR/"
  [[ -d "$TARGET_PATH/.agent" ]] && cp -r "$TARGET_PATH/.agent" "$BACKUP_DIR/"
  [[ -f "$TARGET_PATH/AGENTS.md" ]] && cp "$TARGET_PATH/AGENTS.md" "$BACKUP_DIR/"
fi

# Remove old agents/ directory (will be replaced with symlink)
if [[ -d "$TARGET_PATH/agents" && ! -L "$TARGET_PATH/agents" ]]; then
  echo "Removing old agents/ directory..."
  [[ "$DRY_RUN" != true ]] && rm -rf "$TARGET_PATH/agents"
fi

# Call setup-config with force
echo "Installing centralized configuration..."
if [[ "$DRY_RUN" == true ]]; then
  "$SCRIPT_DIR/setup-config.sh" --dry-run --force --type "$PROJECT_TYPE" "$TARGET_PATH"
else
  "$SCRIPT_DIR/setup-config.sh" --force --type "$PROJECT_TYPE" "$TARGET_PATH"
fi

echo ""
echo "Migration complete!"
echo "   Backup: $BACKUP_DIR"
echo "   Version: $VERSION"
echo ""
echo "Next steps:"
echo "  1. Review AGENTS.md and merge any custom content from backup"
echo "  2. Test workflows: /spec RESEARCH <spec_path>"
echo "  3. If satisfied, remove backup: rm -rf $BACKUP_DIR"
