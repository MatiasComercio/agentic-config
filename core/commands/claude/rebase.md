---
description: Rebase current branch onto target branch
argument-hint: <target>
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Skill
---

# Rebase Command

Rebase current branch onto target branch.

**Argument:**
- `$1` (required): Target branch to rebase onto (e.g., `main`, `develop`)

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
git branch --show-current
```

If branch is `main` or `master`: **STOP** - "Cannot rebase protected branch."

If current branch equals target: **STOP** - "Already on target branch '$1'."

### 4. Commits to Rebase
```bash
git rev-list --count $1..HEAD
```

If count is 0: **STOP** - "No commits to rebase. Branch is up to date with '$1'."

## Confirmation Gate

**STOP HERE** and show:

```
Rebase Summary:
- Branch: [current branch]
- Target: $1
- Commits to rebase: [count]
- Commit list:
  [git log --oneline $1..HEAD]

This will REWRITE HISTORY locally. Proceed? (yes/no)
```

**Wait for explicit "yes"**. Any other response = abort.

## Execution

### 1. Create Backup Branch
```bash
git branch backup/pre-rebase-$(date +%Y%m%d-%H%M%S) HEAD
```

### 2. Fetch Latest (if remote target)
```bash
git fetch origin $1 2>/dev/null || true
```

### 3. Perform Rebase
```bash
git rebase $1
```

If rebase conflicts:
1. Show conflicting files: `git status`
2. Provide resolution guidance
3. Wait for user to resolve manually
4. After resolution: `git rebase --continue`
5. If user wants to abort: `git rebase --abort`

## Verification

Show final state:
```bash
git log --oneline -10
```

## Result Summary

```
Rebase complete:
- [count] commits rebased onto $1
- Backup branch: backup/pre-rebase-[timestamp]
- LOCAL ONLY - not pushed
```
