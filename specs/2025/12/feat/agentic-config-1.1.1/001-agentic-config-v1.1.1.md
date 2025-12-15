# 001 - agentic-config v1.1.1

## Human Section (IMMUTABLE)

### Context
Multi-feature update for agentic-config v1.1.1 addressing template simplification, new commands, improved setup/update workflows, and better customization handling.

### Requirements
1. **UPDATE AGENTS.MD templates** - Simplify using reference template. Efficiency principle: NOT OVERSIMPLIFYING, NOT OVERCOMPLICATING.
2. **IMPORT /adr command** - Port from external source, ensure project-agnostic.
3. **ADD ts-bun version** - Alternative to pnpm for TypeScript setup.
4. **UPDATE /agentic-setup** - Add .gitignore file to project root AND run git init.
5. **UPDATE /agentic-update** - Check for newest core updates, ADD/REMOVE symlinks as needed.
6. **UPDATE customization handling**:
   - Default = copied template (AGENTS.md)
   - Define PROJECT_AGENTS.md for project-specific instructions
   - Add instruction in AGENTS.md: "READ @PROJECT_AGENTS.md for project-specific instructions - CRITICAL COMPLIANCE"
   - MIGRATE existing projects to this structure on /agentic-update
   - Handle overridden AGENTS.md as PROJECT_AGENTS.md
7. **BUMP version** to 1.1.1

### Reference Template (AGENTS.md simplification)
```markdown
# Project Guidelines

## Environment & Tooling
- **Package Manager:** bun
- **Type Checking:** tsc --noEmit (never tsc alone)
- **Linting:** eslint <path> [--fix]
- **Build:** Only when explicitly requested

## Style & Conventions
- TypeScript strict mode, functional components, explicit types (no any)
- After edits: eslint --fix <file> && tsc --noEmit

## Core Principles
- Verify over assume
- Failures first (lead with errors)
- Always re-raise (never swallow exceptions)
- DO NOT OVERCOMPLICATE
- DO NOT OVERSIMPLIFY

## Critical Rules
- NEVER amend commits unless user says 'amend commit'
- NEVER commit files in gitignored directories unless explicitly requested - DO NOT use git add -f to bypass .gitignore
- Minimal changes; avoid ambiguity; no placeholders
- Keep prompts concise; log costs
- EFFICIENCY in application performance and user experience - REFLECT this in EVERY implementation

## /spec Workflow
Reference agents/spec/{STAGE}.md for detailed instructions.
- Default path: specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md
- Modify AI Section only; never touch Human Section
- Commit after each stage: spec(<NNN>): <STAGE> - <title>

## Git Workflow
- Base branch: main (not master)
- git status returns CWD-relative paths - use those exact paths with git add
- Never commit to main; never amend unless 'amend commit' explicitly requested
- One stage = one commit: spec(<NNN>): <STAGE> - <title>

## Architecture Decision Records
- READ adrs/000-index.md for critical decisions before implementing
- ADRs contain binding constraints (licensing, architecture patterns)
- Create new ADRs via /adr command
```

### Success Criteria ✅
- [x] All AGENTS.md templates follow simplified structure
- [x] /adr command is project-agnostic and functional
- [x] ts-bun template works alongside typescript template
- [x] /agentic-setup creates .gitignore and runs git init
- [x] /agentic-update detects and adds/removes symlinks
- [x] PROJECT_AGENTS.md pattern implemented
- [x] Migration handles existing customizations
- [x] VERSION file shows 1.1.1

---

## AI Section

### Stage: CREATE

### Analysis

#### Current State
- **VERSION**: 1.1.0
- **Templates**: 6 types (typescript, python-poetry, python-pip, python-uv, rust, generic)
- **AGENTS.md templates**: ~33 lines, sections: Environment & Tooling, Style & Conventions, Core Principles, Workflow, Git Rules, CUSTOMIZE marker

