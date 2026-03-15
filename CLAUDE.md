# CLAUDE.md — AI Assistant Guide for bharatmarkets

This file provides guidance for AI assistants (Claude, Copilot, etc.) working in this repository. Keep this file up to date as the project evolves.

---

## Project Overview

**bharatmarkets** is a project related to Indian financial markets (Bharat = India). At the time of writing, the repository is in its initial state and has not yet been populated with application code.

- **Repository:** Murugkan/bharatmarkets
- **Status:** Pre-implementation / bootstrapping phase

---

## Repository State (as of 2026-03-15)

The repository currently contains:
- `README.md` — minimal placeholder (`# bharatmarkets`)
- `CLAUDE.md` — this file

No source code, configuration files, dependencies, or tests exist yet.

---

## Git Workflow

### Branches
- `master` / `main` — primary branch
- `claude/<description>-<id>` — AI-generated feature/task branches

### Commit Conventions
- Use clear, descriptive commit messages in the imperative mood (e.g., "Add stock price fetcher", not "Added stock price fetcher")
- Commits are **GPG/SSH signed** — do not use `--no-verify` or `--no-gpg-sign`
- Commit signing key: `/home/claude/.ssh/commit_signing_key.pub`

### Push Instructions
Always push with upstream tracking:
```bash
git push -u origin <branch-name>
```

Branch names for AI sessions must follow: `claude/<description>-<session-id>`

---

## Development Guidelines for AI Assistants

### General Principles
1. **Read before editing** — always read a file before modifying it
2. **Minimal changes** — only change what is needed for the task; do not refactor surrounding code
3. **No over-engineering** — do not add abstractions, helpers, or patterns for hypothetical future use
4. **No comments on unchanged code** — do not add docstrings or comments to code you didn't write
5. **Security first** — avoid SQL injection, XSS, command injection, and other OWASP Top 10 issues
6. **No backwards-compatibility shims** — if something is unused, delete it cleanly

### File Operations
- Prefer `Edit` over full file rewrites when modifying existing files
- Do not create new files unless strictly necessary
- Do not create documentation files (`*.md`) unless explicitly requested

### Confirmations Required Before
- Pushing to `main`/`master`
- Force pushes of any kind
- Deleting files or branches
- Modifying CI/CD pipelines
- Any action that is hard to reverse

---

## When Code Is Added (Update This Section)

Once the project is bootstrapped, update the following sections:

### Technology Stack
_Document the language, framework, and key libraries here._

### Project Structure
_Document the directory layout here (e.g., `src/`, `tests/`, `docs/`)._

### Running the Project
```bash
# Add install, build, and run commands here
```

### Running Tests
```bash
# Add test commands here
```

### Environment Variables
_List required environment variables and link to `.env.example`._

### Code Conventions
_Document naming conventions, linting rules, formatting standards, etc._

### API Overview
_Document the API structure, authentication method, and key endpoints._

---

## Contact / Ownership

- **Repo owner:** Murugkan
- **AI sessions use:** `noreply@anthropic.com` as the git author
