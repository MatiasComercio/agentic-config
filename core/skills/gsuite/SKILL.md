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

## Architecture

This skill uses the orchestrator pattern:

```
User Request -> SKILL.md -> agent-orchestrator-manager -> /spawn agents -> Bash CLI tools
```

NEVER execute tools directly. ALWAYS delegate via `/spawn` command.

## Orchestration Rules

**CRITICAL: NEVER execute tools directly. ALWAYS delegate via `/spawn`.**

The orchestrator (this skill) MUST NOT consume tokens for data processing. Its role is:
1. Parse user request
2. Delegate execution to subagents
3. Review subagent outputs (max 3 correction loops)
4. Return final answer

### Model Selection

| Complexity | Model | Use For |
|------------|-------|---------|
| Simple reads | haiku | `auth.py status`, `gmail.py list`, single API calls |
| Moderate | sonnet | Multi-step operations, data processing, searches, summarization |
| Complex | opus | Cross-service operations, analysis requiring judgment |

### Delegation Pattern

**Phase 1: Data Collection** - Spawn haiku/sonnet to execute CLI tools and collect raw data
**Phase 2: Processing** - Spawn haiku/sonnet to summarize, analyze, or transform data
**Phase 3: Final Answer** - Spawn haiku/sonnet to format the final response
**Orchestrator Role** - Review outputs, ensure requirements met, iterate if needed (max 3 loops)

### Examples

WRONG - Direct execution (orchestrator consuming tokens):
```
Bash(uv run gmail.py list --limit 10)
Bash(uv run gcalendar.py list-events --days 7)
# Then processing data directly in orchestrator context
```

CORRECT - Delegated execution:
```
/spawn haiku "Run: uv run core/skills/gsuite/tools/gmail.py list --limit 10"
/spawn haiku "Run: uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7 --json"
```

CORRECT - Full delegation with processing:
```
/spawn sonnet "Execute:
1. Run: uv run core/skills/gsuite/tools/gmail.py search 'from:user@example.com' --json --limit 10
2. For each message ID, run: uv run gmail.py read <id>
3. Summarize key themes
4. Propose next steps for each
Report: Formatted summary with next steps"
```

## CLI Tools

All tools are PEP 723 uv scripts in `core/skills/gsuite/tools/`:

| Tool | Description | Example |
|------|-------------|---------|
| `setup.py` | Setup automation | `uv run setup.py init` |
| `auth.py` | Account management | `uv run auth.py status` |
| `gdate.py` | Date/time parsing | `uv run gdate.py parse "mon 3pm" --json` |
| `sheets.py` | Sheets operations | `uv run sheets.py read <id> "A1:D10"` |
| `docs.py` | Docs operations | `uv run docs.py read <id>` |
| `slides.py` | Slides operations | `uv run slides.py read <id>` |
| `drive.py` | Drive operations | `uv run drive.py list` |
| `gmail.py` | Gmail operations | `uv run gmail.py list --limit 10` |
| `gcalendar.py` | Calendar operations | `uv run gcalendar.py list-events --days 7` |
| `tasks.py` | Tasks operations | `uv run tasks.py list-lists` |
| `people.py` | Contact search | `uv run people.py search "John"` |

## Conditional Cookbook Reading

| Operation | Cookbook | When to Read |
|-----------|----------|--------------|
| Calendar | `cookbook/gcalendar.md` | list-events with filters, create/update/delete |
| Drive | `cookbook/drive.md` | "shared with me", find recent files, sharing notifications |
| Gmail | `cookbook/gmail.md` | send, draft, reply |
| Tasks | `cookbook/tasks.md` | create, complete, delete |
| People | `cookbook/people.md` | Any name mentioned (not email) |
| Preferences | `cookbook/preferences.md` | User correction/preference detected, "remember this" |
| Auth | `cookbook/auth.md` | Setup, multi-org, credentials issues |

## Customization Path Resolution

**CRITICAL: NEVER read customization files from project root.**

