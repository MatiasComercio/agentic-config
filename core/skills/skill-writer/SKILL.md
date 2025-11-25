---
name: skill-writer
description: Expert assistant for authoring Claude Code skills. Creates precise SKILL.md files with proper YAML frontmatter, validates naming conventions, and applies official best practices. Triggers on keywords: writing skills, creating skills, skill authoring, SKILL.md, new skill, skill template, skill validation, skill structure, create skill, update skill
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Skill Writer

Expert guide for creating Claude Code skills. Reference: https://code.claude.com/docs/en/skills

## Quick Reference

### YAML Frontmatter Template
```yaml
---
name: skill-name
description: Third-person description under 1024 chars. Triggers on keywords: keyword1, keyword2
project-agnostic: false  # REQUIRED: explicitly set true for reusable skills, false for project-specific
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---
```

### Directory Structure
```
.claude/skills/
  skill-name/
    SKILL.md           # Required - main skill definition
    supporting-file.md # Optional - one level deep only
```

### Project-Agnostic Field

**REQUIRED FIELD** - Must be explicitly set for every skill.

**Default: `false`** - Assumes skills are project-specific unless explicitly marked otherwise.

**Set to `true` when the skill:**
- Contains no project-specific paths, structures, or conventions
- Can be copied to any project without modification
- Has no dependencies on specific project tooling or workflows

**Set to `false` when the skill depends on:**
- Project-specific directory structures or paths
- Project-specific configuration files or conventions
- Project-specific tooling or workflows

**When `project-agnostic: false`, the skill MUST document:**
- What project-specific dependencies exist
- What assumptions are made about project structure
- What configuration or setup is required

## Validation Checklist

Before creating any skill, verify:

| Field | Constraint | Check |
|-------|------------|-------|
| `name` | Max 64 chars | `len(name) <= 64` |
| `name` | Lowercase, numbers, hyphens only | `/^[a-z0-9-]+$/` |
| `name` | No reserved words | No "anthropic" or "claude" |
| `description` | Max 1024 chars | `len(description) <= 1024` |
| `description` | Third person only | No "I", "you", "we" |
| `project-agnostic` | Boolean, REQUIRED | Must be explicitly set (true/false) |
| SKILL.md | Under 500 lines | `wc -l < 500` |
| SKILL.md | No bash execution pattern | No exclamation-mark-backtick sequence |
| File refs | One level deep | No nested directories |
| Paths | Forward slashes only | No backslashes |

### Name Validation Regex
```python
import re
def validate_name(name: str) -> bool:
    if len(name) > 64:
        return False
    if not re.match(r'^[a-z0-9-]+$', name):
        return False
    if 'anthropic' in name or 'claude' in name:
        return False
    return True
```

### Content Safety Validation
```python
import re
def has_unsafe_bash_pattern(content: str) -> bool:
    """Detects exclamation-mark-backtick pattern that triggers bash execution during skill loading."""
    return bool(re.search(r'!\`', content))
```

## Skill Patterns

### Pattern 1: Simple Read-Only Skill
For skills that only need to read and analyze.
```yaml
---
name: code-reviewer
description: Performs code review on specified files. Analyzes style, patterns, and potential issues. Triggers on keywords: review code, code review, check code quality
project-agnostic: true
allowed-tools:
  - Read
  - Glob
  - Grep
---
```

### Pattern 2: Documentation Skill
For skills that read, analyze, and write documentation.
```yaml
---
name: api-documenter
description: Generates API documentation from source code. Extracts function signatures, docstrings, and usage examples. Triggers on keywords: document API, API docs, generate documentation
project-agnostic: true
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---
```

### Pattern 3: Multi-File Refactoring Skill
For skills that need to edit multiple files.
```yaml
---
name: import-organizer
description: Organizes and sorts imports across Python files. Groups stdlib, third-party, and local imports. Triggers on keywords: organize imports, sort imports, fix imports
project-agnostic: true
allowed-tools:
  - Read
  - Edit
  - Glob
  - Grep
---
```

### Pattern 4: Workflow Skill with Bash
For skills that need to run commands.
```yaml
---
name: test-runner
description: Executes test suites and analyzes results. Runs pytest with coverage and reports failures. Triggers on keywords: run tests, execute tests, test suite
project-agnostic: false
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---
```

## Writing Effective Descriptions

### Formula
```
[Action verb] + [what it does] + [how/with what]. [Additional capability]. Triggers on keywords: [comma-separated keywords]
```

### Good Examples
- "Generates TypeScript interfaces from JSON schemas. Handles nested objects and arrays. Triggers on keywords: json to typescript, generate types, schema conversion"
- "Analyzes Python code for security vulnerabilities. Checks for injection, auth issues, and data exposure. Triggers on keywords: security audit, vulnerability scan, code security"

### Bad Examples
- "I help you write better code" (first person, vague)
- "A tool for doing stuff with files" (vague, no triggers)
- "This skill will assist the user in..." (second person)

### Trigger Keywords
- Include 3-7 natural phrases users might say
- Mix specific and general terms
- Include synonyms and variations

## Anti-Patterns to Avoid

