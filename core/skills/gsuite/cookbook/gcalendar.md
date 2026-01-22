# Calendar Cookbook

Calendar-specific rules for meeting search, timezone handling, and event creation.

## Meeting Search Semantics

**CRITICAL INTERPRETATION RULES** (apply BEFORE searching):
- "meeting/catchup with X" = X is an **attendee** (use `--attendee <email>`)
- "1:1 with X" = exactly 2 attendees, post-filter for `len(attendees) == 2`
- **NEVER search by event title** when user specifies a person - use `--attendee` filter

### Filtering Out Personal Events

When looking for **meetings** (not personal events), always use `--with-attendees`:
- This filters out solo events like "Exercise", "Lunch", "Focus time"
- Combine filters: `--attendee <email> --with-attendees`

### Search Flow

1. Resolve person's email first (see cookbook/people.md)

2. **Initial search** with meeting filters:
   ```bash
   uv run gcalendar.py list-events --attendee <email> --with-attendees --days 30 --limit 100 --json
   ```

3. **If no results found**, use AskUserQuestion for progressive search:
   ```
   AskUserQuestion:
     Question: "No meetings with <name> found in next 30 days. How to proceed?"
     Header: "Expand"
     Options:
       - "Search further ahead (90 days)" (Recommended)
       - "Search with higher limit (500 events)"
       - "Cancel search"
   ```

4. **When in doubt** (multiple candidate meetings): Use AskUserQuestion to clarify

### Examples

**CORRECT - Calendar search with name:**
```
User: "Find next catchup with Joe"

1. Check people.md / gcalendar.md -> Not found
2. People API: uv run people.py search "Joe"
3. Result: joe.doe@example.com
4. Search: uv run gcalendar.py list-events --attendee joe.doe@example.com --with-attendees --days 30 --json
```

**WRONG - Searching by title instead of attendee:**
```
User: "Find meeting with Joe"

# WRONG: Searching by event title when user said "meeting with Joe"
uv run gcalendar.py list-events --days 30 | grep -i "catchup"

# WRONG: Listing all events (includes personal events like Exercise, Lunch)
uv run gcalendar.py list-events --days 30 --json
```

## Timezone Handling

**Default behavior**: Tool detects local timezone automatically if `--timezone` not specified.

### Parallel/Related Events

When creating a parallel event based on an existing event's time:

1. **DO NOT copy the `timeZone` field** from original event JSON
2. **Use the UTC offset from `dateTime`** to determine actual timezone:
   - `dateTime: "2026-01-22T18:30:00-03:00"` means event is at 18:30 in UTC-3 zone
   - The stored `timeZone` may be organizer's timezone, NOT the display timezone
3. **Use local timezone** when the dateTime offset matches your local offset
4. **Ask for clarification** if ambiguous

### Examples

**WRONG - Using stored timeZone field:**
```bash
# Original event: dateTime "2026-01-22T18:30:00-03:00", timeZone "America/Los_Angeles"
# WRONG: Using stored timeZone makes 18:30 LA time = 23:30 Buenos Aires!
uv run gcalendar.py create "Parallel" "2026-01-22T18:30" "2026-01-22T19:30" \
  --timezone "America/Los_Angeles" --yes
```

**CORRECT - Using offset to determine timezone:**
```bash
# Original event: dateTime "2026-01-22T18:30:00-03:00", timeZone "America/Los_Angeles"
# The -03:00 offset indicates actual timezone (e.g., America/Argentina/Buenos_Aires)
uv run gcalendar.py create "Parallel" "2026-01-22T18:30" "2026-01-22T19:30" \
  --timezone "America/Argentina/Buenos_Aires" --yes

# Or simply let tool detect local timezone (recommended when local matches offset)
uv run gcalendar.py create "Parallel" "2026-01-22T18:30" "2026-01-22T19:30" --yes
```

## Self-Inclusion

When scheduling events with attendees:

1. **Get active account**: `uv run auth.py status --json | jq -r '.active'`
2. **Include self in attendees** unless user explicitly says "don't include me"
3. **Add self to attendee list**: Include the active account email in `--attendees`

```bash
# Get active account email
active=$(uv run core/skills/gsuite/tools/auth.py status --json | jq -r '.active')

# Include self when creating event with attendees
uv run gcalendar.py create "Team Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "$active,colleague@example.com" --meet --yes
```

## Commands Reference

Write operations (create, update, delete) require user confirmation by default.

