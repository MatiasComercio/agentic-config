# Programmatic pi Worker Wrapper

Use `pi-bash.py` when a MUX coordinator needs to launch a programmatic pi worker while preserving file-based report and signal discipline.

## Core rule

Direct `pi ... -p ...` Bash commands are forbidden in MUX. Launch the wrapper instead:

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
  --skill "$SKILL_PATH" \
  --cwd "$PROJECT_ROOT" \
  --stream
```

Operational default: include `--stream` for MUX launches so the coordinator can watch worker turn/tool events in the background command output. Omit it only for low-noise automation. Startup silence has two separate gates: `--startup-warn-after N` warns, and stream launches default to `--startup-timeout 60` to terminate if no first stdout/stderr line arrives. Extended output silence is also fail-closed: stream launches default to `--idle-timeout 600`, `--startup-timeout N` / `--idle-timeout N` tune the thresholds, and `--startup-timeout 0` / `--idle-timeout 0` disable gates only for explicitly justified cases.

The default tool allowlist is least-privilege for file-protocol workers: `read,write,grep,find,ls`. Bash and Edit are not included unless the caller explicitly overrides `--tools`. The generated worker prompt tells pi to create the signal by writing the signal file content directly, not by running `signal.py` through a shell.

Always make provider, model, and thinking explicit either in the launch command or in `pi-bash.yaml`. Config precedence mirrors the safety config pattern: project `./pi-bash.yaml` > user `~/.claude/pi-bash.yaml` > wrapper `pi-bash.default.yaml`. The bundled default is `openai-codex` / `gpt-5.5` / `xhigh`.

Write or update project defaults with:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/pi-bash.py configure \
  --scope project \
  --provider openai-codex \
  --model gpt-5.5 \
  --thinking xhigh \
  --cwd "$PROJECT_ROOT"
```

