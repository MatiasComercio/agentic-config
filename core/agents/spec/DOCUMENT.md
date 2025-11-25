# DOCUMENT
STAGE: DOCUMENT
GOAL: Update project documentation reflecting implementation changes.

## Variables
SPEC: $ARGUMENT

## Critical Compliance

- COMMIT ONLY the files you changed.

## Workflow

1. READ `# AI Section > ## Implement` and `## Post-Implement Review` for changes made.
2. IDENTIFY docs needing updates:
   - README.md (if user-facing changes)
   - AGENTS.md (if workflow/rules changed)
   - Testing documentation (if testing approach is significant)
   - Inline code comments (only if logic non-obvious)
3. REFLECT what to update (CONCISELY).
4. UPDATE identified documentation files.
5. APPEND summary to `# AI Section > ## Updated Doc`:
   - Files updated
   - Changes made
6. SUMMARIZE result (max: 100 words).
7. COMMIT with: `spec(NNN): DOCUMENT - <title>`

## Behavior

- MINIMAL changes - only what's necessary.
- NO new docs unless explicitly requested.
- CONCISE. Bullet list format.