#### Gaps Identified
1. **AGENTS.md templates lack**:
   - /spec workflow reference section
   - Git workflow details (base branch, path handling)
   - ADR reference section
   - Critical rules section (gitignore enforcement, efficiency principle)
   - "DO NOT OVERCOMPLICATE/OVERSIMPLIFY" principle

2. **Missing /adr command** - Exists externally but hardcoded to source path

3. **Missing ts-bun template** - Only pnpm exists for TypeScript

4. **Setup lacks**:
   - .gitignore file creation
   - git init execution

5. **Update lacks**:
   - Symlink diff detection (add/remove)
   - PROJECT_AGENTS.md migration

6. **No PROJECT_AGENTS.md pattern** - All customization in AGENTS.md directly

### Implementation Plan

#### Files to Create
| File | Purpose |
|------|---------|
| `templates/ts-bun/AGENTS.md.template` | Bun variant for TypeScript |
| `templates/ts-bun/.agent/config.yml.template` | Bun config template |
| `core/commands/claude/adr.md` | Project-agnostic ADR command |
| `templates/shared/.gitignore.template` | Default gitignore for setup |

#### Files to Edit
| File | Change |
|------|--------|
| `VERSION` | 1.1.0 -> 1.1.1 |
| `templates/typescript/AGENTS.md.template` | Simplify per reference |
| `templates/python-uv/AGENTS.md.template` | Simplify per reference |
| `templates/python-poetry/AGENTS.md.template` | Simplify per reference |
| `templates/python-pip/AGENTS.md.template` | Simplify per reference |
| `templates/rust/AGENTS.md.template` | Simplify per reference |
| `templates/generic/AGENTS.md.template` | Simplify per reference |
| `scripts/setup-config.sh` | Add .gitignore, git init, PROJECT_AGENTS.md support |
| `scripts/update-config.sh` | Add symlink diff, PROJECT_AGENTS.md migration |
| `scripts/lib/detect-project-type.sh` | Add ts-bun detection |
| `core/agents/agentic-setup.md` | Document new behaviors |
| `core/agents/agentic-update.md` | Document migration |
| `core/agents/agentic-migrate.md` | Handle PROJECT_AGENTS.md |

### Detailed Design

#### 1. AGENTS.md Template Structure (Simplified)

All templates will follow this pattern (language-specific tooling varies):

```markdown
# Project Guidelines

## Environment & Tooling
- **Package Manager:** <tool>
- **Type Checking:** <command>
- **Linting:** <command>
- **Build:** Only when explicitly requested

## Style & Conventions
- <language-specific conventions>
- After edits: <lint + type check command>

## Core Principles
- Verify over assume
- Failures first (lead with errors)
- Always re-raise (never swallow exceptions)
- DO NOT OVERCOMPLICATE
- DO NOT OVERSIMPLIFY

## Critical Rules
- NEVER amend commits unless user says 'amend commit'
- NEVER commit files in gitignored directories unless explicitly requested
- Minimal changes; avoid ambiguity; no placeholders
- EFFICIENCY in application performance and user experience

## /spec Workflow
Reference agents/spec/{STAGE}.md for detailed instructions.
- Default path: specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md
- Modify AI Section only; never touch Human Section
- Commit after each stage: spec(<NNN>): <STAGE> - <title>

## Git Workflow
- Base branch: main (not master)
- git status returns CWD-relative paths - use those exact paths with git add
- Never commit to main; never amend unless 'amend commit' explicitly requested
- One stage = one commit: spec(<NNN>): <STAGE> - <title>

## Project-Specific Instructions
READ @PROJECT_AGENTS.md for project-specific instructions - CRITICAL COMPLIANCE

<!-- PROJECT_AGENTS.md contains project-specific guidelines that override defaults -->
```

#### 2. PROJECT_AGENTS.md Pattern

**Rationale**: Separates versioned template from project customizations.

**Structure**:
- `AGENTS.md` = Template (symlinked or copied, updates with agentic-config)
- `PROJECT_AGENTS.md` = Project-specific (never touched by updates)

