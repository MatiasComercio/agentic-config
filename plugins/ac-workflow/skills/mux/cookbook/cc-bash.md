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

Operational default: include `--stream` for MUX launches so the coordinator can watch worker turn/tool events in the background command output. Omit it only for low-noise or legacy automation.

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
- writes raw child stdout and stderr to `logs/<agent-id>.{stdout,stderr}.log`
- with `--stream`, also writes raw child stdout JSONL to `logs/<agent-id>.events.jsonl`
- with `--stream`, mirrors child stdout and stderr to wrapper stderr for live viewing
- removes any stale declared signal before launch
- requires the child process to exit `0`
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
```

Use `.events.jsonl` for raw Claude Code stream events, `.stdout.log` for the same raw child stdout, and `.stderr.log` for child stderr.

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
