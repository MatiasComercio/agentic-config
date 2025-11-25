#!/usr/bin/env bash
set -euo pipefail

# Agentic Configuration Setup Script
# Installs centralized agentic tools configuration to target project

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
VERSION=$(cat "$REPO_ROOT/VERSION")

# Source utilities
source "$SCRIPT_DIR/lib/detect-project-type.sh"
source "$SCRIPT_DIR/lib/template-processor.sh"
source "$SCRIPT_DIR/lib/version-manager.sh"

# Defaults
FORCE=false
DRY_RUN=false
NO_REGISTRY=false
TOOLS="all"
PROJECT_TYPE=""
INSTALL_EXTRAS=false

# Usage
usage() {
  cat <<EOF
Usage: setup-config.sh [OPTIONS] <target_path>

Install centralized agentic configuration to a project.

Options:
  --type <ts|py-poetry|py-pip|py-uv|rust|generic>
                         Project type (auto-detected if not specified)
  --force                Overwrite existing configuration
  --dry-run              Show what would be done without making changes
  --no-registry          Don't register installation in central registry
  --tools <claude,gemini,codex,all>
                         Which AI tool configs to install (default: all)
  --extras               Install project-agnostic commands and skills
                         (orc, spawn, squash, pull_request, gh_pr_review, etc.)
  -h, --help             Show this help message

Examples:
  # Auto-detect and setup
  setup-config.sh ~/projects/my-app

  # Explicit project type
  setup-config.sh --type typescript ~/projects/my-app

  # Dry run to preview
  setup-config.sh --dry-run ~/projects/my-app
EOF
}

# Parse arguments
TARGET_PATH=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --type)
      PROJECT_TYPE="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --no-registry)
      NO_REGISTRY=true
      shift
      ;;
    --tools)
      TOOLS="$2"
      shift 2
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

# Validate target path
if [[ -z "$TARGET_PATH" ]]; then
  echo "🔴 ERROR: target_path required" >&2
  usage
  exit 1
fi

# Resolve absolute path
if [[ ! -d "$TARGET_PATH" ]]; then
  echo "🔴 ERROR: Directory does not exist: $TARGET_PATH" >&2
  exit 1
fi
TARGET_PATH="$(cd "$TARGET_PATH" && pwd)"

echo "🔵 Agentic Configuration Setup v$VERSION"
echo "   Target: $TARGET_PATH"

# Auto-detect project type if not specified
if [[ -z "$PROJECT_TYPE" ]]; then
  PROJECT_TYPE=$(detect_project_type "$TARGET_PATH")
  echo "   Detected type: $PROJECT_TYPE"
else
  echo "   Type: $PROJECT_TYPE"
fi

# Validate template exists
TEMPLATE_DIR="$REPO_ROOT/templates/$PROJECT_TYPE"
if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "🔴 ERROR: No template for project type: $PROJECT_TYPE" >&2
  echo "   Available: typescript, python-poetry, python-pip, python-uv, rust, generic" >&2
  exit 1
fi

# Check for existing installation
if [[ -L "$TARGET_PATH/agents" || -f "$TARGET_PATH/.agentic-config.json" ]]; then
  EXISTING_VERSION=$(check_version "$TARGET_PATH")
  if [[ "$FORCE" != true ]]; then
    echo "🟡 Existing installation detected (version: $EXISTING_VERSION)"
    echo "   Use --force to overwrite or run update-config.sh to update"
    exit 0
  fi
  echo "   Overwriting existing installation (version: $EXISTING_VERSION)"
fi

# Backup existing files if they exist
BACKED_UP=false
if [[ -e "$TARGET_PATH/agents" || -e "$TARGET_PATH/.agent" || -e "$TARGET_PATH/AGENTS.md" ]]; then
  BACKUP_DIR="$TARGET_PATH/.agentic-config.backup.$(date +%s)"
  echo "🔵 Creating backup: $BACKUP_DIR"

  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$BACKUP_DIR"
    [[ -e "$TARGET_PATH/agents" ]] && mv "$TARGET_PATH/agents" "$BACKUP_DIR/" 2>/dev/null || true
    [[ -e "$TARGET_PATH/.agent" ]] && mv "$TARGET_PATH/.agent" "$BACKUP_DIR/" 2>/dev/null || true
    [[ -e "$TARGET_PATH/AGENTS.md" ]] && mv "$TARGET_PATH/AGENTS.md" "$BACKUP_DIR/" 2>/dev/null || true
    [[ -e "$TARGET_PATH/CLAUDE.md" ]] && rm "$TARGET_PATH/CLAUDE.md" 2>/dev/null || true
    [[ -e "$TARGET_PATH/GEMINI.md" ]] && rm "$TARGET_PATH/GEMINI.md" 2>/dev/null || true
    BACKED_UP=true
  fi
fi

