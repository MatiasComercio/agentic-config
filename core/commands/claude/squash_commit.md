---
description: Generate semantic commit message for squashed HEAD commit
argument-hint: [target]
project-agnostic: true
allowed-tools:
  - Bash
  - Read
---

# Semantic Commit Message Generator

Generates and applies a semantic versioning commit message to an already-squashed HEAD commit.

**CRITICAL**: This command assumes squashing has ALREADY been performed. It only generates and amends the commit message.

## Usage
```
/squash_commit [target]
```

**Arguments**:
- `target`: Optional commit hash or branch name. Defaults to `origin/main`.

**Examples**:
```
/squash_commit                    # Uses origin/main (default)
/squash_commit develop           # Use origin/develop as base
/squash_commit abc123f           # Use specific commit hash as base
/squash_commit origin/feature    # Use specific remote branch
```

---

## Workflow Steps

### Step 1: Pre-Flight Validation

#### 1.1 Safety Checks
```bash
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Check if on protected branch
if [ "$BRANCH" = "main" ]; then
  echo "ERROR: Cannot amend commits on protected branch: $BRANCH"
  exit 1
fi

# Check for uncommitted changes
if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "ERROR: Uncommitted changes detected. Commit or stash changes first."
  git -C "$ROOT" status --short
  exit 1
fi

# Verify there is at least one commit
if ! git -C "$ROOT" rev-parse HEAD >/dev/null 2>&1; then
  echo "ERROR: No commits found in current branch"
  exit 1
fi
```

#### 1.2 Fetch and Resolve Target
```bash
# Fetch latest from origin (always fetch main for default case)
echo "Fetching latest from origin..."
git -C "$ROOT" fetch origin main 2>/dev/null || true

# Resolve target: use argument or default to origin/main
if [ -n "$1" ]; then
  TARGET="$1"
  # If target looks like a branch name (no origin/ prefix, not a hash), fetch it
  if ! echo "$TARGET" | grep -qE '^[0-9a-f]{7,40}$' && ! echo "$TARGET" | grep -q '/'; then
    echo "Fetching origin/$TARGET..."
    git -C "$ROOT" fetch origin "$TARGET" 2>/dev/null || true
  fi
  echo "Target: $TARGET (user provided)"
else
  TARGET="origin/main"
  echo "Target: origin/main (default)"
fi
echo ""

# Resolve target to commit hash (supports branches, remote branches, and commit hashes)
TARGET_REF=""
if git -C "$ROOT" rev-parse --verify "$TARGET" >/dev/null 2>&1; then
  TARGET_REF="$TARGET"
elif git -C "$ROOT" rev-parse --verify "origin/$TARGET" >/dev/null 2>&1; then
  TARGET_REF="origin/$TARGET"
else
  echo "ERROR: Cannot resolve target '$TARGET'"
  echo "Provide a valid commit hash, branch name, or remote branch (e.g., origin/main)"
  echo ""
  echo "Available remote branches:"
  git -C "$ROOT" branch -r | grep -v HEAD
  exit 1
fi

TARGET_HASH=$(git -C "$ROOT" rev-parse "$TARGET_REF")
echo "Resolved target: $TARGET_REF ($TARGET_HASH)"
```

---

### Step 2: Context Gathering

#### 2.1 Analyze Current HEAD Commit
```bash
echo "Current HEAD commit:"
echo "===================="
git -C "$ROOT" log -1 --format="Title: %s%nBody:%n%b"
echo ""

# Extract current commit components
CURRENT_TITLE=$(git -C "$ROOT" log -1 --format='%s')
CURRENT_BODY=$(git -C "$ROOT" log -1 --format='%b')

echo "Analyzing existing commit message..."
# Check if already follows conventional commits format
if echo "$CURRENT_TITLE" | grep -Eq '^[a-z]+(\([a-z/]+\))?: '; then
  echo "Note: Current commit already follows conventional format"
fi
echo ""
```

#### 2.2 Analyze Changes vs Base Branch
```bash
echo "Files changed vs $TARGET_REF:"
git -C "$ROOT" diff --stat "$TARGET_REF..HEAD"
echo ""

# Store changed files for scope derivation
CHANGED_FILES=$(git -C "$ROOT" diff --name-only "$TARGET_REF..HEAD")
FILE_STATS=$(git -C "$ROOT" diff --stat "$TARGET_REF..HEAD")

# Count total changes
COMMITS_AHEAD=$(git -C "$ROOT" rev-list --count "$TARGET_REF..HEAD")
if [ "$COMMITS_AHEAD" -eq 0 ]; then
  echo "WARNING: No commits ahead of $TARGET_REF. Branch may be up-to-date."
fi
```