**Migration Logic** (in update-config.sh):
```bash
if AGENTS.md modified from template:
  1. Extract content below "CUSTOMIZE BELOW THIS LINE"
  2. Create PROJECT_AGENTS.md with extracted content
  3. Replace AGENTS.md with fresh template
  4. Log migration
```

#### 3. /adr Command (Project-Agnostic)

Changes from source version:
- Replace hardcoded path with `$(pwd)/adrs/`
- Auto-create `adrs/` directory if missing
- Auto-create `000-index.md` if missing with template

#### 4. ts-bun Template

Variant of typescript template:
- Package manager: `bun` instead of `pnpm`
- Commands: `bun run`, `bun install`, `bunx`
- Detection: `bun.lockb` file presence

#### 5. Setup Script Updates

Add to `setup-config.sh`:
```bash
# After creating symlinks, before summary:

# Create .gitignore if not exists
if [[ ! -f "$TARGET_PATH/.gitignore" ]]; then
  cp "$REPO_ROOT/templates/shared/.gitignore.template" "$TARGET_PATH/.gitignore"
fi

# Initialize git if not a repo
if [[ ! -d "$TARGET_PATH/.git" ]]; then
  git init "$TARGET_PATH"
fi
```

#### 6. Update Script Updates

Add symlink management:
```bash
# Compare installed symlinks vs available
AVAILABLE_CMDS=(orc spawn squash squash_commit pull_request gh_pr_review adr)
AVAILABLE_SKILLS=(agent-orchestrator-manager single-file-uv-scripter command-writer skill-writer git-find-fork)

# Add missing
for cmd in "${AVAILABLE_CMDS[@]}"; do
  if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" && ! -L "$TARGET/.claude/commands/$cmd.md" ]]; then
    # Offer to add
  fi
done

# Remove orphaned (symlinks pointing to non-existent files)
for link in "$TARGET/.claude/commands/"*.md; do
  if [[ -L "$link" && ! -e "$link" ]]; then
    rm "$link"
    echo "Removed orphaned symlink: $link"
  fi
done
```

Add PROJECT_AGENTS.md migration:
```bash
# Check if AGENTS.md was customized
if has_customizations "$TARGET/AGENTS.md"; then
  extract_customizations "$TARGET/AGENTS.md" > "$TARGET/PROJECT_AGENTS.md"
  cp "$TEMPLATE_DIR/AGENTS.md.template" "$TARGET/AGENTS.md"
  echo "Migrated customizations to PROJECT_AGENTS.md"
fi
```

### Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing setups | High | Backup before migration, dry-run option |
| Template changes break workflows | Medium | Keep essential sections, test all templates |
| PROJECT_AGENTS.md confusion | Low | Clear documentation, migration message |

### Testing Strategy

1. **Unit tests**:
   - Template detection (ts-bun vs typescript)
   - Customization extraction
   - Symlink management

2. **Integration tests**:
   - Fresh setup with each template type
   - Update from 1.1.0 to 1.1.1
   - Migration with existing customizations

3. **Manual validation**:
   - /spec workflow still works
   - /adr creates proper ADRs
   - PROJECT_AGENTS.md respected

### Dependencies
- `jq` for JSON manipulation (existing)
- `git` for init (standard)
- No new dependencies

### Open Questions
1. Should PROJECT_AGENTS.md be auto-created empty or only on migration?
   - **Recommendation**: Only on migration or explicit customization
2. Should we support both AGENTS.md customization AND PROJECT_AGENTS.md?
   - **Recommendation**: No, migrate to single pattern for clarity

---

### Stage: RESEARCH

#### Validation Summary

All CREATE stage analysis validated as accurate. Additional findings documented below.

#### Codebase Verification

| Item | Verified | Details |
|------|----------|---------|
| VERSION file | 1.1.0 | Correct |
| Template count | 6 | typescript, python-uv/poetry/pip, rust, generic |
| AGENTS.md line counts | 28-33 | generic (28), others (32-33) |
| /adr command | Hardcoded | Line 22: hardcoded source path |
| ts-bun template | Missing | Does not exist |
| shared/ directory | Missing | Does not exist |
| detect-project-type.sh | No bun detection | Needs `bun.lockb` check |

