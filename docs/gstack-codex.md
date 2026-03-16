# gstack for Codex

This repo includes a helper installer at [`scripts/install-gstack-codex.sh`](/Users/rashidbaset/Documents/calllock-agenticos/scripts/install-gstack-codex.sh) that installs [gstack](https://github.com/garrytan/gstack) into Codex's skill directory instead of Claude Code's.

It does four things:

1. Clones `garrytan/gstack` into `${CODEX_HOME:-~/.codex}/skills/gstack`
2. Rewrites `gstack`'s hard-coded `.claude/skills` paths to `.codex/skills`
3. Rewrites `CLAUDE.md` references to `AGENTS.md` and creates an `AGENTS.md` copy
4. Runs `./setup` so the `browse`, `qa`, `review`, `ship`, and related skill symlinks are created under `~/.codex/skills`

## Install

```bash
cd /Users/rashidbaset/Documents/calllock-agenticos
scripts/install-gstack-codex.sh
```

Then restart Codex.

## Reinstall or update

Reinstall from `main`:

```bash
cd /Users/rashidbaset/Documents/calllock-agenticos
scripts/install-gstack-codex.sh --force
```

Install a different ref:

```bash
cd /Users/rashidbaset/Documents/calllock-agenticos
scripts/install-gstack-codex.sh --force --ref main
```

Patch an existing checkout again without recloning:

```bash
~/.codex/skills/gstack/bin/codex-patch ~/.codex/skills/gstack
cd ~/.codex/skills/gstack
./setup
```

## Assumptions

- `git`, `python3`, and `bun` are installed locally
- Codex reads skills from `${CODEX_HOME:-~/.codex}/skills`
- `gstack` still uses Claude-specific terminology upstream, so this installer patches the local checkout instead of relying on the generic GitHub skill installer
