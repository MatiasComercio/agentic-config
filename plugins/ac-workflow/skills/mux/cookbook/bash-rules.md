# Bash Restrictions

Orchestrator Bash usage is LIMITED to these EXACT tools.

**Enforcement:** Skill-scoped hook (`mux-orchestrator-guard.py`) validates every Bash command against a whitelist. Non-whitelisted commands are HARD-BLOCKED (denied by hook before execution).

## Allowed Commands

| Command | Purpose |
|---------|---------|
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/session.py` | Create session directory |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/verify.py` | Check signal counts/status |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/signal.py` | Create signals (emergency) |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/check-signals.py` | One-shot signal check (fallback) |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/extract-summary.py` | Bounded report access (TOC + Executive Summary) |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/pi-bash.py launch ...` | Launch supervised programmatic pi worker with file-protocol validation |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/cc-bash.py launch ...` | Launch supervised Claude Code CLI worker with file-protocol validation |
| `uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/agents.py` | List/register agents |
| `mkdir -p` | Create directories |

## Explicit Blocklist (FATAL)

| Command | Violation |
|---------|-----------|
| `npx *` | Runtime execution |
| `npm *` | Package operations |
| `cdk *` | CDK commands |
| `git status` | Repository inspection |
| `git diff` | Content inspection |
| `git log` | History inspection |
| `git show` | Commit inspection |
| `grep` / `rg` | Content search |
| `find` | File search |
| `cat` / `head` / `tail` | File reading |
| `python *` | Script execution |
| `pi *` | Direct programmatic pi execution; use `pi-bash.py` instead |
| `claude *` | Direct Claude Code print-mode execution; use `cc-bash.py` instead |
| `npx @anthropic-ai/claude-code *` | Direct Claude Code package execution; use `cc-bash.py` instead |
| `node *` | Script execution |
| `cargo *` / `go *` | Build commands |
| `make` / `gradle` / `mvn` | Build commands |

## Evidence of Violations (Real Examples)

```bash
# FATAL - orchestrator ran CDK directly
npx cdk synth SdcStack

# FATAL - orchestrator inspected git
git status --porcelain | head -30

# FATAL - orchestrator ran grep
grep -rn "pattern" --include="*.md"

# FATAL - orchestrator launched pi directly instead of using the wrapper
pi --provider "$PROVIDER" --model "$MODEL" --thinking "$THINKING" -p "$PROMPT"

# FATAL - orchestrator launched Claude Code directly instead of using the wrapper
claude --model "$MODEL" -p "$PROMPT"
npx @anthropic-ai/claude-code --model "$MODEL" -p "$PROMPT"
```

## Correct Delegation

```python
# CDK validation -> agent with skill
Task(prompt="Invoke /build-validate skill.", model="sonnet", run_in_background=True)

# Git inspection -> sentinel
Task(prompt="Read ${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/sentinel.md. Check git status.", model="sonnet", run_in_background=True)

# Pattern search -> auditor
Task(prompt="Read ${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/auditor.md. Search for pattern.", model="sonnet", run_in_background=True)
```

## Programmatic CLI Workers

Direct `pi ... -p ...`, `claude -p ...`, and `npx @anthropic-ai/claude-code -p ...` Bash commands remain blocked. Use a wrapper when a MUX wave needs a programmatic CLI worker.

For pi workers:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/pi-bash.py launch \
  "$SESSION_DIR" "$AGENT_ID" \
  --role "$ROLE" \
  --worker-type "$WORKER_TYPE" \
  --objective "$OBJECTIVE" \
  --scope "$SCOPE" \
  --task "$TASK" \
  --report-path "$REPORT_PATH" \
  --signal-path "$SIGNAL_PATH" \
  --provider "$PROVIDER" \
  --model "$MODEL" \
  --thinking "$THINKING" \
  --cwd "$PROJECT_ROOT" \
  --stream
```

For Claude Code CLI workers:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/cc-bash.py launch \
  "$SESSION_DIR" "$AGENT_ID" \
  --role "$ROLE" \
  --worker-type "$WORKER_TYPE" \
  --objective "$OBJECTIVE" \
  --scope "$SCOPE" \
  --task "$TASK" \
  --report-path "$REPORT_PATH" \
  --signal-path "$SIGNAL_PATH" \
  --model "$MODEL" \
  --permission-mode "$PERMISSION_MODE" \
  --cwd "$PROJECT_ROOT" \
  --stream
```

Operational default: include `--stream` for wrapper launches so live child JSONL events appear in the background Bash task output. Omit it only for low-noise or legacy automation. `pi-bash.py` stream launches fail closed after 600 seconds without child stdout/stderr unless the coordinator passes an explicit `--idle-timeout` override.

`pi-bash.py` and `cc-bash.py` validate the declared report and signal files after the child process exits. They do not require an active MUX ledger session; declare-before-dispatch matching is coordinator policy. With `--stream`, they also persist raw child stdout events to `<SESSION_DIR>/logs/<agent-id>.events.jsonl` and mirror child stdout/stderr to wrapper stderr for live viewing. During active MUX execution, watch the background command output instead of tailing logs; after completion or explicit `deactivate.py`, inspect the events, stdout, and stderr logs for diagnostics. See `pi-bash.md` and `cc-bash.md` for optional strict orchestration guidance.

## Hook Whitelist Patterns

The orchestrator hook (`mux-orchestrator-guard.py`) enforces these regex patterns:

```python
BASH_WHITELIST_PATTERNS = [
    r"^mkdir\s+-p\s+",                          # Create directories
    r"^uv\s+run\s+\${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/pi-bash\.py\s+launch\b",  # pi worker wrapper
    r"^uv\s+run\s+\${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/cc-bash\.py\s+launch\b",  # Claude Code worker wrapper
    r"^uv\s+run\s+.*tools/",                    # Any tools/ invocation
    r"^uv\s+run\s+\${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/",  # MUX skill tools (explicit)
]
```

Any command not matching these patterns is DENIED by the hook before execution.

## Rationale

- Every bash command beyond tools/ pollutes context
- "Quick checks" become habit, eroding discipline
- If it's worth checking, it's worth delegating
- **When context is full, your session dies**
- Hook enforcement makes violations impossible, not just discouraged