#### Script Analysis

**setup-config.sh (266 lines):**
- Has --extras flag (lines 79-83)
- Extras list: orc, spawn, squash, squash_commit, pull_request, gh_pr_review
- Missing: .gitignore creation, git init, /adr in extras

**update-config.sh (221 lines):**
- Has --extras flag
- Template change detection compares first 20 lines
- Missing: symlink diff, orphaned cleanup, PROJECT_AGENTS.md migration

**detect-project-type.sh (60 lines):**
- Detection order: TS > Poetry > UV > pip > Rust > Go > generic
- Insert point for bun: After line 13 (before typescript echo)

#### Additional Findings

1. **Missing /adr in extras lists**
   - `setup-config.sh` line 228: needs `adr` added
   - `update-config.sh` line 187: needs `adr` added

2. **Agent documentation gaps**
   - `agentic-setup.md`: missing .gitignore, git init docs
   - `agentic-update.md`: missing PROJECT_AGENTS.md migration docs
   - `agentic-migrate.md`: missing PROJECT_AGENTS.md handling

3. **Template processor** uses simple copy (no variable substitution)
   - PROJECT_AGENTS.md reference in AGENTS.md will be static text

4. **CHANGELOG.md** needs v1.1.1 entry (currently ends at 1.1.0)

#### Open Questions Resolved

| Question | Decision | Rationale |
|----------|----------|-----------|
| PROJECT_AGENTS.md auto-create? | Only on migration | Avoid empty file clutter |
| Support both patterns? | No | Clarity > flexibility |

#### Summary Output

Full research summary: `outputs/orc/2025/12/15/172534-e1f7dc1e/02-spec-research/summary.md`

---

### Stage: PLAN

#### Implementation Phases

| Phase | Description | Estimate | Dependencies |
|-------|-------------|----------|--------------|
| P1 | AGENTS.md template unification | 45 min | None |
| P2 | ts-bun template creation | 20 min | P1 |
| P3 | /adr command porting | 15 min | None |
| P4 | setup-config.sh enhancements | 30 min | P2 |
| P5 | update-config.sh enhancements | 45 min | P1, P3 |
| P6 | PROJECT_AGENTS.md migration | 30 min | P5 |
| P7 | Documentation & version bump | 20 min | P1-P6 |
| **Total** | | **~3.5 hrs** | |

---

#### Phase 1: AGENTS.md Template Unification (45 min)

**Objective**: Simplify all 6 templates to reference structure.

##### Task 1.1: Create unified template structure
- **Files**: All `templates/*/AGENTS.md.template` (6 files)
- **Changes per file**:
  1. Add `/spec Workflow` section (5 lines)
  2. Add `Git Workflow` section (5 lines)
  3. Add `Critical Rules` section (5 lines)
  4. Add `DO NOT OVERCOMPLICATE/OVERSIMPLIFY` to Core Principles
  5. Add `Project-Specific Instructions` section with `PROJECT_AGENTS.md` reference
  6. Remove redundant `Workflow` section (merge into /spec section)

##### Task 1.2: Language-specific tooling (per template)

| Template | Package Manager | Type Check | Lint | After-Edit |
|----------|-----------------|------------|------|------------|
| typescript | pnpm | tsc --noEmit | eslint [--fix] | eslint --fix && tsc --noEmit |
| ts-bun | bun | tsc --noEmit | eslint [--fix] | eslint --fix && tsc --noEmit |
| python-uv | uv | uv run pyright | uv run ruff check [--fix] | ruff check --fix && pyright |
| python-poetry | poetry | poetry run pyright | poetry run ruff check [--fix] | ruff check --fix && pyright |
| python-pip | pip | pyright | ruff check [--fix] | ruff check --fix && pyright |
| rust | cargo | N/A | cargo clippy | cargo clippy && cargo check |
| generic | (customizable) | (customizable) | (customizable) | (customizable) |

