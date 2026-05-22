# Claude Code CLI Worker Wrapper

Status: disabled.

`cc-bash.py launch` is retained as a compatibility stub, but it exits non-zero without launching Claude Code or touching report/signal artifacts.

Reason: Anthropic disabled subscription access to `claude -p`.

Use `pi-bash.py`, Task workers, or pimux-native workers instead. Direct `claude -p ...` and direct `npx @anthropic-ai/claude-code -p ...` remain forbidden in MUX.
