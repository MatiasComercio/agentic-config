---
description: Squash all commits into one, then rebase onto target branch
argument-hint: <target>
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Skill
---

# Squash and Rebase Command

Squash all commits since fork point into a single commit, then rebase onto target branch.

**Argument:**
- `$1` (required): Target branch to rebase onto after squashing (e.g., `main`, `develop`)

## Context Awareness

**INVOKE** `git-rewrite-history` skill to gain context about safe history rewriting patterns.

## Pre-Flight Checks

### 1. Target Branch Validation
```bash
git show-ref --verify refs/heads/$1 2>/dev/null || git show-ref --verify refs/remotes/origin/$1 2>/dev/null
```

If target branch doesn't exist: **STOP** - "Target branch '$1' does not exist."

### 2. Working Tree Status
```bash
git status --porcelain
```

If output is NOT empty: **STOP** - "Working tree is dirty. Commit or stash changes first."

### 3. Current Branch
```bash
BRANCH=$(git branch --show-current)
```

If branch is `main` or `master`: **STOP** - "Cannot squash/rebase protected branch."

If current branch equals target: **STOP** - "Already on target branch '$1'."

### 4. Resolve Base Reference
```bash
BASE=$(git merge-base $1 HEAD)
```

### 5. Count Commits
```bash
git rev-list --count $BASE..HEAD
```

If count is 0: **STOP** - "No commits to squash. Branch is up to date with '$1'."

## Confirmation Gate

**STOP HERE** and show:

```
Squash and Rebase Summary:
- Branch: [current branch]
- Target: $1
- Base: [resolved base commit - short hash]
- Commits to squash: [count]
- Commit list:
  [git log --oneline $BASE..HEAD]

This will:
1. SQUASH [count] commits into 1
2. REBASE onto $1

This will REWRITE HISTORY locally. Proceed? (yes/no)
```

**Wait for explicit "yes"**. Any other response = abort.

## Execution

### 1. Create Backup Branch
```bash
git branch backup/pre-squash-rebase-$(date +%Y%m%d-%H%M%S) HEAD
```

### 2. Fetch Latest Target
```bash
git fetch origin $1 2>/dev/null || true
```

### 3. Soft Reset to Base
```bash
git reset --soft $BASE
```

### 4. Create Squashed Commit

Generate message from branch name:
```bash
git commit -m "$(cat <<'EOF'
feat: [branch-name-as-title]

Squashed [count] commits from [branch].
EOF
)"
```

### 5. Perform Rebase
```bash
git rebase $1
```

If rebase conflicts:
1. Show conflicting files: `git status`
2. Provide resolution guidance
3. Wait for user to resolve manually
4. After resolution: `git rebase --continue`
5. If user wants to abort: `git rebase --abort && git reset --hard backup/pre-squash-rebase-[timestamp]`

## Verification

Show final state:
```bash
git log --oneline -5
```

## Result Summary

```
Squash and Rebase complete:
- [count] commits -> 1 commit ([short hash])
- Rebased onto $1
- Backup branch: backup/pre-squash-rebase-[timestamp]
- LOCAL ONLY - not pushed
```