# Create core symlinks
echo "🔵 Creating core symlinks..."
if [[ "$DRY_RUN" != true ]]; then
  ln -sf "$REPO_ROOT/core/agents" "$TARGET_PATH/agents"
  mkdir -p "$TARGET_PATH/.agent/workflows"
  ln -sf "$REPO_ROOT/core/agents/spec-command.md" "$TARGET_PATH/.agent/workflows/spec.md"
fi

# Install templates
echo "🔵 Installing config templates ($PROJECT_TYPE)..."
if [[ "$DRY_RUN" != true ]]; then
  process_template "$TEMPLATE_DIR/.agent/config.yml.template" "$TARGET_PATH/.agent/config.yml"
  process_template "$TEMPLATE_DIR/AGENTS.md.template" "$TARGET_PATH/AGENTS.md"
fi

# Create local symlinks
echo "🔵 Creating local symlinks..."
if [[ "$DRY_RUN" != true ]]; then
  ln -sf AGENTS.md "$TARGET_PATH/CLAUDE.md"
  ln -sf AGENTS.md "$TARGET_PATH/GEMINI.md"
fi

# Install AI tool configs
if [[ "$TOOLS" == "all" || "$TOOLS" == *"claude"* ]]; then
  echo "🔵 Installing Claude configs..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.claude/commands"
    ln -sf "$REPO_ROOT/core/commands/claude/spec.md" "$TARGET_PATH/.claude/commands/spec.md"
  fi
fi

if [[ "$TOOLS" == "all" || "$TOOLS" == *"gemini"* ]]; then
  echo "🔵 Installing Gemini configs..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.gemini/commands"
    ln -sf "$REPO_ROOT/core/commands/gemini/spec.toml" "$TARGET_PATH/.gemini/commands/spec.toml"
    ln -sf "$REPO_ROOT/core/commands/gemini/spec" "$TARGET_PATH/.gemini/commands/spec"
  fi
fi

if [[ "$TOOLS" == "all" || "$TOOLS" == *"codex"* ]]; then
  echo "🔵 Installing Codex configs..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.codex/prompts"
    ln -sf "$REPO_ROOT/core/commands/codex/spec.md" "$TARGET_PATH/.codex/prompts/spec.md"
  fi
fi

# Install agentic management agents and commands
echo "🔵 Installing agentic management agents..."
if [[ "$DRY_RUN" != true ]]; then
  # Create agent symlinks
  mkdir -p "$TARGET_PATH/.claude/agents"
  for agent in agentic-setup agentic-migrate agentic-update agentic-status agentic-validate agentic-customize; do
    ln -sf "$REPO_ROOT/core/agents/$agent.md" "$TARGET_PATH/.claude/agents/$agent.md"
  done

  # Create agentic command symlinks
  for cmd in agentic agentic-setup agentic-migrate agentic-update agentic-status; do
    ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
  done
fi

# Install extra project-agnostic commands and skills
if [[ "$INSTALL_EXTRAS" == true ]]; then
  echo "🔵 Installing project-agnostic commands..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.claude/commands"
    for cmd in orc spawn squash squash_commit pull_request gh_pr_review; do
      if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" ]]; then
        ln -sf "$REPO_ROOT/core/commands/claude/$cmd.md" "$TARGET_PATH/.claude/commands/$cmd.md"
      fi
    done
  fi

  echo "🔵 Installing project-agnostic skills..."
  if [[ "$DRY_RUN" != true ]]; then
    mkdir -p "$TARGET_PATH/.claude/skills"
    for skill in agent-orchestrator-manager single-file-uv-scripter command-writer skill-writer git-find-fork; do
      if [[ -d "$REPO_ROOT/core/skills/$skill" ]]; then
        ln -sf "$REPO_ROOT/core/skills/$skill" "$TARGET_PATH/.claude/skills/$skill"
      fi
    done
  fi
fi

# Register installation
if [[ "$NO_REGISTRY" != true && "$DRY_RUN" != true ]]; then
  echo "🔵 Registering installation..."
  register_installation "$TARGET_PATH" "$PROJECT_TYPE" "$VERSION"
fi

# Summary
echo ""
echo "🟢 Setup complete!"
echo "   Version: $VERSION"
echo "   Type: $PROJECT_TYPE"
[[ "$INSTALL_EXTRAS" == true ]] && echo "   Extras: commands + skills installed"
[[ "$BACKED_UP" == true ]] && echo "   Backup: $BACKUP_DIR"
[[ "$DRY_RUN" == true ]] && echo "   (DRY RUN - no changes made)"
echo ""
echo "Next steps:"
echo "  1. Review and customize AGENTS.md for project-specific guidelines"
echo "  2. Test with: cd $TARGET_PATH && /spec RESEARCH <spec_path>"
[[ "$INSTALL_EXTRAS" == true ]] && echo "  3. Try /orc, /spawn, /pull_request commands"
echo "  See documentation: $REPO_ROOT/README.md"
