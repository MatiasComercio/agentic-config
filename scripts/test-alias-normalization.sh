#!/usr/bin/env bash
set -uo pipefail

# Test alias normalization for project types
# Verifies that short aliases map to correct template directories

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_BASE="/tmp/agentic-alias-tests-$$"
PASSED=0
FAILED=0

cleanup() {
  rm -rf "$TEST_BASE" 2>/dev/null || true
}
trap cleanup EXIT

log_pass() {
  echo "[PASS] $1"
  ((PASSED++))
}

log_fail() {
  echo "[FAIL] $1"
  ((FAILED++))
}

# Test alias normalization with dry-run
test_alias() {
  local alias="$1"
  local expected="$2"
  local test_dir="$TEST_BASE/$alias"

  mkdir -p "$test_dir"

  # Run with dry-run to check normalization without side effects
  local output
  output=$("$REPO_ROOT/scripts/setup-config.sh" --type "$alias" --dry-run "$test_dir" 2>&1)
  local exit_code=$?

  # Check exit code (should be 0, not fail with "No template" error)
  if [[ $exit_code -ne 0 ]]; then
    log_fail "$alias -> $expected: Script failed with exit code $exit_code"
    echo "  Output: $output"
    return
  fi

  # Check that it doesn't fail with "No template for project type" error
  if echo "$output" | grep -q "No template for project type"; then
    log_fail "$alias -> $expected: Template lookup failed"
    echo "  Output: $output"
    return
  fi

  log_pass "$alias -> $expected: Alias normalized correctly"
}

# Test that full names still work (backward compatibility)
test_full_name() {
  local type="$1"
  local test_dir="$TEST_BASE/full-$type"

  mkdir -p "$test_dir"

  local output
  output=$("$REPO_ROOT/scripts/setup-config.sh" --type "$type" --dry-run "$test_dir" 2>&1)
  local exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    log_fail "$type (full name): Script failed with exit code $exit_code"
    return
  fi

  if echo "$output" | grep -q "No template for project type"; then
    log_fail "$type (full name): Template lookup failed"
    return
  fi

  log_pass "$type (full name): Works correctly"
}

echo "=== Alias Normalization Tests ==="
echo "Test directory: $TEST_BASE"
echo ""

echo "--- Short Aliases ---"
test_alias "py-uv" "python-uv"
test_alias "py-pip" "python-pip"
test_alias "py-poetry" "python-poetry"
test_alias "ts" "typescript"
test_alias "bun" "ts-bun"

echo ""
echo "--- Full Names (Backward Compatibility) ---"
test_full_name "python-uv"
test_full_name "python-pip"
test_full_name "python-poetry"
test_full_name "typescript"
test_full_name "ts-bun"
test_full_name "rust"
test_full_name "generic"

echo ""
echo "=== Results ==="
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi
echo "All tests passed!"
