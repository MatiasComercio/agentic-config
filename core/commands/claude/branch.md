---
description: Create new branch with spec directory structure
argument-hint: <branch-name>
allowed-tools:
  - Bash
  - Write
---

# Create Branch with Spec Directory

Create a new git branch and its corresponding spec directory.

## Pre-Flight Checks

1. **Verify clean git state**:
   - If dirty: STOP and list uncommitted changes

2. **Validate branch name**:
   - Must be provided as argument
   - If empty: STOP with "Branch name required"

## Execution

1. **Create and checkout branch**:
   ```bash
   git checkout -b $ARGUMENTS
   ```

2. **Create spec directory relative to CWD** (NOT repo root):
   ```bash
   # CRITICAL: Use current directory, not repo root
   SPEC_DIR="./specs/$(date +%Y)/$(date +%m)/$ARGUMENTS"
   mkdir -p "$SPEC_DIR"
   touch "$SPEC_DIR/000-backlog.md"
   ```
   - Path: `specs/<YYYY>/<MM>/<branch-name>/`
   - Creates `000-backlog.md` (empty file)

3. **Commit spec directory**:
   ```bash
   git add "$SPEC_DIR"
   git commit -m "chore(spec): create spec directory for $ARGUMENTS"
   ```
   - **CRITICAL**: Must commit BEFORE creating worktree, otherwise spec files are lost

4. **Confirm**:
   ```
   - Branch: $ARGUMENTS
   - Spec dir: specs/<YYYY>/<MM>/<branch-name>/
   - Backlog: 000-backlog.md (committed)
   ```