```bash
# List upcoming events
uv run core/skills/gsuite/tools/gcalendar.py list-events --days 7

# Create event (uses local timezone by default)
uv run core/skills/gsuite/tools/gcalendar.py create "Meeting" "2024-01-15T10:00" "2024-01-15T11:00" --yes

# Create event with explicit timezone
uv run core/skills/gsuite/tools/gcalendar.py create "Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --timezone "America/New_York" --yes

# Create event with attendees and Meet link (include self)
uv run core/skills/gsuite/tools/gcalendar.py create "Team Sync" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "self@example.com,colleague@example.com" --meet --yes

# Create private event (hidden from others)
uv run core/skills/gsuite/tools/gcalendar.py create "Personal" "2024-01-15T10:00" "2024-01-15T11:00" \
  --visibility private --yes

# Create event that shows as free (doesn't block calendar)
uv run core/skills/gsuite/tools/gcalendar.py create "Optional" "2024-01-15T10:00" "2024-01-15T11:00" \
  --show-as free --yes

# Update event (preserves original timezone unless --timezone specified)
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --title "New Title"

# Update event time with explicit timezone
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --start "2024-01-15T11:00" \
  --timezone "America/New_York" --yes

# Add/remove attendees
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --add-attendees "new@example.com" --yes
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --remove-attendees "old@example.com" --yes

# Update visibility and show-as
uv run core/skills/gsuite/tools/gcalendar.py update <event_id> --visibility private --show-as free --yes

# Delete event (requires confirmation)
uv run core/skills/gsuite/tools/gcalendar.py delete <event_id>

# List calendars
uv run core/skills/gsuite/tools/gcalendar.py calendars
```

## Extended API Access (--extra)

For Google Calendar API features not exposed via CLI options, use `--extra`:

- Top-level keys = merged into event body
- `_api` key = API method parameters (e.g., sendUpdates)

### Recurring Events

```bash
# Weekly recurring event
uv run gcalendar.py create "Weekly Standup" "2024-01-15T09:00" "2024-01-15T09:30" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"]}' --yes

# Biweekly on Tuesdays and Thursdays
uv run gcalendar.py create "Biweekly Sync" "2024-01-16T14:00" "2024-01-16T15:00" \
  --extra '{"recurrence": ["RRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH"]}' --yes

# Monthly on first Monday
uv run gcalendar.py create "Monthly Review" "2024-01-01T10:00" "2024-01-01T11:00" \
  --extra '{"recurrence": ["RRULE:FREQ=MONTHLY;BYDAY=1MO"]}' --yes

# Daily for 10 occurrences
uv run gcalendar.py create "Daily Check-in" "2024-01-15T08:00" "2024-01-15T08:15" \
  --extra '{"recurrence": ["RRULE:FREQ=DAILY;COUNT=10"]}' --yes
```

### Custom Reminders

```bash
# 10-minute popup reminder only
uv run gcalendar.py create "Quick Sync" "2024-01-15T10:00" "2024-01-15T10:30" \
  --extra '{"reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 10}]}}' --yes

# Multiple reminders: email 1 day before, popup 30 minutes before
uv run gcalendar.py create "Important Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --extra '{"reminders": {"useDefault": false, "overrides": [{"method": "email", "minutes": 1440}, {"method": "popup", "minutes": 30}]}}' --yes
```

### Attendee Notifications

Use `_api.sendUpdates` to control email notifications when creating/updating events with attendees:

```bash
# Notify all attendees
uv run gcalendar.py create "Team Meeting" "2024-01-15T10:00" "2024-01-15T11:00" \
  --attendees "team@example.com" \
  --extra '{"_api": {"sendUpdates": "all"}}' --yes

# Notify only external attendees
uv run gcalendar.py create "External Call" "2024-01-15T14:00" "2024-01-15T15:00" \
  --attendees "partner@external.com,colleague@example.com" \
  --extra '{"_api": {"sendUpdates": "externalOnly"}}' --yes

# No notifications (silent update)
uv run gcalendar.py update <event_id> --title "Renamed Meeting" \
  --extra '{"_api": {"sendUpdates": "none"}}' --yes
```

### Combined Example

```bash
# Recurring weekly meeting with attendees, custom reminders, and notifications
uv run gcalendar.py create "Weekly 1:1" "2024-01-15T11:00" "2024-01-15T11:30" \
  --attendees "manager@example.com" --meet \
  --extra '{
    "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=MO"],
    "reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 5}]},
    "_api": {"sendUpdates": "all"}
  }' --yes
```
