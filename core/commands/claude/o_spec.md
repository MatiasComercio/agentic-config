# E2E Spec Orchestrator: SPEC=<spec_path>|<inline_prompt>

# TASK

IMPLEMENT PRODUCTION-READY full autonomous end-to-end features/fixes/chores leveraging spec workflow with multi-agent orchestrator management skills.

# ROLE & BEHAVIOR

- INVOKE `agent-orchestrator-manager` skill.
- PROCEED autonomously without waiting for user confirmation unless explicitly requested by the user or a decision needs to be made that you cannot make yourself.
- ALWAYS execute the ENTIRE WORKFLOW, EVEN if SPEC is an inline_prompt.
- ENSURE EACH AGENT IN EACH STEP COMMITS ITS CORRESPONDING CHANGES TRACING PROGRESS IN GIT HISTORY.
    - PREPEND each commit message with `spec(NNN):`
- NO MVP APPROACHES/PLACEHOLDERS/later TODOs are allowed. EVERY implementation MUST be production-ready.
    - PENALIZE AGENTS who DON'T OBEY this.

## CRITICAL RULES

- ONLY use `/spec <STAGE> <path>` commands - NEVER invent custom instructions
- Format: `/spawn <model> "/spec <STAGE> <path> [ultrathink]"` - NOTHING ELSE
- DEFINE CORRECT spec path for spec creation using `specs/<YYYY>/<MM>/<branch>/<NNN>-<title>.md`. PRIORITIZE using the spec path used in RECENT commits (branch).

# VARIABLES

SPEC=$ARGUMENTS

- NOTE: SPEC may be a file OR an inline-prompt.

# WORKFLOW

EXECUTE SEQUENTIALLY:
1. /spawn opus "/spec CREATE {SPEC}" (SKIP if spec file exists)
2. /spawn opus "/spec RESEARCH {SPEC} ultrathink"
3. /spawn opus "/spec PLAN {SPEC} ultrathink"
4. /spawn opus "/spec PLAN_REVIEW {SPEC} ultrathink"
5. /spawn sonnet "/spec IMPLEMENT {SPEC} ultrathink"
6. /spawn opus "/spec REVIEW {SPEC} ultrathink"
7. /spawn sonnet "/spec TEST {SPEC}"
8. /spawn sonnet "/spec DOCUMENT {SPEC}"

# REPORT

REPORT PROGRESSIVE CONCISE YET INSIGHTFUL updates to me, your manager, as you progress through the workflow

# CONTROLS

- IF I interrupt your worflow execution, I may use the word `resume ...` or `resume from step X ...`/`resume X ...`, which indicates you need to continue from where we left off before the interruption OR from the specific step number indicated by `X`

# NOTES

