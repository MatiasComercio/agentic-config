# Claude Code CLI Worker Wrapper

Use `cc-bash.py` when a MUX coordinator needs to launch a Claude Code print-mode worker while preserving file-based report and signal discipline.

## Core rule

Direct `claude -p ...` and `npx @anthropic-ai/claude-code -p ...` Bash commands are forbidden in MUX. Launch the wrapper instead:

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
  --allowed-tool "Read" \
  --allowed-tool "Write" \
  --allowed-tool "Edit" \
  --disallowed-tool "Task" \
  --skill "$SKILL_PATH" \
  --cwd "$PROJECT_ROOT" \
  --stream
```

Operational default: include `--stream` for MUX launches so the coordinator can watch worker turn/tool events in the background command output. Omit it only for low-noise automation. Startup silence is warning-only; use `--startup-warn-after N` to tune or disable that diagnostic.

The wrapper is a foreground supervisor. If the worker should run in the background, use the Bash tool's background mode. Do not add `&`, shell pipelines, redirection, or polling loops to the command string.

## Command resolution

`cc-bash.py` resolves the Claude Code command in this order:

1. Use `claude` if it is resolvable on `PATH`.
2. Otherwise fall back to `npx @anthropic-ai/claude-code`.

The concrete fallback may include `npx -y` to avoid an interactive package-install confirmation prompt.

## What the wrapper enforces

`cc-bash.py` owns subprocess and artifact safety:

- runs Claude Code with `subprocess.run(..., shell=False)` in non-stream mode
- uses Claude Code print mode with `-p`
- appends skill preload context through `--append-system-prompt` instead of replacing the default system prompt
- with `--stream`, forces `--output-format stream-json --verbose`
- writes raw child stdout and stderr to `logs/<agent-id>.{stdout,stderr}.log` in non-stream mode
- writes wrapper-side launch diagnostics to `logs/<agent-id>.wrapper.log` before child output exists
- with `--stream`, writes sanitized child stdout JSONL to `logs/<agent-id>.events.jsonl`
- with `--stream`, keeps `logs/<agent-id>.stdout.log` lean instead of duplicating JSON events
- with `--stream --raw-events`, additionally writes unsanitized child stdout JSONL to `logs/<agent-id>.raw-events.jsonl`
- with `--stream`, mirrors sanitized child stdout events and raw child stderr to wrapper stderr with a `cc> ` prefix for live viewing
- with `--no-mirror`, suppresses live child output while keeping logs and events
- with `--startup-warn-after`, warns if no first stdout/stderr line arrives before the threshold without killing the child
- with `--stream`, bounds stream-reader shutdown after child exit and logs cleanup warnings before protocol validation
- removes stale declared report and signal files before launch
- treats the file protocol as authoritative, recording non-zero child exits as diagnostics when protocol validation succeeds
- requires the declared report file to exist
- requires the declared signal file to exist
- requires signal `status: success`
- requires signal `path:` to resolve to the declared report path
- requires report headings for Table of Contents, Executive Summary, and Next Steps
- prints exactly `0` only on protocol-valid success

## What the wrapper does not enforce

`cc-bash.py` is intentionally usable outside MUX. It does not require:

- active MUX session state
- strict runtime ledger state
- a prior `DECLARE`
- a `DECLARE -> DISPATCH` transition
- coordinator-side summary evidence

Those checks are orchestration policy, not wrapper policy.

## Streaming observability

`--stream` exposes Claude Code's native `stream-json` event stream without normalizing or rewriting events. It overrides any explicit `--output-format` value and adds Claude Code's required `--verbose` flag. The wrapper stdout remains reserved for the success protocol and still prints exactly `0` only after validation passes.

During active MUX execution, watch the background Bash task output emitted by the wrapper. Do not poll or tail log files while the worker is active.

After completion, or after an explicit `deactivate.py` for diagnostics, inspect:

```text
<SESSION_DIR>/logs/<agent-id>.events.jsonl
<SESSION_DIR>/logs/<agent-id>.stdout.log
<SESSION_DIR>/logs/<agent-id>.stderr.log
<SESSION_DIR>/logs/<agent-id>.wrapper.log
<SESSION_DIR>/logs/<agent-id>.raw-events.jsonl  # only with --raw-events
```

Use `.events.jsonl` for lean Claude Code stream events, `.stdout.log` for non-JSON stdout plus stream-mode notes, `.stderr.log` for child stderr and wrapper diagnostics, and `.wrapper.log` for sanitized argv, child PID, warning, and exit diagnostics. Use `--raw-events` only for explicit forensic debugging because it can be large and may contain provider internals.

## Skill preloading

Claude Code does not expose the same `--skill <path>` CLI preload flag as pi. `cc-bash.py` accepts repeatable `--skill` arguments, resolves them before launch, and appends their content to Claude Code's default system prompt with `--append-system-prompt`.

Rules:

- `--role` is an opaque project-defined role label.
- `--skill` is preload context and may be a skill name or path.
- Name resolution is deterministic and fail-closed.
- Path form is preferred for cookbook agents or project-specific files.
- If a requested skill cannot be resolved or read, the wrapper fails before launching Claude Code.
- The wrapper must not use `--system-prompt` by default.

## Optional strict MUX enforcement

If a coordinator wants declare-before-dispatch enforcement, keep it outside the wrapper:

1. Declare the expected dispatch in coordinator state:
   - role
   - worker type
   - objective
   - scope
   - report path
   - signal path
2. Launch `cc-bash.py` with matching arguments.
3. Wait for the runtime completion notification.
4. Validate the wrapper returned `0`.
5. Extract summary evidence with `extract-summary.py --evidence`.
6. Advance only if report, signal, and summary evidence are all present and consistent.
7. If Claude Code CLI and another harness disagree materially, route to explicit adjudication.

This pattern gives strict MUX behavior without making `cc-bash.py` MUX-only.
