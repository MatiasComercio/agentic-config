---
description: Export project asset to agentic-config repository
argument-hint: <asset_type> <asset_name> [agentic_config_path] [--force] [--dry-run]
project-agnostic: false
---

# Agentic Export

Export an asset from the current project INTO the agentic-config repository.

**Run from**: Project with agentic-config setup (has `.claude/` directory)

## Arguments

- **asset_type**: `command` | `skill` | `template`
- **asset_name**: Name of the asset in `.claude/{type}s/`
- **agentic_config_path**: (optional) Path to agentic-config repo
  - Default: `~/projects/agentic-config` or `$AGENTIC_CONFIG_ROOT`
- **--force**: Overwrite existing without prompt
- **--dry-run**: Preview without writing

Request: $ARGUMENTS

## Execution

Delegate to shared core logic:

```
/agentic-share export $ARGUMENTS
```

## Examples

```bash
# Export a command to default agentic-config location
/agentic-export command my-useful-cmd

# Export a skill
/agentic-export skill my-skill

# Export to specific agentic-config path
/agentic-export command my-cmd /custom/path/to/agentic-config

# Dry run to preview sanitization
/agentic-export command my-cmd --dry-run
```

## Pre-Flight Check

Before delegating, verify:
1. Current directory has `.claude/` directory
2. Asset exists in `.claude/{type}s/{name}`
3. Agentic-config path is resolvable

If checks fail, provide clear error and exit.

## Path Resolution

Agentic-config path resolution order:
1. Explicit path argument
2. `$AGENTIC_CONFIG_ROOT` environment variable
3. `~/projects/agentic-config` (default)
4. ABORT if none found
