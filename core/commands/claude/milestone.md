---
description: Validate backlog section completion, then squash+tag or identify gaps
argument-hint: <backlog-path> <section> <base-branch> [version] ["validation-prompt"]
project-agnostic: true
allowed-tools:
  - Read
  - Edit
  - Bash
  - Grep
  - Glob
  - Task
  - Write
  - AskUserQuestion
---

# Milestone Validation & Release

Validate section completion in backlog, then either release or identify gaps.

## Argument Parsing

Parse `$ARGUMENTS` into:

| Variable | Source | Required | Example |
|----------|--------|----------|---------|
| `BACKLOG_PATH` | 1st arg | Yes | `specs/backlog.md` |
| `SECTION` | 2nd arg | Yes | `1.2` |
| `BASE_BRANCH` | 3rd arg | Yes | `main` |
| `VERSION` | 4th arg (if not quoted) | No | `v0.1.1-alpha` |
| `VALIDATION_PROMPT` | Last quoted string `"..."` | No | `"Check NoteMeta, parser, tests"` |

**Parsing Rules:**
- If an argument starts and ends with `"`, treat as `VALIDATION_PROMPT`
- Version is optional; if 4th arg is quoted, there's no version

## Phase 1: Pre-Flight Checks

1. **Git state**: Must be clean (no uncommitted changes)
2. **Backlog exists**: File at `BACKLOG_PATH` must exist
3. **Section exists**: Section `SECTION` must be found in backlog
4. **Commits exist**: Must have commits since `BASE_BRANCH`

If any fail → STOP with specific error message.

## Phase 2: Extract Checklist

1. Read backlog file at `BACKLOG_PATH`
2. Find section matching `SECTION` (patterns: `#### 1.2`, `### Phase 1.2`, `## 1.2`)
3. Extract ALL checklist items until next section:
   - `- [ ]` = unchecked
   - `- [x]` = checked
4. Report: `Found X items (Y checked, Z unchecked)`

## Phase 3: Validate Implementation

### If `VALIDATION_PROMPT` provided:
Use it as explicit criteria. Spawn validation agent with prompt:
```
VALIDATE: {VALIDATION_PROMPT}

For each criterion, search codebase and report:
- Status: FOUND | MISSING
- Evidence: file:line references
- Notes: any issues
```

### If NO `VALIDATION_PROMPT`:
For each UNCHECKED item (`- [ ]`):

1. Parse item to identify expected:
   - Files/components (look for nouns)
   - Interfaces/functions (look for code terms)
   - Tests (if mentioned)

2. Search codebase:
   - Grep for key terms
   - Glob for expected file patterns
   - Check test directories

3. Classify:
   - **IMPLEMENTED**: Found despite unchecked
   - **MISSING**: No evidence found

## Phase 4: Decision Gate

### ✅ ALL COMPLETE (all items implemented or checked)

Display:
```
✅ Section {SECTION} COMPLETE

Validated Items:
- [x] Item 1 - evidence: file:line
- [x] Item 2 - evidence: file:line
...

Release Configuration:
- Base: {BASE_BRANCH}
- Version: {VERSION} (or "no tag")
- Commits to squash: N

Proceed with squash? (yes/no)
```

**On "yes":**
1. Update backlog: mark all items `[x]`, add ✅ to section header
2. Commit: `docs: mark {SECTION} as completed`
3. Create backup: `{branch}-backup/{YYYY}/{MM}/{DD}/001`
4. Soft reset to `BASE_BRANCH`
5. Create squashed commit with comprehensive message
6. If `VERSION`: create annotated tag

→ Proceed to **Phase 5: Push Confirmation**

### ❌ INCOMPLETE (missing items)

Display:
```
❌ Section {SECTION} INCOMPLETE

Missing:
1. {item} - {what's missing}
2. {item} - {what's missing}

Implemented but unchecked:
1. {item} - {evidence}

Options:
(A) Create /spec for missing items
(B) Abort - review manually
```

**On "A":** Output spec creation commands:
```
Missing items require specs:

/spec CREATE {item-1-title}
/spec CREATE {item-2-title}
```

**On "B":** STOP cleanly.

## Phase 5: Push Confirmation

After successful squash/tag, display:

```
## Release Prepared Locally

Commit: {sha} {message}
Branch: {branch}
Tag: {VERSION} (if created)
Backup: {backup-branch}

Push to origin?

Commands to execute:
  git push --force-with-lease origin {branch}
  git push origin {VERSION}  # if tag

Proceed with push? (yes/no)
```

**On "yes":**
1. Execute: `git push --force-with-lease origin {branch}`
2. If `VERSION`: Execute: `git push origin {VERSION}`
3. Report success with remote URLs

**On "no":**
Display manual commands and exit:
```
Skipped push. Run manually when ready:
  git push --force-with-lease origin {branch}
  git push origin {VERSION}
```

## Abort Conditions

| Condition | Action |
|-----------|--------|
| Backlog not found | STOP: "File not found: {path}" |
| Section not found | STOP: "Section {SECTION} not found. Available: [list]" |
| No commits to squash | STOP: "No commits between {BASE_BRANCH} and HEAD" |
| Git dirty | STOP: "Uncommitted changes. Commit or stash first." |
| User declines | STOP cleanly, no changes |
| Push fails | STOP: show error, suggest manual resolution |

## Usage Examples

```bash
# Full release with validation prompt
/milestone specs/backlog.md 1.2 main v0.1.1-alpha "NoteMeta extended, parser exists, 20 tests pass"

# Without custom prompt (auto-detect from checklist)
/milestone docs/roadmap.md 2.1 main v2.1.0

# Validate only, no version tag
/milestone CHANGELOG.md phase-3 develop

# Quoted prompt without version
/milestone specs/features.md 4.0 main "API endpoints implemented, auth working"
```
