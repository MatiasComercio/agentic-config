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
  --model "$MODEL" \
  --thinking "$THINKING" \
  --skill "$SKILL_PATH" \
  --cwd "$PROJECT_ROOT"
```

The wrapper is a foreground supervisor. If the worker should run in the background, use the Bash tool's background mode. Do not add `&`, shell pipelines, redirection, or polling loops to the command string.

## What the wrapper enforces

`pi-bash.py` owns subprocess and artifact safety:

- runs `pi` with `subprocess.run(..., shell=False)`
- passes requested skills to pi with repeatable `--skill` arguments
- writes raw child stdout and stderr to `logs/<agent-id>.{stdout,stderr}.log`
- requires the child process to exit `0`
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
