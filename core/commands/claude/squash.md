---
description: Squash all commits since base into single commit, optionally re-tag
argument-hint: [base-ref] [tag]
project-agnostic: true
allowed-tools:
  - Bash
  - Read
---

# Squash Command

Squash all commits since base reference into a single commit.

**Arguments:**
- `$1` (optional): Base reference - branch name or commit hash (default: merge-base with main)
- `$2` (optional): Tag to delete and recreate on squashed commit

## Pre-Flight Checks

### 1. Working Tree Status
```bash
git status --porcelain
```

If output is NOT empty: **STOP** - "Working tree is dirty. Commit or stash changes first."

### 2. Current Branch
```bash
git branch --show-current
```

If branch is `main` or `master`: **STOP** - "Cannot squash on protected branch."

### 3. Resolve Base Reference

**If `$1` provided:**
- Check if it's a branch: `git show-ref --verify refs/heads/$1 2>/dev/null`
- If branch exists: resolve via `git merge-base $1 HEAD`
- Otherwise treat as commit hash and use directly

**If `$1` NOT provided:**
- Default: `git merge-base main HEAD`

### 4. Count Commits
```bash
git rev-list --count <base>..HEAD
```

If count is 0: **STOP** - "No commits to squash."

### 5. Tag Check (if `$2` provided)
```bash
git tag -l "$2"
```

If tag doesn't exist: **WARN** - "Tag '$2' doesn't exist. Will create new tag."

## Confirmation Gate

**STOP HERE** and show:

```
Squash Summary:
- Branch: [current branch]
- Base: [resolved base commit - short hash]
- Commits to squash: [count]
- Tag: [tag name or "none"]
- Commit list:
  [git log --oneline <base>..HEAD]

This will REWRITE HISTORY locally. Proceed? (yes/no)
```

**Wait for explicit "yes"**. Any other response = abort.

## Execution

### 1. Delete Tag (if provided and exists)
```bash
git tag -d $2
```

### 2. Soft Reset
```bash
git reset --soft <base>
```

### 3. Create Squashed Commit
Generate message from branch name (convert kebab-case to readable):
```bash
git commit -m "$(cat <<'EOF'
feat: [branch-name-as-title]

Squashed [count] commits from [branch].
EOF
)"
```

### 4. Recreate Tag (if provided)
```bash
git tag $2
```

## Verification

Show final state:
```bash
git log --oneline <base>..HEAD
```

If tagged:
```bash
git tag -l --points-at HEAD
```

## Result Summary

```
Squash complete:
- [count] commits -> 1 commit ([short hash])
- Tag: [tag or "none"]
- LOCAL ONLY - not pushed
```
