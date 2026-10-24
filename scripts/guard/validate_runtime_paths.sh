#!/usr/bin/env bash
# Source from the project root before creating directories or starting Python.
project_root="$(pwd -P)"
for path_name in RUN_DIR TMPDIR TMP TEMP XDG_CACHE_HOME PIP_CACHE_DIR PLAYWRIGHT_BROWSERS_PATH PYTHONPYCACHEPREFIX; do
  resolved_path="$(realpath -m -- "${!path_name}")"
  case "$resolved_path" in
    "$project_root"/*) ;;
    *)
      printf '%s must resolve to a directory inside the project\n' "$path_name" >&2
      exit 2
      ;;
  esac
done
