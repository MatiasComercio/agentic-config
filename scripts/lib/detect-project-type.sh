#!/usr/bin/env bash
# Detects project type based on presence of configuration files

detect_project_type() {
  local target_path="$1"

  # Bun indicators (check before typescript for specificity)
  if [[ -f "$target_path/bun.lockb" ]]; then
    echo "ts-bun"
    return 0
  fi

  # TypeScript/Node.js indicators
  if [[ -f "$target_path/package.json" ]]; then
    local pkg_content=$(cat "$target_path/package.json" 2>/dev/null || echo "")
    if echo "$pkg_content" | grep -q "typescript\|@types"; then
      echo "typescript"
      return 0
    fi
  fi

  # Python indicators (prefer poetry over uv over pip)
  if [[ -f "$target_path/pyproject.toml" ]]; then
    local pyproject_content=$(cat "$target_path/pyproject.toml" 2>/dev/null || echo "")
    if echo "$pyproject_content" | grep -q "\[tool.poetry\]"; then
      echo "python-poetry"
      return 0
    fi
  fi

  # Python UV indicators (check before falling back to pip)
  if [[ -f "$target_path/uv.lock" ]]; then
    echo "python-uv"
    return 0
  fi

  # Check pyproject.toml for uv markers
  if [[ -f "$target_path/pyproject.toml" ]]; then
    local pyproject_content=$(cat "$target_path/pyproject.toml" 2>/dev/null || echo "")
    if echo "$pyproject_content" | grep -q "\[tool.uv\]"; then
      echo "python-uv"
      return 0
    fi
  fi

  if [[ -f "$target_path/requirements.txt" ]] || [[ -f "$target_path/setup.py" ]] || [[ -f "$target_path/setup.cfg" ]]; then
    echo "python-pip"
    return 0
  fi

  # Rust indicators
  if [[ -f "$target_path/Cargo.toml" ]]; then
    echo "rust"
    return 0
  fi

  # Go indicators
  if [[ -f "$target_path/go.mod" ]]; then
    echo "go"
    return 0
  fi

  # Default to generic
  echo "generic"
  return 0
}

# Detect Python tooling (type checker and linter) from project config files
# Returns: TYPE_CHECKER=<pyright|mypy> LINTER=<ruff|pylint>
# Priority: pyproject.toml > setup.cfg > requirements*.txt > defaults
detect_python_tooling() {
  local target_path="$1"
  local type_checker=""
  local linter=""

  # Check pyproject.toml for [tool.*] sections
  if [[ -f "$target_path/pyproject.toml" ]]; then
    local pyproject_content
    pyproject_content=$(cat "$target_path/pyproject.toml" 2>/dev/null || echo "")

    # Type checker detection
    if echo "$pyproject_content" | grep -q '\[tool\.pyright\]'; then
      type_checker="pyright"
    elif echo "$pyproject_content" | grep -q '\[tool\.mypy\]'; then
      type_checker="mypy"
    fi

    # Linter detection
    if echo "$pyproject_content" | grep -q '\[tool\.ruff\]'; then
      linter="ruff"
    elif echo "$pyproject_content" | grep -q '\[tool\.pylint\]'; then
      linter="pylint"
    fi
  fi

  # Check setup.cfg if not found in pyproject.toml
  if [[ -f "$target_path/setup.cfg" ]]; then
    local setup_cfg_content
    setup_cfg_content=$(cat "$target_path/setup.cfg" 2>/dev/null || echo "")

    if [[ -z "$type_checker" ]]; then
      if echo "$setup_cfg_content" | grep -q '^\[mypy'; then
        type_checker="mypy"
      fi
    fi

    if [[ -z "$linter" ]]; then
      if echo "$setup_cfg_content" | grep -q '^\[pylint'; then
        linter="pylint"
      fi
    fi
  fi

  # Check requirements*.txt for package presence
  for req_file in "$target_path/requirements"*.txt; do
    [[ ! -f "$req_file" ]] && continue
    local req_content
    req_content=$(cat "$req_file" 2>/dev/null || echo "")

    if [[ -z "$type_checker" ]]; then
      if echo "$req_content" | grep -qE '^pyright[^a-zA-Z]|^pyright$'; then
        type_checker="pyright"
      elif echo "$req_content" | grep -qE '^mypy[^a-zA-Z]|^mypy$'; then
        type_checker="mypy"
      fi
    fi

    if [[ -z "$linter" ]]; then
      if echo "$req_content" | grep -qE '^ruff[^a-zA-Z]|^ruff$'; then
        linter="ruff"
      elif echo "$req_content" | grep -qE '^pylint[^a-zA-Z]|^pylint$'; then
        linter="pylint"
      fi
    fi
  done

  # Apply defaults for any undetected tooling
  [[ -z "$type_checker" ]] && type_checker="pyright"
  [[ -z "$linter" ]] && linter="ruff"

  echo "TYPE_CHECKER=$type_checker LINTER=$linter"
}
