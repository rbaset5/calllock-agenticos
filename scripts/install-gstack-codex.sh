#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install a Codex-native gstack checkout under ~/.codex/skills.

Usage:
  scripts/install-gstack-codex.sh [--dest PATH] [--ref REF] [--repo-url URL] [--force] [--no-setup]

Options:
  --dest PATH      Install destination. Defaults to ${CODEX_HOME:-~/.codex}/skills/gstack
  --ref REF        Git ref to clone. Defaults to main
  --repo-url URL   Source repository URL. Defaults to https://github.com/garrytan/gstack.git
  --force          Remove an existing destination before reinstalling
  --no-setup       Skip ./setup after patching
  -h, --help       Show this help text
EOF
}

die() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

ensure_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

select_utf8_locale() {
  local current="${LC_ALL:-${LANG:-}}"
  if [ -n "$current" ] && locale -a 2>/dev/null | grep -qx "$current"; then
    printf '%s\n' "$current"
    return
  fi

  for candidate in en_US.UTF-8 C.UTF-8 UTF-8; do
    if locale -a 2>/dev/null | grep -qx "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  locale -a 2>/dev/null | awk '/UTF-8$/ { print; exit }'
}

write_codex_patch_script() {
  local patch_script="$1"

  cat >"$patch_script" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(pwd)}"
[ -d "$ROOT" ] || {
  printf 'Error: missing gstack root: %s\n' "$ROOT" >&2
  exit 1
}

select_utf8_locale() {
  local current="${LC_ALL:-${LANG:-}}"
  if [ -n "$current" ] && locale -a 2>/dev/null | grep -qx "$current"; then
    printf '%s\n' "$current"
    return
  fi

  for candidate in en_US.UTF-8 C.UTF-8 UTF-8; do
    if locale -a 2>/dev/null | grep -qx "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  locale -a 2>/dev/null | perl -ne 'print if /UTF-8$/ && ++$c == 1'
}

LOCALE_VALUE="$(select_utf8_locale)"
if [ -n "$LOCALE_VALUE" ]; then
  export LC_ALL="$LOCALE_VALUE"
  export LANG="$LOCALE_VALUE"
  export LC_CTYPE="$LOCALE_VALUE"
fi

python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()

if (root / "CLAUDE.md").is_file() and not (root / "AGENTS.md").exists():
    (root / "AGENTS.md").write_text((root / "CLAUDE.md").read_text(), encoding="utf-8")

replacements = [
    ("$HOME/.claude/skills", "$HOME/.codex/skills"),
    ("~/.claude/skills", "~/.codex/skills"),
    (".claude/skills", ".codex/skills"),
    ("CLAUDE.md", "AGENTS.md"),
    ("Claude Code", "Codex"),
]

allowed_names = {"setup"}
allowed_suffixes = {".md", ".tmpl", ".ts", ".json"}

for path in root.rglob("*"):
    if not path.is_file():
        continue
    if any(part in {".git", "node_modules", "dist"} for part in path.parts):
        continue
    if path.name not in allowed_names and path.suffix not in allowed_suffixes and "bin" not in path.parts:
        continue

    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    updated = original
    for before, after in replacements:
        updated = updated.replace(before, after)

    if updated != original:
        path.write_text(updated, encoding="utf-8")
PY
EOF

  chmod +x "$patch_script"
}

REPO_URL="https://github.com/garrytan/gstack.git"
REF="main"
FORCE=0
RUN_SETUP=1
DEST=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dest)
      [ "$#" -ge 2 ] || die "--dest requires a value"
      DEST="$2"
      shift 2
      ;;
    --ref)
      [ "$#" -ge 2 ] || die "--ref requires a value"
      REF="$2"
      shift 2
      ;;
    --repo-url)
      [ "$#" -ge 2 ] || die "--repo-url requires a value"
      REPO_URL="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --no-setup)
      RUN_SETUP=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

ensure_command git
ensure_command bun
ensure_command locale
ensure_command python3

LOCALE_VALUE="$(select_utf8_locale)"
if [ -n "$LOCALE_VALUE" ]; then
  export LC_ALL="$LOCALE_VALUE"
  export LANG="$LOCALE_VALUE"
  export LC_CTYPE="$LOCALE_VALUE"
fi

CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SKILLS_DIR="$CODEX_HOME_DIR/skills"
DEST="${DEST:-$SKILLS_DIR/gstack}"

mkdir -p "$(dirname "$DEST")"

if [ -e "$DEST" ]; then
  if [ "$FORCE" -ne 1 ]; then
    die "Destination already exists: $DEST (use --force to replace it)"
  fi
  rm -rf "$DEST"
fi

git clone --depth 1 --branch "$REF" "$REPO_URL" "$DEST"
write_codex_patch_script "$DEST/bin/codex-patch"
"$DEST/bin/codex-patch" "$DEST"

if [ "$RUN_SETUP" -eq 1 ]; then
  (
    cd "$DEST"
    ./setup
  )
fi

cat <<EOF
Installed gstack for Codex at:
  $DEST

Skills directory:
  $SKILLS_DIR

Next step:
  Restart Codex to pick up the new skills.
EOF
