# IMPLEMENT
STAGE: IMPLEMENT
GOAL: IMPLEMENT EXACT step by step PLAN to achieve `SPEC` Objectives aligned with Details, Research & Strategy.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.
- UPDATE progress for each TODO in spec file:
  - BEFORE start task: `In Progress`
  - AFTER finished task: `Done` or `Failed` or any other task completion status

## Workflow

1. READ `# AI Section > ## Plan`
2. REFLECT your understanding and what you will do (CONCISELY).
3. WRITE TODO list in SPEC `# AI Section > ## Implement`. Each TODO item with `Status: Pending`.
4. IMPLEMENT each TODO item SEQUENTIALLY, one at a time. For each TODO item:
   1. UPDATE SPEC file TODO item `Status: In Progress`
   2. IMPLEMENT TODO item
   3. WRITE unit tests for the implemented component/function
   4. UPDATE SPEC file TODO item `Status: Done` or `Failed` or any other task completion status
5. WRITE e2e tests after all implementation tasks complete (if applicable)
6. IF an unexpected error/failure occurs, surface it to the user. If you cannot recover from it, stop and ask user feedback. DO NOT ignore the error/failure.
7. SUMMARIZE result to user in output (max: 150 words).
8. COMMIT implementation, tests, and spec (ONLY the files you changed):
	1. Commit code changes + tests + spec file with task statuses using message: `spec(NNN): IMPLEMENT - <title>`
	2. Update spec with commit hash, placing it clearly at the end of the '# AI Section > ## Implement' section.
	3. Commit spec file again with message: `spec(NNN): IMPLEMENT - <title> [hash]`

## Behavior

- Think hard. Take your time. Be systematic.
- DO NOT ASSUME.
- BE AS PRECISE AND CONCISE as possible. Use the less amount of words without losing accuracy or meaning.
- FORMAT: bullet list.
- SURFACE ERRORS FIRST, in their own section.