#### 2.3 Read CHANGELOG for Context (if exists)
```bash
# Check for CHANGELOG.md
CWD_FROM_ROOT=${PWD#$ROOT/}
CHANGELOG_PATH="$CWD_FROM_ROOT/CHANGELOG.md"

if git -C "$ROOT" ls-files "$CHANGELOG_PATH" | grep -q .; then
  echo "Reading CHANGELOG for version context..."
  git -C "$ROOT" show "HEAD:$CHANGELOG_PATH" | head -50
  echo ""
fi
```

---

### Step 3: Semantic Commit Message Generation

**INSTRUCTION**: Generate a semantic commit message following Conventional Commits extended rules.

#### 3.1 Analyze Existing Message
- Parse `CURRENT_TITLE` and `CURRENT_BODY`
- Extract any existing type/scope if present
- Identify intent from message content
- Use as baseline for semantic message generation

#### 3.2 Commit Message Structure
```
<type>(<scope>): <short description>

<body - detailed changes>

<footer - breaking changes, refs, etc>
```

#### 3.3 Type Classification

Analyze current commit message and modified files to determine primary type:

| Type | Description | Version Impact |
|------|-------------|----------------|
| `feat` | New feature | MINOR bump |
| `fix` | Bug fix | PATCH bump |
| `docs` | Documentation only | None |
| `style` | Formatting, no code change | None |
| `refactor` | Code restructuring, no behavior change | None |
| `perf` | Performance improvement | PATCH bump |
| `test` | Adding/fixing tests | None |
| `chore` | Build process, tooling | None |
| `build` | Build system changes | None |
| `ci` | CI configuration | None |

#### 3.4 Scope Derivation

Extract scope from modified file paths (`CHANGED_FILES`):

Derive scope from modified file paths. Use most specific common path segment. Combine with `/` for nested scopes (e.g., `api/auth`, `ui/dashboard`). Omit if changes span unrelated areas.

**Scope Rules**:
- Use most specific common path segment
- Combine with `/` for nested scopes
- Omit if changes span too many unrelated areas
- Consider existing scope in `CURRENT_TITLE` if applicable

#### 3.5 Breaking Changes Detection

Search current commit message (`CURRENT_TITLE` + `CURRENT_BODY`) for:
- `BREAKING CHANGE:` or `BREAKING-CHANGE:` in body/footer
- Significant API changes mentioned
- Database schema modifications
- Major behavior changes

If found: Add exclamation mark after type, before colon (example: feat(api)!: description)

#### 3.6 Body Construction

**Include**:
- High-level summary (1-3 sentences)
- Key changes grouped by category
- File paths for critical changes
- Technical specifics (function names, table names, etc.)
- Preserve important details from `CURRENT_BODY` if relevant

**Format**:
```
This <type> <summary of what was done>.

Key changes:
- Category 1: specific change (affected file/component)
- Category 2: another change (details)

Modified files: N
```

#### 3.7 Footer Construction

**Include if applicable**:
- `BREAKING CHANGE: <description>` (if breaking changes exist)
- `Fixes: #<issue-number>` or `Closes: #<issue-number>` (if parseable from commit message)
- `Refs: specs/path/to/spec.md` (if spec files modified, extracted from `CHANGED_FILES`)
- `Generated with [Claude Code](https://claude.ai/code)`
- `Co-Authored-By: Claude <noreply@anthropic.com>`

---

### Step 4: Generate Commit Message Preview

**INSTRUCTION**: Use gathered context to generate the semantic commit message.

**Process**:
1. Analyze existing commit message (`CURRENT_TITLE` + `CURRENT_BODY`)
2. Extract any existing conventional commit components
3. Classify primary type (feat, fix, refactor, etc.) from changes
4. Derive scope from modified file paths (`CHANGED_FILES`)
5. Detect breaking changes from message content
6. Construct body with key changes
7. Add footer with references (specs, attribution)

