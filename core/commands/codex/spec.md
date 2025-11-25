---
description: Execute /spec workflow stages (RESEARCH, PLAN, IMPLEMENT)
---

# /spec Command

Execute the /spec workflow according to stage instructions in `agents/spec/{STAGE}.md`.

## Usage

```
/spec RESEARCH <spec_path>
/spec PLAN <spec_path>
/spec IMPLEMENT <spec_path>
```

Available stages: RESEARCH, PLAN, IMPLEMENT, REVIEW, VALIDATE, FIX, AMEND

## Instructions

When this command is triggered:
1. RE-READ `./agents/spec/{STAGE}.md` (first argument specifies stage)
2. RE-READ the spec file at SPEC_PATH (second argument)
3. REFLECT on exact steps to take
4. WAIT for user confirmation ("OK")
5. EXECUTE the stage workflow
6. COMMIT ONLY files modified during this stage

Refer to `AGENTS.md` for complete workflow documentation.
