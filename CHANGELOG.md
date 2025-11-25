# Changelog

All notable changes to the Agentic Configuration System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-24

### Added
- Initial release of centralized agentic configuration system
- Core workflow files from praxi (RESEARCH, PLAN, IMPLEMENT, REVIEW, VALIDATE, FIX, AMEND)
- Template support for 5 project types:
  - TypeScript (pnpm, tsc, eslint)
  - Python with Poetry (poetry, pyright, ruff)
  - Python with pip (pip, mypy, pylint)
  - Rust (cargo, clippy)
  - Generic (customizable)
- Management scripts:
  - `setup-config.sh` - Install to new project
  - `migrate-existing.sh` - Convert manual installations
  - `update-config.sh` - Sync latest changes
- Utility libraries:
  - `detect-project-type.sh` - Auto-detect project language
  - `template-processor.sh` - Process template files
  - `version-manager.sh` - Track versions and registry
- Hybrid symlink + copy distribution pattern:
  - Symlinked: Core workflows, AI tool commands
  - Copied: Project configs, AGENTS.md
- Version tracking via `.agentic-config.json`
- Central installation registry (`.installations.json`)
- Opt-in update checking per project
- AI tool integration:
  - Claude Code (`.claude/commands/spec.md`)
  - Gemini CLI (`.gemini/commands/spec.toml`)
  - Antigravity (`.agent/workflows/spec.md`)
- Comprehensive README and documentation
- Automatic backup before migration/updates
- Dry-run mode for all scripts

### Architecture Decisions
- Chose hybrid approach over git submodules (simpler, no git complexity)
- Symlinks for universal files (instant updates)
- Copies for customizable configs (project independence)
- Central repo as single source of truth
- Opt-in auto-check (respects project autonomy)
- Both Python toolchains supported (poetry + pip)

### Migration Notes
- Existing projects with manual installations can use `migrate-existing.sh`
- Customizations in AGENTS.md are preserved during migration
- Backups created automatically (`.agentic-config.backup.<timestamp>`)
- Version 1.0.0 establishes baseline for all future updates

## [1.1.0] - 2025-11-25

### Added
- **Agent-Powered Management System**
  - 6 specialized Claude Code agents for installation management
  - Natural language interface for all operations
  - Interactive workflows with explanation and confirmation

- **New Commands:**
  - `/agentic setup [path]` - Setup new project with auto-detection
  - `/agentic migrate [path]` - Migrate existing installations
  - `/agentic update [path]` - Update to latest version with diff review
  - `/agentic status` - Dashboard of all installations
  - `/agentic validate [path]` - Diagnose and auto-fix issues
  - `/agentic customize` - Interactive customization guide

- **Agent Features:**
  - Auto-detect project type (TypeScript, Python, Rust, Generic)
  - Explain before execution (dry-run support)
  - Show diffs for template changes
  - Guide manual merges when needed
  - Validate after operations
  - Auto-fix common issues

- **Documentation:**
  - Comprehensive agent guide (`docs/agents/AGENTIC_AGENT.md`)
  - Updated README with agent-powered workflows
  - Natural language usage examples

### Changed
- Setup script now creates agent and command symlinks
- Version manager tracks agent files in `.agentic-config.json`
- README Quick Start now recommends agent interface

### Technical
- 6 agent files in `core/agents/agentic-*.md`
- 5 command wrappers in `core/commands/claude/agentic*.md`
- Agents use bash scripts under the hood (no duplication)
- Backward compatible: manual script execution still works

## [1.0.1] - 2025-11-25

### Added
- Codex CLI support (`.codex/prompts/spec.md` symlink to central spec-command.md)
- Updated setup-config.sh to install Codex configurations alongside Claude/Gemini
- Updated version tracking to include Codex symlinks in `.agentic-config.json`

### Fixed
- Completed all 4 agentic tool integrations (Claude Code, Gemini CLI, Codex CLI, Antigravity)

## [Unreleased]

### Planned
- Validate-config.sh script for integrity checks
- List-installations.sh to query registry
- Uninstall-config.sh for clean removal
- Extended documentation (architecture.md, customization.md)
- Migration guides for breaking changes
- Support for additional languages (Go, Java, etc.)
- Advanced template variable substitution
- Conflict resolution for template updates
- CI/CD integration examples
