# RESEARCH Summary: agentic-config v1.1.1

## Overview

Research stage completed for spec `001-agentic-config-v1.1.1.md`. This document validates the CREATE stage analysis and provides additional findings.

---

## Findings

### 1. AGENTS.md Templates

**Current State:**
- 6 templates: typescript (33 lines), python-uv/poetry/pip (32 lines), rust (32 lines), generic (28 lines)
- Sections: Environment & Tooling, Style & Conventions, Core Principles, Workflow, Git Rules, CUSTOMIZE marker

**Gaps vs Reference Template:**
| Missing Section | Impact |
|-----------------|--------|
| /spec Workflow | No reference to `agents/spec/{STAGE}.md` |
| Git Workflow (full) | Missing base branch, git status path handling |
| Critical Rules | Missing gitignore enforcement, efficiency principle |
| ADR Reference | Not mentioned at all |
| "DO NOT OVERCOMPLICATE/OVERSIMPLIFY" | Not in Core Principles |
| PROJECT_AGENTS.md reference | Pattern doesn't exist |

**Line Count Increase:** 32-33 lines -> ~55 lines (estimated)

---

### 2. /adr Command

**Source:** `/Users/matias/projects/ziot/praxi/.claude/commands/adr.md`

**Current Issues:**
- Hardcoded path: `/Users/matias/projects/ziot/praxi/adrs/000-index.md` (line 22)
- No auto-creation of `adrs/` directory
- No auto-creation of `000-index.md`

**Required Changes:**
- Replace hardcoded path with `$(pwd)/adrs/`
- Add directory creation: `mkdir -p adrs/`
- Add index template creation if missing

---

### 3. ts-bun Template

**Current State:** Does not exist

**Detection Logic Needed:** `bun.lockb` file presence
- Position in priority: BEFORE generic `package.json` check (after typescript)

**Template Differences from typescript:**
| Item | typescript | ts-bun |
|------|------------|--------|
| Package Manager | pnpm | bun |
| Install | pnpm install | bun install |
| Run | pnpm run | bun run |
| Exec | pnpx | bunx |
| Lock file | pnpm-lock.yaml | bun.lockb |

---

### 4. setup-config.sh Analysis

**Current Features (266 lines):**
- Auto-detect project type
- Create core symlinks (agents/, spec workflows)
- Install templates (config.yml, AGENTS.md)
- Install AI tool configs (Claude, Gemini, Codex)
- Install agentic management agents
- Optional extras installation (--extras flag)
- Backup existing files
- Register installation

**Missing Features:**
- `.gitignore` creation (no `templates/shared/` exists)
- `git init` execution
- PROJECT_AGENTS.md support

**Insert Points:**
- After symlink creation, before summary (lines 252-259)

---

### 5. update-config.sh Analysis

**Current Features (221 lines):**
- Version comparison
- Template change detection (first 20 lines)
- Force update option
- Extras installation (--extras flag)
- Version tracking update

**Missing Features:**
- Symlink diff detection (add/remove new symlinks)
- PROJECT_AGENTS.md migration
- Orphaned symlink cleanup

**Current Extras Lists:**
```bash
# Commands
orc spawn squash squash_commit pull_request gh_pr_review

# Skills
agent-orchestrator-manager single-file-uv-scripter command-writer skill-writer git-find-fork
```

**Note:** `adr` command NOT in extras list yet

---

### 6. detect-project-type.sh Analysis

**Current Detection Order:**
1. TypeScript: `package.json` with typescript/@types
2. Python Poetry: `pyproject.toml` with `[tool.poetry]`
3. Python UV: `uv.lock` OR `pyproject.toml` with `[tool.uv]`
4. Python pip: `requirements.txt`, `setup.py`, `setup.cfg`
5. Rust: `Cargo.toml`
6. Go: `go.mod`
7. Generic: fallback

**ts-bun Detection:** NOT IMPLEMENTED
- Should check for `bun.lockb` BEFORE generic TypeScript check
- Insert after line 13 (before TypeScript echo)

---

### 7. Core Agents Analysis

**agentic-setup.md:**
- Documents --extras flag
- Lists available commands and skills
- Missing: .gitignore creation, git init documentation

**agentic-update.md:**
- Documents --extras flag
- Shows diff workflow
- Missing: PROJECT_AGENTS.md migration, symlink diff

**agentic-migrate.md:**
- Documents customization preservation
- Missing: PROJECT_AGENTS.md handling

---

### 8. Shared Templates

**Current State:** `templates/shared/` directory does NOT exist

**Required for v1.1.1:**
- `.gitignore.template` - Default gitignore for new projects

---

## Validation of CREATE Stage

| Requirement | CREATE Stage Accurate | Notes |
|-------------|----------------------|-------|
| AGENTS.md simplification | Yes | Gap analysis correct |
| /adr command import | Yes | Path hardcoding identified |
| ts-bun template | Yes | bun.lockb detection correct |
| setup .gitignore + git init | Yes | Insert point identified |
| update symlink diff | Yes | Logic outlined |
| PROJECT_AGENTS.md pattern | Yes | Migration strategy defined |
| VERSION bump | Yes | 1.1.0 -> 1.1.1 |

---

## Additional Findings

### 1. Missing /adr in Extras List
The CREATE stage correctly identifies `/adr` command creation but doesn't mention adding it to:
- `setup-config.sh` extras list (line 228)
- `update-config.sh` extras list (line 187)

### 2. Open Questions Resolution
| Question | Recommendation | Rationale |
|----------|----------------|-----------|
| PROJECT_AGENTS.md auto-create? | Only on migration | Avoid empty file clutter |
| Support both patterns? | No, migrate to single | Clarity > flexibility |

### 3. Template Processing
`lib/template-processor.sh` uses simple copy (no variable substitution). PROJECT_AGENTS.md reference in AGENTS.md template will be static text.

---

## Files Summary

### Files to Create (4)
- `templates/ts-bun/AGENTS.md.template`
- `templates/ts-bun/.agent/config.yml.template`
- `core/commands/claude/adr.md`
- `templates/shared/.gitignore.template`

### Files to Edit (12)
- `VERSION`
- `templates/typescript/AGENTS.md.template`
- `templates/python-uv/AGENTS.md.template`
- `templates/python-poetry/AGENTS.md.template`
- `templates/python-pip/AGENTS.md.template`
- `templates/rust/AGENTS.md.template`
- `templates/generic/AGENTS.md.template`
- `scripts/setup-config.sh`
- `scripts/update-config.sh`
- `scripts/lib/detect-project-type.sh`
- `core/agents/agentic-setup.md`
- `core/agents/agentic-update.md`

---

## Risk Assessment Validation

| Risk | Mitigation Status |
|------|-------------------|
| Breaking existing setups | Backup in migrate-existing.sh |
| Template changes break workflows | Need test matrix |
| PROJECT_AGENTS.md confusion | Documentation required |

---

## Recommendations

1. **Test matrix needed:** Fresh setup + update path for each template type
2. **Add /adr to extras lists** in both setup and update scripts
3. **CHANGELOG.md update** for v1.1.1 with all changes
4. **Consider:** Add `bun add` vs `bun install` clarification in ts-bun template