**Output Format**:
```
==========================================
CURRENT COMMIT MESSAGE:
==========================================
[Current HEAD commit message]
==========================================

==========================================
PROPOSED SEMANTIC MESSAGE:
==========================================
[Generated semantic commit message]
==========================================
```

---

### Step 5: User Confirmation

**INSTRUCTION**: Show both current and proposed commit messages, then ask for confirmation.

**Ask user**:
1. "Does this semantic commit message accurately reflect the changes?"
2. "Would you like to amend the commit with this message? (yes/no/edit)"

**Options**:
- `yes`: Proceed with amending the commit
- `no`: Abort without changes
- `edit`: Allow user to modify the commit message before amending

---

### Step 6: Amend Commit

**CRITICAL**: This step modifies git history. Ensure user confirmed.

```bash
echo "Amending HEAD commit with semantic message..."
echo ""

# Store the semantic commit message
COMMIT_MSG="[GENERATED_COMMIT_MESSAGE_HERE]"

# Amend the current HEAD commit
git -C "$ROOT" commit --amend -m "$COMMIT_MSG"

echo "Commit amended successfully."
```

**Safety Note**:
- Only amends HEAD commit (no rebase involved)
- Safer than squash rebase as it modifies only message, not history structure
- Still requires force-push if commit was already pushed

---

### Step 7: Verification & Next Steps

#### 7.1 Verify Amendment Success
```bash
echo "Verifying amended commit..."
echo ""

# Show final commit
echo "Amended commit:"
git -C "$ROOT" log --oneline -1
echo ""

# Show commit details
git -C "$ROOT" show --stat HEAD
```

#### 7.2 Provide Next Steps
```bash
echo "=========================================="
echo "COMMIT AMENDED"
echo "=========================================="
echo ""
echo "Branch: $BRANCH"
echo "Target base: $TARGET_REF"
echo ""
echo "Next steps:"
echo "  1. Review commit: git show HEAD"
echo "  2. Push (force required if already pushed): git push --force-with-lease origin $BRANCH"
echo "  3. Create PR if ready"
echo ""
echo "IMPORTANT: If commit was already pushed, force-push is required."
echo "Only force-push to feature branches, never to $TARGET_REF."
echo "=========================================="
```

---

## Safety Checks Summary

- Verify not on protected branch (main)
- Check for uncommitted changes
- Verify HEAD commit exists
- Confirm target branch exists
- Show current vs proposed message preview
- Require user confirmation
- Warn about force-push requirement if needed

---

## Edge Cases

### No Commits Ahead of Target
If branch is up-to-date with target:
- WARNING: "No commits ahead of $TARGET_REF. Branch may be up-to-date."
- Proceed anyway (user may want to improve existing commit message)

### Already Semantic Format
If current commit already follows conventional commits:
- Note: "Current commit already follows conventional format"
- Still generate improved version based on file analysis

### Invalid Target Reference
If target cannot be resolved:
- ERROR: "Cannot resolve target '<target>'"
- List available remote branches
- Suggest valid formats: commit hash, branch name, or remote ref

---

## Design Decisions

1. **Post-Squash Operation**
   - Assumes squash has ALREADY been performed before command execution
   - Only generates and amends commit message
   - Simpler workflow: no rebase, no conflict resolution
   - Safer: modifies only message, not commit structure

2. **Message-Only Amendment**
   - Uses `git commit --amend` (not rebase)
   - Preserves all file changes exactly
   - Only updates commit message metadata
   - Minimal risk compared to history rewriting

3. **Default Target: origin/main**
   - Defaults to `origin/main` for simplicity and predictability
   - Accepts commit hash, branch name, or full remote ref (e.g., `origin/develop`)
   - Always fetches `main` first, then fetches specified branch if different
   - Resolves target to commit hash for consistent diff behavior

4. **Semantic Commit Analysis**
   - Analyzes existing commit message as baseline
   - Respects existing conventional format if present
   - Uses file path analysis as primary signal for type/scope
   - Incorporate CHANGELOG context for version-aware messages

5. **Safety-First Approach**
   - Multiple validation checkpoints
   - Clear current vs proposed message preview
   - Explicit warnings about force-push if already pushed
   - No destructive operations (only message amendment)

6. **Context-Aware Scope**
   - Derive scope from modified files vs target branch
   - Keep scope concise but meaningful
   - Preserve existing scope if appropriate