### 1. Overly Broad Skills
```yaml
# Bad - too broad, unfocused
name: code-helper
description: Helps with all coding tasks
```
```yaml
# Good - focused purpose
name: python-type-annotator
description: Adds type annotations to Python functions. Infers types from usage and docstrings. Triggers on keywords: add types, type hints, annotate python
project-agnostic: true
```

### 2. Excessive Tool Permissions
```yaml
# Bad - grants all tools for simple task
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
```
```yaml
# Good - minimal permissions
allowed-tools:
  - Read
  - Glob
```

### 3. Bloated SKILL.md Files
- Include only information Claude does not already know
- Avoid restating general programming knowledge
- Focus on project-specific patterns and conventions

### 4. Reserved Name Usage
```yaml
# Invalid - contains reserved word
name: claude-assistant
name: anthropic-helper
```

### 5. Deep File Nesting
```
# Invalid - nested too deep
.claude/skills/my-skill/templates/python/base.md

# Valid - one level only
.claude/skills/my-skill/python-template.md
```

### 6. Missing Trigger Keywords
```yaml
# Bad - no discoverability
description: Formats SQL queries

# Good - discoverable
description: Formats SQL queries with consistent style. Handles SELECT, INSERT, UPDATE, DELETE. Triggers on keywords: format sql, sql formatter, pretty print sql
```

### 7. Bash Execution Pattern in Content
```yaml
# Bad - causes bash execution error during skill loading
# Error: Bash command failed for pattern "[BANG-backtick][backtick]": (eval):1: command not found
description: Shows slash command syntax like [BANG-backtick] ls -la [backtick]
```
```yaml
# Good - use safe alternatives
description: Shows slash command syntax using text like "BANG-backtick: ls -la" or describe textually
```

When documenting slash commands or examples that include exclamation marks:
- **Problem**: The pattern exclamation-mark-backtick (visually: `[BANG][backtick]`) triggers bash execution during skill loading
- **Error message**: `Bash command failed for pattern "![backtick][backtick]": [stderr] (eval):1: command not found:`
- **Safe alternatives**:
  - Use text: "BANG-backtick: command here"
  - Use placeholder: `[BANG-backtick: command]`
  - Describe textually without showing the exact syntax

### 8. Missing Project-Agnostic Field
```yaml
# Bad - missing required field
name: my-skill
description: Does something useful
allowed-tools:
  - Read
# ERROR: project-agnostic field is missing
```
```yaml
# Good - explicit declaration
name: my-skill
description: Does something useful
project-agnostic: false  # Explicitly marks as project-specific
allowed-tools:
  - Read
```

## Testing Recommendations

### Cross-Model Testing
Test skills across different Claude models to ensure consistent behavior:
1. Claude Sonnet - primary model
2. Claude Opus - complex reasoning
3. Claude Haiku - quick tasks

### Test Cases
For each skill, verify:
1. **Trigger activation**: Skill activates on expected keywords
2. **Tool usage**: Only uses allowed tools
3. **Output format**: Produces expected output structure
4. **Edge cases**: Handles empty files, missing data, errors

### Manual Testing Script
```bash
# Test skill discovery
ls -la .claude/skills/

# Verify SKILL.md line count
wc -l .claude/skills/skill-name/SKILL.md

# Validate YAML frontmatter
head -20 .claude/skills/skill-name/SKILL.md
```

## Pre-Share Checklist

Before distributing a skill:

- [ ] Name is max 64 chars, lowercase/numbers/hyphens only
- [ ] Name does not contain "anthropic" or "claude"
- [ ] Description is max 1024 chars, third person only
- [ ] Description includes trigger keywords
- [ ] `project-agnostic` field is explicitly set (REQUIRED)
- [ ] `project-agnostic: true` only if skill has zero project dependencies
- [ ] `project-agnostic: false` documents what project dependencies exist
- [ ] SKILL.md is under 500 lines
- [ ] All file references are one level deep
- [ ] All paths use forward slashes
- [ ] Only necessary tools are in allowed-tools
- [ ] Tested on target Claude model(s)
- [ ] Contains only project-specific knowledge

## Creating a New Skill

### Step-by-Step Process
1. Define purpose and scope (narrow > broad)
2. Choose minimal required tools
3. Write third-person description with triggers
4. Create directory: `.claude/skills/{name}/`
5. Write SKILL.md with frontmatter
6. Add supporting files if needed (one level deep)
7. Validate against checklist
8. Test with representative prompts

### Minimal Viable Skill
```yaml
---
name: example-skill
description: Performs a specific task on target files. Triggers on keywords: example, demo skill
project-agnostic: true
allowed-tools:
  - Read
  - Glob
---

# Example Skill

Brief description of what this skill does.

## Usage

When to use this skill and expected inputs.

## Output

What the skill produces.
```

## Supporting Files

Skills can reference additional files for:
- Templates
- Schemas
- Examples
- Configuration

### Reference Syntax
```markdown
See [template](./template.md) for the output format.
```

### Constraints
- Files must be in same directory as SKILL.md
- Maximum one level of nesting
- Use forward slashes in paths
- Keep supporting files focused and concise
