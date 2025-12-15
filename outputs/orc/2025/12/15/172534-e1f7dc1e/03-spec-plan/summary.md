# PLAN Stage Summary - agentic-config v1.1.1

## Overview

Comprehensive implementation plan for agentic-config v1.1.1, covering 7 phases with ~3.5 hours estimated effort.

## Phase Summary

| Phase | Description | Estimate | Status |
|-------|-------------|----------|--------|
| P1 | AGENTS.md template unification | 45 min | Planned |
| P2 | ts-bun template creation | 20 min | Planned |
| P3 | /adr command porting | 15 min | Planned |
| P4 | setup-config.sh enhancements | 30 min | Planned |
| P5 | update-config.sh enhancements | 45 min | Planned |
| P6 | PROJECT_AGENTS.md migration | 30 min | Planned |
| P7 | Documentation & version bump | 20 min | Planned |

## Key Deliverables

### Files to Create (4)
1. `templates/ts-bun/AGENTS.md.template` - Bun variant template
2. `templates/ts-bun/.agent/config.yml.template` - Bun config
3. `core/commands/claude/adr.md` - Project-agnostic ADR command
4. `templates/shared/.gitignore.template` - Default gitignore

### Files to Modify (18)
- 6x AGENTS.md templates (unified structure)
- 3x Scripts (setup, update, detect)
- 3x Agent docs (setup, update, migrate)
- 3x Core docs (VERSION, CHANGELOG, README)
- 3x Misc updates

## Execution Dependencies

```
P1 (templates) --> P2 (ts-bun) --> P4 (setup)
P3 (adr) -----------------------> P4 (setup)
P1 (templates) --> P5 (update) --> P6 (migrate)
All --------------------------------> P7 (docs)
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Template migration breaks projects | High | Backup + dry-run |
| PROJECT_AGENTS.md extraction fails | Medium | Conservative detection |
| Orphan cleanup removes wanted links | Low | Only dead symlinks |
| ts-bun conflicts with typescript | Low | Check bun.lockb first |

## Success Criteria

- [ ] All 7 templates follow unified structure
- [ ] ts-bun detection works (bun.lockb)
- [ ] /adr command project-agnostic
- [ ] setup-config.sh creates .gitignore + git init
- [ ] update-config.sh detects new extras + cleans orphans
- [ ] PROJECT_AGENTS.md migration works
- [ ] VERSION = 1.1.1, CHANGELOG updated

## Full Spec

See: `specs/2025/12/feat/agentic-config-1.1.1/001-agentic-config-v1.1.1.md`
