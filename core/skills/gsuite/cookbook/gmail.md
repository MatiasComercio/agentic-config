# Gmail Cookbook

Gmail operations and confirmation rules.

## Confirmation Rules

Write operations (send, draft) require user confirmation by default.

| Operation | Confirmation Required | Bypass Flag |
|-----------|----------------------|-------------|
| `send` | Yes | `--yes` |
| `draft` | Yes | `--yes` |
| `list` | No | - |
| `read` | No | - |
| `search` | No | - |
| `labels` | No | - |

## Commands Reference

```bash
# List messages
uv run core/skills/gsuite/tools/gmail.py list --limit 10

# Read message content
uv run core/skills/gsuite/tools/gmail.py read <message_id>

# Send email (requires confirmation)
uv run core/skills/gsuite/tools/gmail.py send "to@example.com" "Subject" "Body"

# Send email (skip confirmation)
uv run core/skills/gsuite/tools/gmail.py send "to@example.com" "Subject" "Body" --yes

# Create draft (requires confirmation)
uv run core/skills/gsuite/tools/gmail.py draft "to@example.com" "Subject" "Body"

# Search messages
uv run core/skills/gsuite/tools/gmail.py search "from:user@example.com"

# List labels
uv run core/skills/gsuite/tools/gmail.py labels
```

## Recipient Resolution

**ALWAYS resolve recipients before sending**. See cookbook/people.md for resolution flow.

```
User: "Send email to John about the meeting"

1. Resolve "John" -> john.smith@example.com (via people.md or People API)
2. Confirm recipient if multiple matches
3. Execute: uv run gmail.py send "john.smith@example.com" "Subject" "Body"
```
