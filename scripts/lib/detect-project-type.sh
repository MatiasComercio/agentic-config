#!/usr/bin/env bash
# Detects project type based on presence of configuration files

detect_project_type() {
  local target_path="$1"

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
