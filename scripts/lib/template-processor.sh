#!/usr/bin/env bash
# Processes template files with variable substitution

process_template() {
  local template_file="$1"
  local output_file="$2"

  if [[ ! -f "$template_file" ]]; then
    echo "🔴 ERROR: Template not found: $template_file" >&2
    return 1
  fi

  # Simple copy for now (no variable substitution needed in current templates)
  # Future enhancement: add sed/awk for {{VARIABLE}} substitution
  cp "$template_file" "$output_file"

  return 0
}