##### Validation
- [ ] All 6 templates have identical section structure
- [ ] All templates include PROJECT_AGENTS.md reference
- [ ] Line count: ~50-55 lines per template (vs. current ~33)

---

#### Phase 2: ts-bun Template Creation (20 min)

**Objective**: Add Bun variant for TypeScript projects.

##### Task 2.1: Create template directory
```
templates/ts-bun/
├── AGENTS.md.template
└── .agent/
    └── config.yml.template
```

##### Task 2.2: AGENTS.md.template
- Copy from `typescript/AGENTS.md.template`
- Replace `pnpm` → `bun`
- Replace `pnpm install` → `bun install`
- Replace `vitest` → `bun test` (if applicable)

##### Task 2.3: config.yml.template
- Copy from `typescript/.agent/config.yml.template`
- Update package manager references

##### Task 2.4: Update detect-project-type.sh
**Insert at line 8** (before TypeScript check):
```bash
# Bun indicators (check before pnpm)
if [[ -f "$target_path/bun.lockb" ]]; then
  echo "ts-bun"
  return 0
fi
```

##### Validation
- [ ] `bun.lockb` detection works
- [ ] Falls back to `typescript` when no lockb present
- [ ] Template renders correctly

---

#### Phase 3: /adr Command Porting (15 min)

**Objective**: Make /adr command project-agnostic.

##### Task 3.1: Create command file
- **Source**: External adr command file
- **Target**: `/core/commands/claude/adr.md`

##### Task 3.2: Make project-agnostic
**Changes**:
1. Replace hardcoded source path with:
   ```
   Read ADR index: `$(pwd)/adrs/000-index.md`
   ```
2. Add auto-create logic:
   ```
   If `adrs/` directory missing:
     - Create `adrs/`
     - Create `000-index.md` with template
   ```
3. Update commit command to use relative path

##### Task 3.3: Add to extras list
**Files to update**:
- `scripts/setup-config.sh` line 228: Add `adr` to cmd list
- `scripts/update-config.sh` line 187: Add `adr` to cmd list

##### Validation
- [ ] /adr works in project without existing `adrs/` dir
- [ ] Creates proper index template
- [ ] Commit path is relative

---

#### Phase 4: setup-config.sh Enhancements (30 min)

**Objective**: Add .gitignore, git init, new extras.

##### Task 4.1: Create shared .gitignore template
**File**: `templates/shared/.gitignore.template`
```gitignore
# Agentic Config
.agentic-config.backup.*

# Editor
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Secrets (never commit)
.env
.env.local
*.key
credentials.json
```

##### Task 4.2: Add .gitignore copy logic
**Insert after line 179** (after local symlinks):
```bash
# Create .gitignore if not exists
if [[ ! -f "$TARGET_PATH/.gitignore" ]]; then
  echo "🔵 Creating default .gitignore..."
  if [[ "$DRY_RUN" != true ]]; then
    cp "$REPO_ROOT/templates/shared/.gitignore.template" "$TARGET_PATH/.gitignore"
  fi
fi
```

##### Task 4.3: Add git init logic
**Insert after .gitignore**:
```bash
# Initialize git if not a repo
if [[ ! -d "$TARGET_PATH/.git" ]]; then
  echo "🔵 Initializing git repository..."
  if [[ "$DRY_RUN" != true ]]; then
    git -C "$TARGET_PATH" init --quiet
  fi
fi
```

##### Task 4.4: Add `adr` to extras list
**Edit line 228**: Add `adr` to command list

##### Task 4.5: Update agentic-setup.md agent
- Document .gitignore creation
- Document git init behavior
- Add adr to extras description

##### Validation
- [ ] Fresh setup creates .gitignore
- [ ] Fresh setup runs git init
- [ ] Existing .gitignore preserved
- [ ] Existing .git preserved
- [ ] --dry-run shows all new operations

---

#### Phase 5: update-config.sh Enhancements (45 min)

**Objective**: Add symlink diff management, orphan cleanup.

