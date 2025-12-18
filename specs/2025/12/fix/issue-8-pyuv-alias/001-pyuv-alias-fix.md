# Spec: Fix py-uv alias not mapping to python-uv template

## Human

### Problem

GitHub Issue #8: The setup script accepts `py-uv` as an alias but doesn't normalize it to `python-uv` before template lookup, causing "No template for project type: py-uv" error.

### Root Cause

In `scripts/setup-config.sh`:
- Line 60 shows `py-uv` as a valid option in usage text
- Line 189-194 validates template directory existence using PROJECT_TYPE directly
- No normalization occurs between user input and template lookup
- Template directory is named `python-uv` (not `py-uv`)

### Expected Behavior

`setup-config.sh --type py-uv` should normalize to `python-uv` and use the python-uv template.

### Solution

Add alias normalization logic after PROJECT_TYPE is set (after line 163) to map short aliases to full template names:
- `ts` -> `typescript`
- `py-poetry` -> `python-poetry`
- `py-pip` -> `python-pip`
- `py-uv` -> `python-uv`

### Files to Modify

- `scripts/setup-config.sh`

### Test Plan

- Run `./scripts/setup-config.sh --type py-uv --dry-run /tmp/test-project`
- Verify it resolves to python-uv template
- Verify other aliases work: ts, py-poetry, py-pip
- Verify full names still work: typescript, python-uv, etc.

### Closes

#8

---

## AI

### RESEARCH

Status: pending

### PLAN

Status: completed

## Plan

### Files

- scripts/setup-config.sh
  - Lines 163-186: Add alias normalization block after PROJECT_TYPE assignment (line 163)
  - Normalize: ts->typescript, py-poetry->python-poetry, py-pip->python-pip, py-uv->python-uv

### Tasks

#### Task 1 - Add alias normalization after PROJECT_TYPE assignment

Tools: Edit

Description: Insert normalization block after line 163 (after PROJECT_TYPE is set, before auto-detection of Python tooling) to map short aliases to full template directory names.

Diff:
````diff
--- a/scripts/setup-config.sh
+++ b/scripts/setup-config.sh
@@ -163,6 +163,18 @@ else
   echo "   Type: $PROJECT_TYPE"
 fi

+# Normalize project type aliases to full template names
+case "$PROJECT_TYPE" in
+  ts)
+    PROJECT_TYPE="typescript"
+    ;;
+  py-poetry|py-pip|py-uv)
+    # Map py-* aliases to python-* template names
+    PROJECT_TYPE="python-${PROJECT_TYPE#py-}"
+    ;;
+  # All other types pass through unchanged (typescript, python-poetry, python-pip, python-uv, rust, generic)
+esac
+
 # Auto-detect Python tooling for python-pip projects
 if [[ "$PROJECT_TYPE" == "python-pip" ]]; then
   # Save CLI-provided values
````

Verification:
- Visually inspect lines 163-177 in setup-config.sh to confirm normalization block is present
- Ensure case statement handles all aliases: ts, py-poetry, py-pip, py-uv

#### Task 2 - Test all aliases with dry-run

Tools: Bash

Description: Execute dry-run tests for all aliases (py-uv, ts, py-poetry, py-pip) and full names (python-uv, typescript, python-poetry, python-pip) to verify normalization works correctly.

Commands:
````bash
# Create test directory
mkdir -p /tmp/test-agentic-alias

# Test py-uv alias (the reported issue)
scripts/setup-config.sh --type py-uv --dry-run /tmp/test-agentic-alias

# Test ts alias
scripts/setup-config.sh --type ts --dry-run /tmp/test-agentic-alias

# Test py-poetry alias
scripts/setup-config.sh --type py-poetry --dry-run /tmp/test-agentic-alias

# Test py-pip alias
scripts/setup-config.sh --type py-pip --dry-run /tmp/test-agentic-alias

# Test full name python-uv (should still work)
scripts/setup-config.sh --type python-uv --dry-run /tmp/test-agentic-alias

# Test full name typescript (should still work)
scripts/setup-config.sh --type typescript --dry-run /tmp/test-agentic-alias

# Cleanup
rm -rf /tmp/test-agentic-alias
````

Verification:
- All commands should complete successfully without "No template for project type" errors
- Each command should show correct Type in output (e.g., py-uv normalizes to python-uv)
- Exit codes should all be 0

#### Task 3 - Commit changes

Tools: Bash (git)

Description: Commit the modified setup-config.sh file with conventional commit message.