If the selected provider is not authenticated, run this in a separate terminal:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/skills/mux/tools/pi-bash.py auth-help --cwd "$PROJECT_ROOT"
```

Then run the shown `pi --provider ... --model ... --thinking ...` command, type `/login`, and select the matching provider. For the bundled default, select ChatGPT Plus/Pro (Codex).

The wrapper is a foreground supervisor. If the worker should run in the background, use the Bash tool's background mode. Do not add `&`, shell pipelines, redirection, or polling loops to the command string.

## What the wrapper enforces

`pi-bash.py` owns subprocess and artifact safety:

- runs `pi` with `subprocess.Popen(..., shell=False, stdin=DEVNULL, start_new_session=True)` in stream and non-stream mode
- passes requested skills to pi with repeatable `--skill` arguments
- always passes explicit `--provider`, `--model`, and `--thinking` to pi, resolved from CLI flags or `pi-bash.yaml`
- with `--stream`, runs pi with `--mode json`
- passes `--offline` to pi by default to avoid startup network checks before first output; `--allow-startup-network` opts out
- writes attempt-scoped logs to `logs/<agent-id>.<attempt-id>.*`
- writes `logs/<agent-id>.latest.json` so retries never overwrite prior evidence
- writes wrapper-side launch diagnostics before child output exists
- with `--stream`, writes sanitized child stdout JSONL to `.events.jsonl`
- with `--stream`, keeps `.stdout.log` lean instead of duplicating JSON events
- with `--stream --raw-events`, additionally writes unsanitized child stdout JSONL to `.raw-events.jsonl`
- with `--stream`, mirrors sanitized child stdout events and raw child stderr to wrapper stderr with a `pi> ` prefix for live viewing
- with `--no-mirror`, suppresses live child output while keeping logs and events
- with `--startup-warn-after`, warns if no first stdout/stderr line arrives before the threshold
- with `--startup-timeout`, fails terminally if no first stdout/stderr line arrives before the threshold
- supervises stream and non-stream children with heartbeat diagnostics, optional runtime/idle timeouts, and sanitized process/session snapshots
- fails terminally on default stream startup/idle timeouts and records failed lifecycle state in `logs/<agent-id>.latest.json`
- defaults to `--no-extensions` with the built-in `read,write,grep,find,ls` allowlist unless explicitly overridden
- keeps Bash and Edit out of the default worker tool set
- bounds stream-reader shutdown after child exit and logs cleanup warnings before protocol validation
- rejects session paths that resolve outside `cwd` or contain parent-directory traversal
- writes logs only under the resolved session directory
- requires declared report and signal paths to resolve inside the resolved session directory
- removes stale declared report and signal files before launch, after path confinement succeeds
- treats the file protocol as authoritative, recording non-zero child exits as diagnostics when protocol validation succeeds
- requires the declared report file to exist
- requires the declared signal file to exist
- requires signal `status: success`
- requires signal `path:` to resolve to the declared report path
- requires report headings for Table of Contents, Executive Summary, and Next Steps
- prints exactly `0` only on protocol-valid success

## What the wrapper does not enforce

`pi-bash.py` is intentionally usable outside MUX. It does not require:

- active MUX session state
- strict runtime ledger state
- a prior `DECLARE`
- a `DECLARE -> DISPATCH` transition
- coordinator-side summary evidence

Those checks are orchestration policy, not wrapper policy.

## Streaming observability

`--stream` exposes pi's native JSON event stream as lean/sanitized JSONL. The wrapper stdout remains reserved for the success protocol and still prints exactly `0` only after validation passes.

During active MUX execution, watch the background Bash task output emitted by the wrapper. Do not poll or tail log files while the worker is active.

After completion, or after an explicit `deactivate.py` for diagnostics, inspect:

```text
<SESSION_DIR>/logs/<agent-id>.<attempt-id>.events.jsonl
<SESSION_DIR>/logs/<agent-id>.<attempt-id>.stdout.log
<SESSION_DIR>/logs/<agent-id>.<attempt-id>.stderr.log
<SESSION_DIR>/logs/<agent-id>.<attempt-id>.wrapper.log
<SESSION_DIR>/logs/<agent-id>.<attempt-id>.raw-events.jsonl  # only with --raw-events
<SESSION_DIR>/logs/<agent-id>.latest.json
```

Use `.events.jsonl` for lean pi turn/tool event history, `.stdout.log` for non-JSON stdout plus stream-mode notes, `.stderr.log` for child stderr plus wrapper diagnostics, `.wrapper.log` for sanitized argv, child PID, heartbeat/snapshot, warning, and exit diagnostics, and `.latest.json` to find the newest attempt. Use `--raw-events` only for explicit forensic debugging because it can be large and may contain provider internals.

## Skill preloading

Use repeatable `--skill` arguments for required skills:

```bash
--skill builder --skill ${CLAUDE_PLUGIN_ROOT}/skills/mux/agents/sentinel.md
```

Rules:

- `--role` is an opaque project-defined role label.
- `--skill` is preload context and may be a skill name or path.
- Name resolution is deterministic and fail-closed.
- Path form is preferred for cookbook agents or project-specific files.
- If a requested skill cannot be resolved or read, the wrapper fails before launching pi.

## Optional strict MUX enforcement

If a coordinator wants declare-before-dispatch enforcement, keep it outside the wrapper:

1. Declare the expected dispatch in coordinator state:
   - role
   - worker type
   - objective
   - scope
   - report path
   - signal path
2. Launch `pi-bash.py` with matching arguments.
3. Wait for the runtime completion notification.
4. Validate the wrapper returned `0`.
5. Extract summary evidence with `extract-summary.py --evidence`.
6. Advance only if report, signal, and summary evidence are all present and consistent.
7. If Claude and pi reviewer/advisor outputs disagree materially, route to explicit adjudication.

This pattern gives strict MUX behavior without making `pi-bash.py` MUX-only.
