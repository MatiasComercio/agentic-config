---
name: gsuite
description: Google Suite integration for Sheets, Docs, Slides, Gmail, Calendar, Tasks with multi-account support. Orchestrates operations via CLI tools. Triggers on keywords: google sheets, google docs, google slides, gsuite, gdrive, spreadsheet, document, gmail, google calendar, google tasks
project-agnostic: true
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Skill
---

# GSuite Skill

Google Suite integration for Claude Code with multi-account support (enterprise + personal).

## Capabilities

- Sheets: Read/write cells, create spreadsheets, append rows, format cells
- Docs: Read/write documents, create docs, export to PDF/DOCX
- Slides: Read presentations, create slides, add content
- Drive: List files, share, manage permissions, create folders
- Gmail: Read/send/draft messages, search, manage labels
- Calendar: List/create/update/delete events, manage calendars
- Tasks: List/create/complete/delete tasks
- People: Search contacts, resolve names to emails before operations
- Auth: Multi-account management with account switching

## Orchestration

**CRITICAL: NEVER execute tools directly. ALWAYS delegate via `/spawn`.**

| Complexity | Model | Use For |
|------------|-------|---------|
| Simple reads | haiku | `auth.py status`, `gmail.py list`, single API calls |
| Moderate | sonnet | Multi-step operations, data processing, summarization |
| Complex | opus | Cross-service operations, analysis requiring judgment |

For delegation patterns and examples, see `cookbook/orchestration.md`.

## Conventions

**Tools:** All PEP 723 uv scripts in `core/skills/gsuite/tools/`. All support `--help` and `--account/-a <email>`.

**Cookbook:** `<tool>.py` -> `cookbook/<tool>.md` (MANDATORY read before executing)

**Customization:** `<tool>.py` -> `$AGENTIC_GLOBAL/customization/gsuite/<tool>.md`

## Workflow

### 1. Initialize
- Get date context: `date "+%Y-%m-%dT%H:%M:%S %Z"`
- Check auth: `uv run auth.py status --json`
- Resolve account (ask if ambiguous, remember for session)

### 2. Load Preferences
Check `$AGENTIC_GLOBAL/customization/gsuite/` for:
- `index.md` (always)
- `<tool>.md` (if exists)
- `people.md` (if name mentioned)

### 3. Resolve People
If name (not email) mentioned -> read `cookbook/people.md`, then:
1. Check customization `people.md` first
2. Fall back to People API
3. Handle ambiguous matches

### 4. Read Cookbook (BLOCKING)
**STOP. Read cookbook before executing any tool.**
Convention: `<tool>.py` -> `cookbook/<tool>.md`

### 5. Execute & Report
Run tool, report results (status, data, errors).

### 6. Learn Preferences (Post-Execution)
On user correction -> read `cookbook/preferences.md` for storage flow.

## Configuration

Config directory: `~/.agents/gsuite/`

```
~/.agents/gsuite/
  credentials.json          # OAuth client credentials
  service-account.json      # Enterprise service account (optional)
  config.yml                # Confirmation settings (optional)
  active_account            # Current active account
  accounts/<email>/token.json
```

### Confirmation Settings

Write operations require confirmation by default. Configure in `config.yml`:

```yaml
confirmation:
  default: true    # Global default
  gmail: true      # Per-tool override
  tasks: false     # Disable for specific tools
```

Use `--yes` or `-y` flag to bypass confirmation.

## Extended API Access

For `--extra` parameter usage (recurring events, CC/BCC, subtasks, etc.), see `cookbook/extra.md`.

## Error Handling

- No credentials: Read `cookbook/auth.md` for interactive setup
- Token expired: Auto-refresh via google-auth library
- Rate limit (429): Exponential backoff with retry
- Permission denied: Verify account has access to resource
