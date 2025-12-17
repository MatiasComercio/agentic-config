#!/usr/bin/env bash
set -uo pipefail

# Test Python tooling variants for python-pip template
# Tests: 4 variant combinations + autodetection scenarios

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_BASE="/tmp/agentic-tooling-tests-$$"
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

# Test a specific variant combination
test_variant() {
  local name="$1"
  local type_checker="$2"
  local linter="$3"
  local test_dir="$TEST_BASE/$name"

  mkdir -p "$test_dir"
  touch "$test_dir/requirements.txt"  # Make it python-pip

  "$REPO_ROOT/scripts/setup-config.sh" --force \
    --type-checker "$type_checker" \
    --linter "$linter" \
    "$test_dir" >/dev/null 2>&1

  local agents_content
  agents_content=$(cat "$test_dir/AGENTS.md")

  # Check type checker
  if echo "$agents_content" | grep -q "Type Checking.*$type_checker"; then
    log_pass "$name: Type checker is $type_checker"
  else
    log_fail "$name: Type checker should be $type_checker"
  fi

  # Check linter
  if echo "$agents_content" | grep -q "$linter"; then
    log_pass "$name: Linter is $linter"
  else
    log_fail "$name: Linter should be $linter"
  fi
}

# Test autodetection from pyproject.toml
test_autodetect_pyproject() {
  local name="autodetect-pyproject"
  local test_dir="$TEST_BASE/$name"

  mkdir -p "$test_dir"
  touch "$test_dir/requirements.txt"
  cat > "$test_dir/pyproject.toml" <<'EOF'
[tool.mypy]
strict = true

[tool.pylint]
max-line-length = 100
EOF

  "$REPO_ROOT/scripts/setup-config.sh" --force "$test_dir" >/dev/null 2>&1

  local agents_content
  agents_content=$(cat "$test_dir/AGENTS.md")

  if echo "$agents_content" | grep -q "Type Checking.*mypy"; then
    log_pass "$name: Detected mypy from pyproject.toml"
  else
    log_fail "$name: Should detect mypy from pyproject.toml"
  fi

  if echo "$agents_content" | grep -q "pylint"; then
    log_pass "$name: Detected pylint from pyproject.toml"
  else
    log_fail "$name: Should detect pylint from pyproject.toml"
  fi
}

# Test autodetection from setup.cfg
test_autodetect_setup_cfg() {
  local name="autodetect-setup-cfg"
  local test_dir="$TEST_BASE/$name"

  mkdir -p "$test_dir"
  touch "$test_dir/requirements.txt"
  cat > "$test_dir/setup.cfg" <<'EOF'
[mypy]
strict = True

[pylint.messages_control]
disable = C0114
EOF

  "$REPO_ROOT/scripts/setup-config.sh" --force "$test_dir" >/dev/null 2>&1

  local agents_content
  agents_content=$(cat "$test_dir/AGENTS.md")

  if echo "$agents_content" | grep -q "Type Checking.*mypy"; then
    log_pass "$name: Detected mypy from setup.cfg"
  else
    log_fail "$name: Should detect mypy from setup.cfg"
  fi

  if echo "$agents_content" | grep -q "pylint"; then
    log_pass "$name: Detected pylint from setup.cfg"
  else
    log_fail "$name: Should detect pylint from setup.cfg"
  fi
}

# Test autodetection from requirements.txt
test_autodetect_requirements() {
  local name="autodetect-requirements"
  local test_dir="$TEST_BASE/$name"

  mkdir -p "$test_dir"
  cat > "$test_dir/requirements.txt" <<'EOF'
flask==2.0.0
mypy>=1.0
ruff>=0.1.0
EOF

  "$REPO_ROOT/scripts/setup-config.sh" --force "$test_dir" >/dev/null 2>&1

  local agents_content
  agents_content=$(cat "$test_dir/AGENTS.md")

  if echo "$agents_content" | grep -q "Type Checking.*mypy"; then
    log_pass "$name: Detected mypy from requirements.txt"
  else
    log_fail "$name: Should detect mypy from requirements.txt"
  fi

  if echo "$agents_content" | grep -q "ruff"; then
    log_pass "$name: Detected ruff from requirements.txt"
  else
    log_fail "$name: Should detect ruff from requirements.txt"
  fi
}

# Test defaults when no config exists
test_defaults() {
  local name="defaults"
  local test_dir="$TEST_BASE/$name"

  mkdir -p "$test_dir"
  touch "$test_dir/requirements.txt"  # Empty file, no tooling config

  "$REPO_ROOT/scripts/setup-config.sh" --force "$test_dir" >/dev/null 2>&1

  local agents_content
  agents_content=$(cat "$test_dir/AGENTS.md")

  if echo "$agents_content" | grep -q "Type Checking.*pyright"; then
    log_pass "$name: Default type checker is pyright"
  else
    log_fail "$name: Default type checker should be pyright"
  fi

  if echo "$agents_content" | grep -q "ruff check"; then
    log_pass "$name: Default linter is ruff"
  else
    log_fail "$name: Default linter should be ruff"
  fi
}

# Test CLI override of autodetection
test_cli_override() {
  local name="cli-override"
  local test_dir="$TEST_BASE/$name"

  mkdir -p "$test_dir"
  touch "$test_dir/requirements.txt"
  cat > "$test_dir/pyproject.toml" <<'EOF'
[tool.mypy]
strict = true
EOF

  # CLI should override autodetected mypy with pyright
  "$REPO_ROOT/scripts/setup-config.sh" --force \
    --type-checker pyright \
    "$test_dir" >/dev/null 2>&1

  local agents_content
  agents_content=$(cat "$test_dir/AGENTS.md")

  if echo "$agents_content" | grep -q "Type Checking.*pyright"; then
    log_pass "$name: CLI override works (pyright over autodetected mypy)"
  else
    log_fail "$name: CLI should override autodetection"
  fi
}

echo "=== Python Tooling Variant Tests ==="
echo "Test directory: $TEST_BASE"
echo ""

# Run all tests
echo "--- Variant Combinations ---"
test_variant "pyright-ruff" "pyright" "ruff"
test_variant "pyright-pylint" "pyright" "pylint"
test_variant "mypy-ruff" "mypy" "ruff"
test_variant "mypy-pylint" "mypy" "pylint"

echo ""
echo "--- Autodetection ---"
test_autodetect_pyproject
test_autodetect_setup_cfg
test_autodetect_requirements
test_defaults
test_cli_override

echo ""
echo "=== Results ==="
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [[ $FAILED -gt 0 ]]; then
  exit 1
fi
echo "All tests passed!"