Customization files are USER-local and stored in the global agentic installation:

```bash
# CORRECT - Always use $AGENTIC_GLOBAL
$AGENTIC_GLOBAL/customization/gsuite/people.md
$AGENTIC_GLOBAL/customization/gsuite/gcalendar.md

# WRONG - Project root has different purpose
$PWD/customization/gsuite/...  # This is for DEVELOPMENT, not runtime
./customization/gsuite/...     # NEVER use relative paths
```

**Resolution order:**
1. Resolve `$AGENTIC_GLOBAL` first (see CLAUDE.md Path Resolution)
2. Check if customization file exists: `[[ -f "$AGENTIC_GLOBAL/customization/gsuite/<tool>.md" ]]`
3. Only read if exists - missing files are normal (user hasn't customized)

## Workflow

### 0. Resolve Date Context (MANDATORY)

Before ANY operation, get current date/time with timezone:

```bash
date "+%Y-%m-%dT%H:%M:%S %Z"
```

Use this as baseline for ALL relative date references ("today", "next week", "upcoming", etc.). NEVER hardcode or assume years.

### 0.1. Load Preferences (Convention-Based)

**Convention**: `<tool>.py` -> `<tool>.md`

Before executing operations, load relevant preferences:

1. **Always**: Read `index.md` (general patterns, conditional routing)
2. **Tool-specific**: Read `<tool>.md` if exists
3. **Account reference**: Read `auth.md` when "work", "personal", account label detected
4. **Name mentioned**: Read `people.md` when name (not email) mentioned

```bash
PREFS="$AGENTIC_GLOBAL/customization/gsuite"

# Always check index first
[[ -f "$PREFS/index.md" ]] && cat "$PREFS/index.md"

# Tool-specific
[[ -f "$PREFS/<tool>.md" ]] && cat "$PREFS/<tool>.md"

# Cross-cutting (conditional)
[[ -f "$PREFS/auth.md" ]] && cat "$PREFS/auth.md"      # if account reference
[[ -f "$PREFS/people.md" ]] && cat "$PREFS/people.md"  # if name mentioned
```

Apply loaded preferences to current operation parameters.

### 0.2. Resolve Account (MANDATORY)

When account is ambiguous, confirm with user before proceeding.

**Auto-resolve (no confirmation needed):**
- Explicit in request: "on my work calendar", "from personal email"
- Loaded from auth.md preferences: account labels resolved
- Single account configured: use it
- Already specified in session: reuse

**Confirm when:**
- Multiple accounts configured AND no account specified/derivable
- First gsuite operation in session without account context

**AskUserQuestion template:**
```
Question: "Which account should I use for this operation?"
Header: "Account"
Options: [list configured accounts from auth.py status]
```

After confirmation, remember for session unless user specifies otherwise.

**Multi-account operations:**

When request explicitly involves multiple accounts (e.g., "check both my work and personal calendars"):
1. Parse which accounts are referenced
2. Execute operations with explicit `--account` for each
3. Combine results in response

Example:
```bash
# User: "check next week schedule for my personal & work calendars"
uv run gcalendar.py list-events --days 7 --account personal@example.com --json
uv run gcalendar.py list-events --days 7 --account work@company.com --json
```

### 1. Check Authentication

Before any operation, verify authentication:

```bash
uv run core/skills/gsuite/tools/auth.py status --json
```

If no accounts configured, **read `cookbook/auth.md`** and initiate interactive setup using AskUserQuestion.

### 2. Resolve People (MANDATORY)

When ANY person's name is mentioned (not email), **read `cookbook/people.md`** and follow resolution flow:
1. Check preferences first (`$AGENTIC_GLOBAL/customization/gsuite/people.md`)
2. Use People API if not in preferences
3. Handle single/multiple/no matches appropriately

### 3. Parse User Request

Identify operation type and **read relevant cookbook** for tool-specific rules:
- Calendar operations -> `cookbook/gcalendar.md`
- Gmail send/draft -> `cookbook/gmail.md`
- Tasks write ops -> `cookbook/tasks.md`

### 4. Invoke Orchestrator

Delegate to agent-orchestrator-manager which spawns agents to execute CLI tools.

### 5. Report Results

Collect agent outputs and report to user with:
- Operation status (success/failure)
- Data retrieved or modified
- Any errors encountered

### 5b. Proactive Preference Learning

After operation AND user follow-up, detect preference/correction patterns in user messages.

**Trigger on:**
- Corrections: "No, always ...", "Actually, ...", "Never ...", "Don't ..."
- Preferences: "I prefer ...", "I want ...", "Use my ...", "From now on ...", "By default ..."
- Explicit: "remember this", "save this preference"

**Do NOT trigger on:**
- One-off specifications: "Use work calendar for this meeting"
- Factual statements: "The meeting is at 3pm"
- Contextual choices: "This one" / "That file"

When detected: **Read `cookbook/preferences.md`** for AskUserQuestion flow and storage.

### 6. Missing Command Handling

When a required CLI option/command is not available:
1. **Primary**: Propose to update the tool inline
2. **Fallback**: Offer to raise feature request via `/ac-issue`

### 7. User Preferences

When user says "remember preference" OR when correction/preference pattern detected (Step 5b):
**Read `cookbook/preferences.md`** for storage flow and AskUserQuestion templates.

## Conditional Documentation

**ALWAYS read first:**
- **$AGENTIC_GLOBAL/customization/gsuite/index.md** - Customization entry point

The `index.md` contains conditional routing to tool-specific files. Only read additional files when `index.md` indicates they exist and are relevant.

## Commands Reference

All tools support `--account/-a <email>` to override the active account.

### Authentication

```bash
uv run core/skills/gsuite/tools/auth.py status           # List accounts
uv run core/skills/gsuite/tools/auth.py add              # Add account (OAuth)
uv run core/skills/gsuite/tools/auth.py switch <email>   # Switch active
uv run core/skills/gsuite/tools/auth.py remove <email>   # Remove account
```

For setup flows, **read `cookbook/auth.md`**.

### Date/Time Parsing

Parse relative date/time expressions to ISO format for calendar operations:

```bash
uv run core/skills/gsuite/tools/gdate.py parse "mon 3pm" --json           # Next Monday at 3pm
uv run core/skills/gsuite/tools/gdate.py parse "tomorrow 2pm" --duration "1h" --json
uv run core/skills/gsuite/tools/gdate.py parse "next friday 10am" --json
uv run core/skills/gsuite/tools/gdate.py parse "in 3 days" --json
uv run core/skills/gsuite/tools/gdate.py now --json                       # Current time info
```

Integration with calendar:
```bash
times=$(uv run gdate.py parse "mon 3pm" --duration "1h" --json)
start=$(echo "$times" | jq -r '.start')
end=$(echo "$times" | jq -r '.end')
uv run gcalendar.py create "Meeting" "$start" "$end" --yes
```

### Sheets Operations

```bash
uv run core/skills/gsuite/tools/sheets.py read <id> "Sheet1!A1:D10"
uv run core/skills/gsuite/tools/sheets.py read <id> "Sheet1!A1:D10" --account user@example.com
uv run core/skills/gsuite/tools/sheets.py write <id> "Sheet1!A1" "value"
uv run core/skills/gsuite/tools/sheets.py append <id> "Sheet1" '["val1", "val2"]'
uv run core/skills/gsuite/tools/sheets.py create "My Spreadsheet"
```

### Docs Operations

```bash
uv run core/skills/gsuite/tools/docs.py read <id>
uv run core/skills/gsuite/tools/docs.py read <id> --account user@example.com
uv run core/skills/gsuite/tools/docs.py write <id> --append "New content"
uv run core/skills/gsuite/tools/docs.py create "My Document"
uv run core/skills/gsuite/tools/docs.py export <id> --format pdf --output ./doc.pdf
```

### Slides Operations

```bash
uv run core/skills/gsuite/tools/slides.py read <id>
uv run core/skills/gsuite/tools/slides.py read <id> --account user@example.com
uv run core/skills/gsuite/tools/slides.py create "My Presentation"
uv run core/skills/gsuite/tools/slides.py add-slide <id> --layout TITLE_AND_BODY
```

### Drive Operations

```bash
uv run core/skills/gsuite/tools/drive.py list [--folder <folder_id>]
uv run core/skills/gsuite/tools/drive.py list --shared-with-me                    # Files shared with me
uv run core/skills/gsuite/tools/drive.py list --owner user@example.com            # Filter by owner
uv run core/skills/gsuite/tools/drive.py list --account user@example.com
uv run core/skills/gsuite/tools/drive.py search "quarterly report"                # Full-text search
uv run core/skills/gsuite/tools/drive.py search "5 year plan" --shared-with-me    # Search in shared files
uv run core/skills/gsuite/tools/drive.py search "budget" --owner user@example.com # Search by owner
uv run core/skills/gsuite/tools/drive.py share <file_id> <email> --role writer
uv run core/skills/gsuite/tools/drive.py mkdir "Folder Name" [--parent <folder_id>]
```

### Gmail Operations

**Read `cookbook/gmail.md`** for confirmation rules and recipient resolution.

```bash
uv run core/skills/gsuite/tools/gmail.py list --limit 10
uv run core/skills/gsuite/tools/gmail.py list --limit 10 --account user@example.com
uv run core/skills/gsuite/tools/gmail.py read <message_id>
uv run core/skills/gsuite/tools/gmail.py send "to@example.com" "Subject" "Body" [--yes]
uv run core/skills/gsuite/tools/gmail.py draft "to@example.com" "Subject" "Body"
uv run core/skills/gsuite/tools/gmail.py search "from:user@example.com"
```

### Calendar Operations

**Read `cookbook/gcalendar.md`** for meeting search, timezone handling, and self-inclusion rules.

```bash
uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7
uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7 --account user@example.com
uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7 --exclude-declined  # Filter out declined
uv run core/skills/gsuite/tools/gcalendar.py list-events --type meeting  # Only meetings (with others)
uv run core/skills/gsuite/tools/gcalendar.py list-events --type block    # Only blocks (focus, OOO, personal)
uv run core/skills/gsuite/tools/gcalendar.py create "Meeting" "2024-01-15T10:00" "2024-01-15T11:00" [--yes]
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --title "New Title"
uv run core/skills/gsuite/tools/gcalendar.py delete <event_id>
uv run core/skills/gsuite/tools/gcalendar.py rsvp <event_id> accepted --yes
uv run core/skills/gsuite/tools/gcalendar.py rsvp <event_id> declined --yes
uv run core/skills/gsuite/tools/gcalendar.py calendars
```

### Tasks Operations

**Read `cookbook/tasks.md`** for confirmation rules.

```bash
uv run core/skills/gsuite/tools/tasks.py list-lists
uv run core/skills/gsuite/tools/tasks.py list-lists --account user@example.com
uv run core/skills/gsuite/tools/tasks.py list-tasks <tasklist_id>
uv run core/skills/gsuite/tools/tasks.py create <tasklist_id> "Task title" [--yes]
uv run core/skills/gsuite/tools/tasks.py complete <tasklist_id> <task_id>
```

### People Operations

**Read `cookbook/people.md`** for resolution flow.

```bash
uv run core/skills/gsuite/tools/people.py search "John Smith"
uv run core/skills/gsuite/tools/people.py search "John Smith" --account user@example.com
uv run core/skills/gsuite/tools/people.py list --limit 20
```

## Configuration

Config directory: `~/.agents/gsuite/`

```
~/.agents/gsuite/
  credentials.json          # OAuth client credentials
  service-account.json      # Enterprise service account (optional)
  config.yml                # Confirmation settings (optional)
  active_account            # Current active account
  accounts/
    <email>/
      token.json            # OAuth tokens per account
```

### Confirmation Settings

By default, write operations require user confirmation. Configure in `~/.agents/gsuite/config.yml`:

```yaml
confirmation:
  default: true    # Global default (true = ask confirmation)
  gmail: true      # Per-tool override
  calendar: true
  tasks: false     # Example: disable for tasks
```

Use `--yes` or `-y` flag on any command to bypass confirmation.

### Tool Customizations

Optional per-tool output format customizations in `$AGENTIC_GLOBAL/customization/gsuite/`:

```
$AGENTIC_GLOBAL/customization/
  gsuite/
    index.md          # Entry point with routing
    people.md         # Global contact aliases
    gcalendar.md      # Calendar output format
    gmail.md          # Gmail output format
```

Note: `$AGENTIC_GLOBAL` = `${AGENTIC_CONFIG_PATH:-~/.agents/agentic-config}`

## Extended API Access

The `--extra` parameter provides escape hatch access to Google API features not exposed via CLI options.

### Convention

```json
{
  "field": "value",         // Merged into request body (common case)
  "_api": { "param": val }  // Passed to API method directly (rare)
}
```

- Top-level keys (except `_api`) = merged into request body
- `_api` key = API method parameters

### Common Extended Parameters

| Tool | Parameter | Description | Example |
|------|-----------|-------------|---------|
| gcalendar | `recurrence` | Recurring event rules | `'{"recurrence": ["RRULE:FREQ=WEEKLY"]}'` |
| gcalendar | `reminders` | Custom reminders | `'{"reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 10}]}}'` |
| gcalendar | `_api.sendUpdates` | Notify attendees: none/all/externalOnly | `'{"_api": {"sendUpdates": "all"}}'` |
| gmail | `cc` | CC recipients | `'{"cc": ["a@example.com"]}'` |
| gmail | `bcc` | BCC recipients | `'{"bcc": ["b@example.com"]}'` |
| tasks | `parent` | Create subtask | `'{"parent": "task-id"}'` |
| drive | `_api.transferOwnership` | Transfer file ownership | `'{"_api": {"transferOwnership": true}}'` |
| drive | `_api.supportsAllDrives` | Access shared drives | `'{"_api": {"supportsAllDrives": true}}'` |

### Examples

```bash
# Recurring weekly event (simple body field)
uv run gcalendar.py create "Weekly Sync" "2024-01-15T10:00" "2024-01-15T11:00" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY"]}'

# Recurring event with attendee notifications
uv run gcalendar.py create "Team Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "team@example.com" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY"], "_api": {"sendUpdates": "all"}}'

# Email with CC and BCC
uv run gmail.py send "to@example.com" "Subject" "Body" \
  --extra '{"cc": ["cc@example.com"], "bcc": ["bcc@example.com"]}'

# Create subtask under parent
uv run tasks.py create <list-id> "Subtask" \
  --extra '{"parent": "parent-task-id"}'

# Drive share with ownership transfer
uv run drive.py share <file-id> "new-owner@example.com" --role owner \
  --extra '{"_api": {"transferOwnership": true}}'
```

### API Documentation

For full parameter reference, see official Google API docs:
- Calendar: https://developers.google.com/calendar/api/v3/reference
- Gmail: https://developers.google.com/gmail/api/reference/rest
- Tasks: https://developers.google.com/tasks/reference/rest
- Drive: https://developers.google.com/drive/api/v3/reference
- Sheets: https://developers.google.com/sheets/api/reference/rest
- Docs: https://developers.google.com/docs/api/reference/rest
- Slides: https://developers.google.com/slides/api/reference/rest

## Error Handling

- No credentials: **Read `cookbook/auth.md`** for interactive setup
- Token expired: Auto-refresh via google-auth library
- Rate limit (429): Exponential backoff with retry
- Permission denied: Verify account has access to resource
