---
description: Import external asset into agentic-config repository
argument-hint: <asset_type> <source_path> [target_name] [--force] [--dry-run]
project-agnostic: false
---

# Agentic Import

Import an asset from an external project INTO the agentic-config repository.

**Run from**: agentic-config repository root

## Arguments

- **asset_type**: `command` | `skill` | `template` | `agent`
- **source_path**: Absolute path to the asset to import
- **target_name**: (optional) Name for the imported asset
- **--force**: Overwrite existing without prompt
- **--dry-run**: Preview without writing

Request: $ARGUMENTS

## Execution

Delegate to shared core logic:

```
/agentic-share import $ARGUMENTS
```

## Examples

```bash
# Import a command
/agentic-import command /path/to/project/.claude/commands/my-cmd.md

# Import a skill directory
/agentic-import skill /path/to/project/.claude/skills/my-skill/

# Import with custom name
/agentic-import command /path/to/project/.claude/commands/old-name.md new-name

# Dry run to preview
/agentic-import command /path/to/source.md --dry-run
```

## Pre-Flight Check

Before delegating, verify:
1. Current directory is agentic-config root (check for `core/` directory)
2. Source path exists
3. Source path is absolute

If checks fail, provide clear error and exit.