##### Task 5.1: Define available extras
**Add after line 12**:
```bash
# Available extras (keep in sync with setup-config.sh)
AVAILABLE_CMDS=(orc spawn squash squash_commit pull_request gh_pr_review adr)
AVAILABLE_SKILLS=(agent-orchestrator-manager single-file-uv-scripter command-writer skill-writer git-find-fork)
```

##### Task 5.2: Add orphan symlink cleanup
**Add function before main logic**:
```bash
cleanup_orphan_symlinks() {
  local target="$1"
  local dir="$2"
  local removed=0

  if [[ -d "$target/$dir" ]]; then
    for link in "$target/$dir"/*; do
      if [[ -L "$link" && ! -e "$link" ]]; then
        rm "$link"
        echo "  ⚠ Removed orphan: $(basename "$link")"
        ((removed++)) || true
      fi
    done
  fi
  echo "$removed"
}
```

##### Task 5.3: Add new extras detection
**Add to extras installation section (~line 182)**:
```bash
# Check for new available commands not yet installed
echo "🔵 Checking for new available commands..."
for cmd in "${AVAILABLE_CMDS[@]}"; do
  if [[ -f "$REPO_ROOT/core/commands/claude/$cmd.md" && ! -L "$TARGET_PATH/.claude/commands/$cmd.md" ]]; then
    echo "  📦 New command available: $cmd"
  fi
done

# Clean up orphaned symlinks
ORPHANS=$(cleanup_orphan_symlinks "$TARGET_PATH" ".claude/commands")
[[ $ORPHANS -gt 0 ]] && echo "  Cleaned $ORPHANS orphan command symlinks"

ORPHANS=$(cleanup_orphan_symlinks "$TARGET_PATH" ".claude/skills")
[[ $ORPHANS -gt 0 ]] && echo "  Cleaned $ORPHANS orphan skill symlinks"
```

##### Task 5.4: Update agentic-update.md agent
- Document orphan cleanup
- Document new extras detection
- Add adr to available commands list

##### Validation
- [ ] Detects new commands not yet installed
- [ ] Removes orphaned symlinks
- [ ] Logs cleanup actions
- [ ] --extras installs new commands including adr

---

#### Phase 6: PROJECT_AGENTS.md Migration (30 min)

**Objective**: Implement customization separation pattern.

##### Task 6.1: Add migration function to update-config.sh
**Add function**:
```bash
migrate_to_project_agents() {
  local target="$1"
  local template_dir="$2"
  local agents_file="$target/AGENTS.md"
  local project_file="$target/PROJECT_AGENTS.md"

  # Skip if PROJECT_AGENTS.md already exists
  [[ -f "$project_file" ]] && return 0

  # Check if AGENTS.md has customizations
  local marker_line=$(grep -n "CUSTOMIZE BELOW THIS LINE" "$agents_file" 2>/dev/null | cut -d: -f1)
  [[ -z "$marker_line" ]] && return 0

  # Extract content after marker (skip marker line + 1 comment line)
  local custom_content=$(tail -n +$((marker_line + 2)) "$agents_file" | grep -v '^$' | head -20)
  [[ -z "$custom_content" ]] && return 0

  # Has real customizations - migrate
  echo "🔵 Migrating customizations to PROJECT_AGENTS.md..."
  tail -n +$((marker_line + 2)) "$agents_file" > "$project_file"

  # Replace AGENTS.md with fresh template
  cp "$template_dir/AGENTS.md.template" "$agents_file"

  echo "🟢 Migration complete: customizations preserved in PROJECT_AGENTS.md"
  return 0
}
```

##### Task 6.2: Call migration in update flow
**Add before version update (~line 168)**:
```bash
# Migrate customizations to PROJECT_AGENTS.md if needed
if [[ "$FORCE" == true ]]; then
  migrate_to_project_agents "$TARGET_PATH" "$TEMPLATE_DIR"
fi
```

##### Task 6.3: Update AGENTS.md templates
All templates already updated in Phase 1 to include:
```markdown
## Project-Specific Instructions
READ @PROJECT_AGENTS.md for project-specific instructions - CRITICAL COMPLIANCE

<!-- PROJECT_AGENTS.md contains project-specific guidelines that override defaults -->
```

