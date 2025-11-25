---
description: Spawn a subagent with specified model and task
argument-hint: <model> <task>
project-agnostic: true
allowed-tools:
  - Task
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - SlashCommand
---

# Spawn

SPAWN SUBAGENT {MODEL} with `Think Hard` enabled and the exact prompt: {TASK}
INSTRUCT SUBAGENT to report back an MD summary of what was accomplished along with any errors or issues that may have occurred, plus extra notes.
ASSESS the SUBAGENT completion and performance, acting as its manager. If necessary, spawn a new subagent to FIX / IMPROVE the situation. Inform the user before doing so (DO NOT wait his response unless necessary for options tool call for user input).
REPORT the SUBAGENTS results back to the user, along with your assessment.

## CRITICAL

When TASK includes `/spec <STAGE>`, VALIDATE commit message matches `spec(NNN): <STAGE> - <title>` before reporting success. If missing/wrong, spawn fix agent.

## VARIABLES

MODEL=$1 (opus, sonnet, or haiku - defaults to current session model if not specified)
TASK=$ARGUMENTS (everything after model)
