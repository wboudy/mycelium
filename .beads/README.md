# Beads Rust - AI-Native Issue Tracking

Welcome to Beads Rust. This repository uses **br** (`beads_rust`) for issue tracking so issue state lives alongside code in `.beads/`.

**Note:** `br` is non-invasive and never executes git commands. After `br sync --flush-only`, you must manually run `git add .beads/ && git commit`.

## What is Beads Rust?

Beads Rust is issue tracking that lives in your repo, making it a good fit for AI coding agents and developers who want local, versioned issue state.

**Learn more:** [github.com/Dicklesworthstone/beads_rust](https://github.com/Dicklesworthstone/beads_rust)

## Quick Start

### Essential Commands

```bash
# Create new issues
br create "Add user authentication"

# View all issues
br list

# View issue details
br show <issue-id>

# Update issue status
br update <issue-id> --status in_progress
br update <issue-id> --status done

# Flush issue state to JSONL, then commit manually
br sync --flush-only
git add .beads/
git commit -m "sync beads"
```

### Working with Issues

Issues in Beads Rust are:
- **Git-native**: Stored in `.beads/issues.jsonl` and versioned with code
- **AI-friendly**: CLI-first design works well with AI coding agents
- **Branch-aware**: Issues can follow your branch workflow
- **Explicit sync model**: You control when `.beads/` is staged and committed

## Why Beads Rust?

- Built for AI-assisted development workflows
- Works in CLI-first environments without web dependency
- Lightweight, local, and repository-native issue state

## Get Started with Beads Rust

```bash
# Initialize in your repo
br init

# Create your first issue
br create "Try out Beads Rust"
```

## Learn More

- **Documentation**: [github.com/Dicklesworthstone/beads_rust](https://github.com/Dicklesworthstone/beads_rust)
- **Quick Start Guide**: Run `br quickstart`

