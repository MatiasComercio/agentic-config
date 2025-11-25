# Agentic-Config Management Agent Guide

Natural language interface for managing agentic-config installations powered by Claude Code agents.

## Overview

The agentic management system provides specialized AI agents that handle setup, migration, updates, validation, and customization of agentic-config installations through conversational interfaces.

## Available Commands

| Command | Description | Example Usage |
|---------|-------------|---------------|
| `/agentic setup [path]` | Setup new project | `/agentic setup ~/projects/my-app` |
| `/agentic migrate [path]` | Migrate existing installation | `/agentic migrate .` |
| `/agentic update [path]` | Update to latest version | `/agentic update` |
| `/agentic status` | Show all installations | `/agentic status` |
| `/agentic validate [path]` | Check installation integrity | `/agentic validate .` |
| `/agentic customize` | Interactive customization guide | `/agentic customize` |

**Default path:** Current directory (`.`) if not specified

## Natural Language Usage

Agents respond to conversational requests:

```
"Setup agentic-config in this project"
"Migrate my manual agentic installation"
"Update to latest version"
"Show me all my installations"
"Validate this installation"
"Help me customize AGENTS.md"
```

Claude automatically invokes the appropriate agent based on your intent.

## Agent Descriptions

### Setup Agent (`agentic-setup`)

**Purpose:** Install agentic-config in new or existing projects

**Workflow:**
1. Detects project type (TypeScript, Python, Rust, etc.)
2. Asks confirmation for setup parameters
3. Explains what will be installed
4. Executes `setup-config.sh` with appropriate flags
5. Validates installation
6. Guides initial customization

**Best for:** Fresh projects, first-time setup

### Migrate Agent (`agentic-migrate`)

**Purpose:** Convert manual installations to centralized system

**Workflow:**
1. Identifies existing manual installation
2. Scans for customizations to preserve
3. Creates backup of current files
4. Executes `migrate-existing.sh`
5. Guides manual merge of custom content
6. Validates migration

**Best for:** Projects with manually-installed agentic configurations

### Update Agent (`agentic-update`)

**Purpose:** Sync to latest agentic-config version

**Workflow:**
1. Compares current vs latest version
2. Shows CHANGELOG for changes
3. Identifies files needing review
4. Shows diffs for template modifications
5. Offers update options (force/manual/skip)
6. Executes `update-config.sh`
7. Validates post-update

**Best for:** Keeping installations current

### Status Agent (`agentic-status`)

**Purpose:** Query all installations health

**Workflow:**
1. Reads central registry
2. Checks each project's version
3. Validates symlink integrity
4. Presents formatted status report
5. Highlights issues needing attention
6. Suggests remediation commands

**Best for:** Overview of all projects using agentic-config

### Validate Agent (`agentic-validate`)

**Purpose:** Diagnose and fix installation issues

**Workflow:**
1. Runs comprehensive integrity checks
2. Validates symlinks, configs, templates
3. Checks registry consistency
4. Presents diagnostic report
5. Offers auto-fix for common issues
6. Re-validates after fixes

**Best for:** Troubleshooting "/spec not working" or similar issues

### Customize Agent (`agentic-customize`)

**Purpose:** Guide safe customization

**Workflow:**
1. Asks what user wants to customize
2. Guides to correct file (AGENTS.md vs config.yml)
3. Shows relevant examples
4. Implements changes in safe areas
5. Explains update safety guarantees
6. Validates customizations loaded

**Best for:** Adding project-specific guidelines, architecture notes

## Example Workflows

### New Project Setup

```bash
cd ~/projects/new-app

# Natural language
"Setup agentic-config for this TypeScript project"

# Or slash command
/agentic setup

# Agent will:
# - Detect TypeScript via package.json
# - Ask confirmation
# - Explain installation (dry-run recommended)
# - Execute setup
# - Guide customization
```

### Update With Template Changes

```bash
cd ~/projects/my-app

/agentic update

# Agent shows:
# Current: v1.0.0 → Latest: v1.1.0
# CHANGELOG highlights
# Files needing review
# Diffs for AGENTS.md template section
#
# Options: force update, manual merge, or skip
```

### Troubleshooting

```bash
# /spec command not working after system upgrade

/agentic validate

# Agent diagnoses:
# - Checks all symlinks
# - Validates config files
# - Tests command availability
# - Identifies broken symlinks
# - Offers auto-fix
# - Re-validates
```

## Customization Safety

### AGENTS.md Structure

```markdown
## Core Principles
[Template section - updated by central repo]

## CUSTOMIZE BELOW THIS LINE
<!-- Your content - NEVER touched by updates -->

### Architecture
...your project notes...
```

**Update safety:**
- Template section (first ~20 lines): May change with updates
- Custom section (below marker): **Always preserved**
- Update agent only shows diffs for template section

### Files Behavior

**Symlinked (auto-update):**
- `agents/`, `.claude/commands/`, `.gemini/commands/`, `.codex/prompts/`
- Update instantly when central repo changes
- No customization possible

**Copied (customizable):**
- `AGENTS.md` - Customize below marker
- `.agent/config.yml` - Rarely needs changes

## Troubleshooting

### Agent Not Responding

**Issue:** Agent doesn't activate on natural language request

**Fix:**
- Use explicit slash command: `/agentic <action>`
- Check agent symlinks exist: `ls -la .claude/agents/agentic-*.md`
- Re-run setup if missing: `~/projects/agentic-config/scripts/setup-config.sh --force .`

### Permission Denied

**Issue:** Scripts fail with permission errors

**Fix:**
```bash
chmod +x ~/projects/agentic-config/scripts/*.sh
chmod +x ~/projects/agentic-config/scripts/lib/*.sh
```

### Broken Symlinks

**Issue:** Symlinks point to non-existent files

**Fix:**
```bash
/agentic validate  # Diagnoses issue
# Agent offers auto-fix via setup-config.sh --force
```

## Advanced Usage

### Batch Operations

```bash
# Update all installations
/agentic status  # Shows which need updates
# Then manually run update on each, or use status output

# Validate all projects
for project in $(jq -r '.installations[].path' ~/.../agentic-config/.installations.json); do
  echo "Validating: $project"
  cd "$project" && /agentic validate
done
```

### Custom Workflows

Create project-specific commands in `.claude/commands/`:

```markdown
<!-- .claude/commands/my-workflow.md -->
---
description: Custom workflow combining agentic features
---

1. Validate installation
2. Update to latest
3. Run project tests
4. Deploy if passing

Use agentic-validate, agentic-update agents in sequence.
```

## Version History

- **v1.1.0** - Initial agent system release
- **v1.0.1** - Codex CLI support added
- **v1.0.0** - Initial centralized configuration system

## See Also

- [Main README](../../README.md) - Full documentation
- [CHANGELOG](../../CHANGELOG.md) - Version history
- [Setup Script](../../scripts/setup-config.sh) - Manual installation
- [Update Script](../../scripts/update-config.sh) - Manual updates
