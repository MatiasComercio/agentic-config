# Human Section
Critical: any text/subsection here cannot be modified by AI.

## High-Level Objective (HLO)

Create a `/issue` command that allows users to report issues to the central agentic-config repository (https://github.com/MatiasComercio/agentic-config/issues) using the GitHub CLI. This command streamlines bug reporting and feature requests by extracting context from the current conversation or accepting explicit user input, reducing friction for contributors to report problems or suggest improvements.

## Mid-Level Objectives (MLO)

- CREATE `core/commands/claude/issue.md` command file with proper YAML frontmatter
- IMPLEMENT gh CLI integration for issue creation targeting the central repository
- SUPPORT two input modes:
  - **Context-based**: Extract issue details from current conversation (errors, stack traces, unexpected behavior)
  - **Explicit**: Accept user-provided title and body
- VALIDATE gh CLI authentication before issue creation
- FORMAT issue body with structured sections (description, reproduction steps, environment info)
- INCLUDE automatic environment metadata (OS, git version, branch context)
- ENSURE project-agnostic design (works from any agentic-config installation)

## Details (DT)

### Target Repository
- Issues MUST be created at: `MatiasComercio/agentic-config`
- Use `gh issue create --repo MatiasComercio/agentic-config`

### Command Usage Patterns
```
/issue                           # Context-based: extract from conversation
/issue "Title" "Description"     # Explicit: user provides details
/issue --bug "Title"             # Bug report with template
/issue --feature "Title"         # Feature request with template
```

### Issue Body Structure
```markdown
## Description
<User-provided or context-extracted description>

## Environment
- OS: <detected>
- Shell: <detected>
- Git version: <detected>
- Branch: <current branch if relevant>
- agentic-config version: <from git tag or commit>

## Context
<If extracted from conversation: relevant error messages, stack traces, or unexpected behavior>

## Reproduction Steps
<If applicable>

---
Reported via `/issue` command from agentic-config
```

### Constraints
- MUST validate `gh auth status` before creating issue
- MUST NOT expose sensitive information (API keys, personal paths, etc.)
- SHOULD sanitize paths to be relative or anonymized
- MUST handle cases where no context is available gracefully
- MUST confirm with user before creating issue (show preview)

### Reference Commands
- Similar pattern to: `core/commands/claude/pull_request.md`
- Uses gh CLI like: `core/commands/claude/gh_pr_review.md`

## Behavior

You are implementing a production-ready Claude Code command. Follow the established patterns in existing commands (pull_request.md, gh_pr_review.md). The command must be robust, handle edge cases gracefully, and provide clear user feedback at each step.

# AI Section
Critical: AI can ONLY modify this section.

## Research

## Plan

## Plan Review

## Implement

## Test Evidence & Outputs

## Updated Doc

## Post-Implement Review
