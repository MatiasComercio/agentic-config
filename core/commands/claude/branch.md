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

2. **Create spec directory** (following project convention):
   ```
   specs/<YYYY>/<MM>/<branch-name>/
   ```
   - Use current year and month
   - Create `000-backlog.md` (empty file)

3. **Confirm**:
   ```
   - Branch: $ARGUMENTS
   - Spec dir: specs/<YYYY>/<MM>/<branch-name>/
   - Backlog: 000-backlog.md (empty)
   ```
