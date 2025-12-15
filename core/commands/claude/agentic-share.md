---
description: Shared core logic for asset import/export (internal use)
argument-hint: <mode> <asset_type> <source> [target] [options]
project-agnostic: false
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Agentic Asset Share

Core logic for importing/exporting assets between projects and agentic-config repository.

## Arguments

- **mode**: `import` | `export`
- **asset_type**: `command` | `skill` | `template` | `agent`
- **source**: Source path or asset name
- **target**: (optional) Target name or path
- **options**: (optional) `--force` to overwrite, `--dry-run` to preview

Parsed from: $ARGUMENTS

## Asset Type Mappings

| Type | Project Location | Agentic-Config Location |
|------|------------------|------------------------|
| command | `.claude/commands/` | `core/commands/claude/` |
| skill | `.claude/skills/` | `core/skills/` |
| template | `templates/` | `templates/` |
| agent | N/A | `core/agents/` |

## Execution Flow

### Step 1: Parse Arguments

Extract from $ARGUMENTS:
- MODE = first argument (import/export)
- ASSET_TYPE = second argument
- SOURCE = third argument
- TARGET = fourth argument (optional)
- OPTIONS = remaining arguments

### Step 2: Validate Mode

If MODE is not `import` or `export`:
- ABORT with error: "Invalid mode. Use 'import' or 'export'"

### Step 3: Validate Asset Type

If ASSET_TYPE not in [command, skill, template, agent]:
- ABORT with error: "Invalid asset_type. Use: command, skill, template, agent"

### Step 4: Resolve Paths

#### Import Mode (external -> agentic-config)
- SOURCE_PATH = absolute path provided
- Verify SOURCE_PATH exists
- Extract PROJECT_ROOT = parent directory containing .claude/ or project root markers
- Map TARGET_PATH based on asset_type:
  - command -> `core/commands/claude/{filename}`
  - skill -> `core/skills/{dirname}/`
  - template -> `templates/{filename}`
  - agent -> `core/agents/{filename}`

#### Export Mode (project -> agentic-config)
- Run from project with agentic-config setup
- SOURCE_PATH = `.claude/{type}s/{name}` or asset name
- Detect AGENTIC_CONFIG_PATH:
  1. Use provided path if given
  2. Check $AGENTIC_CONFIG_ROOT env var
  3. Check `~/projects/agentic-config`
  4. ABORT if not found
- Map TARGET_PATH same as import mode

### Step 5: Read Source Content

Read the source file(s) completely.

For skills (directories):
- Read all .md files in the skill directory
- Track all files to process

### Step 6: Sanitization Pipeline (CRITICAL)

Apply these transforms IN ORDER:

1. **Absolute Path Replacement**
   - Pattern: `/Users/[^/]+/` -> `{USER_HOME}/`
   - Pattern: `/home/[^/]+/` -> `{USER_HOME}/`

2. **Project Root Replacement**
   - Detect project name from PROJECT_ROOT basename
   - Pattern: `{PROJECT_ROOT_PATH}` -> `{PROJECT_ROOT}`
   - Pattern: hardcoded project paths -> `{PROJECT_ROOT}`

3. **Project Name Replacement**
   - Pattern: exact project name matches -> `{PROJECT_NAME}`
   - Be conservative: only replace clear project name references

4. **Secret/Token Scrubbing**
   - Pattern: `(api[_-]?key|token|secret|password|credential)[s]?\s*[:=]\s*['"][^'"]+['"]` -> `{REDACTED}`
   - Pattern: `Bearer [A-Za-z0-9-_]+` -> `Bearer {REDACTED}`
   - Pattern: `sk-[A-Za-z0-9]+` -> `{REDACTED_API_KEY}`

5. **Environment Variable Paths**
   - Pattern: `\$HOME/` -> `{USER_HOME}/`
   - Pattern: `\${HOME}/` -> `{USER_HOME}/`

### Step 7: Validation

Scan sanitized content for REMAINING issues:

```
BLOCKERS (must fix before proceeding):
- Any remaining /Users/ or /home/ paths
- Any remaining hardcoded absolute paths
- Known secret patterns that weren't caught

WARNINGS (review but may proceed):
- Project-specific directory names
- Hardcoded port numbers
- Environment-specific configurations
```

If BLOCKERS found:
- ABORT
- Show each blocker with line number and content
- Suggest manual fixes

If WARNINGS found:
- Show warnings
- Ask: "Continue despite warnings? (yes/no)"
- Wait for confirmation

### Step 8: Check Target Exists

If TARGET_PATH exists and --force not provided:
- Show existing file content summary
- Ask: "Target exists. Overwrite? (yes/no)"
- Wait for confirmation

### Step 9: Write Sanitized Content

If --dry-run:
- Show what WOULD be written
- Show diff if target exists
- EXIT without writing

Otherwise:
- Write sanitized content to TARGET_PATH
- Preserve file permissions

### Step 10: Post-Write Validation

Re-read written file and verify:
- No absolute paths leaked
- File is valid markdown
- Frontmatter (if any) is valid YAML

### Step 11: Report

Output summary:
```
Asset {MODE}ed successfully:
- Source: {SOURCE_PATH}
- Target: {TARGET_PATH}
- Type: {ASSET_TYPE}
- Sanitizations applied: {count}
- Warnings: {count}

Next steps:
- Review the sanitized file
- Test the asset in agentic-config
- Commit when ready
```

## Error Handling

On ANY error:
1. Show clear error message
2. Show what was attempted
3. Do NOT leave partial files
4. Suggest recovery steps

## Security Notes

- NEVER copy files containing clear secrets
- ALWAYS sanitize before writing
- Validation failures ABORT the operation
- Manual review is recommended after every import/export

## Post-Workflow Commit

After successful import/export, offer to commit the asset.

### 1. Identify Target Repository
- **Import**: Currently in agentic-config repository
- **Export**: Target is agentic-config repository (may need to `cd` there)

### 2. Filter to Asset Files
Only stage the specific asset file(s):
- For commands: `core/commands/claude/{name}.md`
- For skills: `core/skills/{name}/`
- For templates: `templates/{name}/`
- For agents: `core/agents/{name}.md`

### 3. Offer Commit Option
Use AskUserQuestion:
- **Question**: "Commit {MODE}ed asset to agentic-config?"
- **Options**:
  - "Yes, commit now" (Recommended) → Commits the asset
  - "No, I'll commit later" → Skip commit
  - "Show changes first" → Run `git diff` on the asset then re-ask

**Note**: In auto-approve/yolo mode, default to "Yes, commit now".

### 4. Execute Commit
If user confirms:
```bash
# Navigate to agentic-config if needed
cd ~/projects/agentic-config  # or $AGENTIC_CONFIG_ROOT

# Stage the specific asset
git add {TARGET_PATH}

# Commit with descriptive message
git commit -m "feat(assets): {MODE} {ASSET_TYPE} '{ASSET_NAME}'

- Source: {SOURCE_PATH}
- Sanitized: {SANITIZATION_COUNT} replacements
- Type: {ASSET_TYPE}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### 5. Report Result
- Show commit hash if successful
- Show asset location in repository
- Remind: "Asset available to all projects after next update"
