# Changelog

All notable changes to agentic-config.

## [0.1.2] - 2025-12-16

### Added
- `/init` command for post-clone setup (creates symlinks + global install)
- `/branch` command for new branch with spec directory structure
- Quickstart section in README for new contributors

### Changed
- All commands/skills now installed by default (removed `--extras` flag)
- `/spec` removed from global install (project-specific only)
- Symlinks converted from absolute to relative paths (portable)
- Self-hosted repo detection in update script

### Fixed
- Symlinks now work after cloning to any directory

## [0.1.1] - 2025-12-15

### Added
- ts-bun template for Bun package manager
- `/adr` command for Architecture Decision Records
- PROJECT_AGENTS.md pattern (separates template from customizations)
- Auto-create `.gitignore` and `git init` during setup
- Orphan symlink cleanup on update

## [0.1.0] - 2025-11-25

### Added
- Centralized agentic configuration system
- Templates: TypeScript, Python (uv/poetry/pip), Rust, generic
- Hybrid symlink + copy distribution pattern
- Claude Code, Gemini CLI, Codex CLI, Antigravity integrations
- Spec workflow stages: CREATE, RESEARCH, PLAN, PLAN_REVIEW, IMPLEMENT, TEST, REVIEW, DOCUMENT, VALIDATE, FIX, AMEND
- Agent-powered management with 6 specialized agents
- `/agentic` commands: setup, migrate, update, status, validate, customize
- Natural language interface for all operations
- Project-agnostic commands and skills (/orc, /spawn, /squash, /pull_request, /gh_pr_review)
- Management scripts: setup, migrate, update
- Dynamic extras discovery and installation