Commands:
````bash
# Verify we're not on main branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" == "main" ]; then
  echo "ERROR: Cannot commit on main branch" >&2
  exit 1
fi

# Stage only the modified file
git add scripts/setup-config.sh

# Create commit
git commit -m "$(cat <<'EOF'
fix(setup): normalize project type aliases before template lookup

Add normalization logic to map short aliases to full template names:
- ts -> typescript
- py-poetry -> python-poetry
- py-pip -> python-pip
- py-uv -> python-uv

Fixes #8

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"

# Verify commit was created
git log -1 --oneline
````

Verification:
- Commit is created successfully
- Only scripts/setup-config.sh is included in commit
- Commit is not on main branch

### Validate

Requirements validation against Human Section:

1. **L8: Fix "No template for project type: py-uv" error** - Task 1 adds normalization to convert py-uv to python-uv before template lookup
2. **L13-14: No normalization occurs between user input and template lookup** - Task 1 adds explicit normalization case statement
3. **L19: setup-config.sh --type py-uv should normalize to python-uv** - Task 1 handles this via py-* alias pattern matching
4. **L23-27: Map all aliases** - Task 1 normalizes all four aliases: ts, py-poetry, py-pip, py-uv
5. **L31: Modify setup-config.sh** - Task 1 edits this file only
6. **L35-38: Test all aliases and full names** - Task 2 tests all aliases and full names with dry-run
7. **L42: Closes #8** - Task 3 commit message includes "Fixes #8"

### IMPLEMENT

Status: completed

Task 1 completed: Added alias normalization block at lines 165-175 in setup-config.sh. The case statement maps:
- ts -> typescript
- py-poetry -> python-poetry
- py-pip -> python-pip
- py-uv -> python-uv

All other types pass through unchanged.

### TEST

Status: completed

All alias tests passed successfully:
- py-uv -> python-uv (FIXED - original issue)
- ts -> typescript
- py-poetry -> python-poetry
- py-pip -> python-pip
- python-uv (full name still works)
- typescript (full name still works)

All commands completed with exit code 0 and correct template resolution. No "No template for project type" errors occurred.

### REVIEW

Status: completed

Implementation verification:
- Lines 165-175: Normalization block added correctly after PROJECT_TYPE assignment
- Case statement handles all 4 aliases: ts, py-poetry, py-pip, py-uv
- String manipulation ${PROJECT_TYPE#py-} correctly strips "py-" prefix
- Other project types pass through unchanged
- Placement is optimal: after type detection, before template validation
- No breaking changes: full template names still work
- Minimal impact: only 12 lines added, single responsibility

Requirements validation (Human Section):
- Issue #8 resolved: py-uv now maps to python-uv template
- All aliases normalized before template lookup
- Test plan executed successfully with all aliases and full names
- Only setup-config.sh modified as specified

## Test Evidence & Outputs

### Existing Project Tests

Ran: `scripts/test-python-tooling-variants.sh`

Status: PASS (17/17 tests passed, 0 failed)

Verified:
- All Python tooling variant combinations work correctly
- Autodetection logic remains functional
- Default tooling assignments unchanged
- CLI overrides function properly

No regressions introduced by alias normalization changes.

### Alias Normalization Tests

Commands run (all with --dry-run):

1. `setup-config.sh --type py-uv` - PASS (normalizes to python-uv)
2. `setup-config.sh --type ts` - PASS (normalizes to typescript)
3. `setup-config.sh --type py-poetry` - PASS (normalizes to python-poetry)
4. `setup-config.sh --type py-pip` - PASS (normalizes to python-pip)
5. `setup-config.sh --type python-uv` - PASS (full name unchanged)
6. `setup-config.sh --type typescript` - PASS (full name unchanged)

All tests completed successfully with exit code 0. No "No template for project type" errors.

Fix verification:
- Original issue (#8) resolved: py-uv now correctly maps to python-uv template
- All aliases normalize before template lookup
- Full template names pass through unchanged (no breaking changes)

Fix cycles: 0 (no code fixes required, all tests passed on first run)

### DOCUMENT

Status: completed

Documentation updates:

None required - this is a bug fix that restores advertised functionality (py-uv alias support). The usage text already documented py-uv as a valid option, and the fix simply ensures the implementation matches the documentation.

No CHANGELOG entry needed - this fixes broken functionality rather than adding new features. The fix will be included in the next release notes as a bug fix closing issue #8.