##### Task 6.4: Update agentic-migrate.md agent
- Document PROJECT_AGENTS.md pattern
- Explain migration behavior
- Add manual migration instructions

##### Validation
- [ ] Detects customizations below marker
- [ ] Creates PROJECT_AGENTS.md with extracted content
- [ ] Replaces AGENTS.md with fresh template
- [ ] Preserves projects without customizations
- [ ] Skips if PROJECT_AGENTS.md exists

---

#### Phase 7: Documentation & Version Bump (20 min)

**Objective**: Update all documentation and bump version.

##### Task 7.1: VERSION file
- Change `1.1.0` → `1.1.1`

##### Task 7.2: CHANGELOG.md
Add entry:
```markdown
## [1.1.1] - 2025-12-XX

### Added
- **ts-bun template**: Bun package manager alternative for TypeScript
- **/adr command**: Architecture Decision Records with auto-numbering
- **PROJECT_AGENTS.md pattern**: Separate template from customizations
- **Setup enhancements**:
  - Auto-create .gitignore
  - Auto-run git init
- **Update enhancements**:
  - Detect new available commands/skills
  - Clean up orphaned symlinks
  - Migrate customizations to PROJECT_AGENTS.md

### Changed
- All AGENTS.md templates simplified with unified structure
- Added /spec workflow and git workflow sections
- Added critical rules section
- detect-project-type.sh now detects bun.lockb

### Migration Notes
- Existing customizations below "CUSTOMIZE BELOW THIS LINE" will be migrated to PROJECT_AGENTS.md on next --force update
- New commands available: /adr (install with --extras)
```

##### Task 7.3: Update README.md
- Add ts-bun to project types list
- Document PROJECT_AGENTS.md pattern
- Add /adr to extras list

##### Task 7.4: Update agent docs
- `agentic-setup.md`: .gitignore, git init, /adr
- `agentic-update.md`: PROJECT_AGENTS.md migration, orphan cleanup
- `agentic-migrate.md`: PROJECT_AGENTS.md handling

##### Validation
- [ ] VERSION shows 1.1.1
- [ ] CHANGELOG has complete entry
- [ ] README documents all new features
- [ ] All agent docs current

---

#### Execution Order

```
P1 (templates) ─┬─> P2 (ts-bun) ───┐
                │                   │
P3 (adr) ───────┼─────────────────>├─> P4 (setup) ─┐
                │                   │               │
                └─> P5 (update) ───>├─> P6 (migrate)│
                                    │               │
                                    └───────────────┴─> P7 (docs)
```

**Parallelizable**: P1 + P3 can run concurrently
**Sequential**: P4 depends on P2, P3; P6 depends on P5; P7 depends on all

---

#### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Template migration breaks existing projects | Backup always created; --dry-run available |
| PROJECT_AGENTS.md extraction fails | Conservative marker detection; skip if uncertain |
| Orphan cleanup removes wanted symlinks | Only removes dead symlinks (target missing) |
| ts-bun detection conflicts with typescript | Check bun.lockb BEFORE package.json |

---

#### Testing Plan

1. **Unit**: Each script function in isolation
2. **Integration**:
   - Fresh setup with each template type (7 types)
   - Update from 1.1.0 with customizations
   - Update from 1.1.0 without customizations
   - --extras flag adds all new commands including adr
3. **Regression**:
   - Existing /spec workflow unaffected
   - Existing symlinks remain valid
   - Version tracking works

---

#### Summary

| Deliverable | Files Created | Files Modified |
|-------------|---------------|----------------|
| ts-bun template | 2 | 0 |
| /adr command | 1 | 2 |
| .gitignore template | 1 | 1 |
| Template updates | 0 | 6 |
| Script updates | 0 | 3 |
| Agent updates | 0 | 3 |
| Docs updates | 0 | 3 |
| **Total** | **4** | **18** |

Full plan summary: `outputs/orc/2025/12/15/172534-e1f7dc1e/03-spec-plan/summary.md`
