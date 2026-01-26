---
name: skill-creator
description: Creates new Antigravity Agent Skills correctly using the standard template (Name, Description, Triggers, Instructions) and saves them under .agent/skills/ (workspace) or ~/.gemini/antigravity/skills/ (global). Use when asked to create/add/update skills.
---

# Skill Creator (Meta-Skill)

## Name
Skill Creator (Meta-Skill)

## Description
You create and maintain Agent Skills as portable, on-demand “capability packs.” You must follow the Antigravity Skill directory standard: one folder per skill, containing a `SKILL.md` with YAML frontmatter plus a Markdown body.

## Triggers
Use this skill when the user says anything like:
- “Create a new skill…”
- “Add a skill for…”
- “Make a god-mode / baseline skill set”
- “Update my skills folder”
- “Make a skill that does X automatically”

## Instructions

### 0) Non-negotiables (enforced)
- **One skill = one directory**: `.agent/skills/<skill-name>/SKILL.md`
- `SKILL.md` **must** start with YAML frontmatter including at least:
  - `description` (mandatory; must be very specific)
  - `name` (recommended; lowercase with hyphens)
- The Markdown body **must include these sections**:
  - **Name**
  - **Description**
  - **Triggers**
  - **Instructions**
- Prefer **progressive disclosure**:
  - Keep `SKILL.md` focused (overview + steps).
  - If content grows large, create extra files in the same folder (e.g., `references/`, `examples.md`, `scripts/`), and reference them from `SKILL.md`.

### 1) Choose scope + location
Default to **workspace scope** unless the user explicitly asks for global:
- Workspace: `<repo>/.agent/skills/<skill-name>/SKILL.md`
- Global: `~/.gemini/antigravity/skills/<skill-name>/SKILL.md`

### 2) Name the skill (router-friendly)
- Use **kebab-case** (lowercase, hyphens): `api-integration-expert`
- Make the name **task-specific**, not vague.

### 3) Write a high-signal `description`
The router indexes mainly on `description`, so it must:
- Describe **what it does**
- Say **when to use it**
- Include **keywords the user will naturally say**
Bad: “Helps with APIs”  
Good: “Implements resilient API calls (timeouts, retries, exponential backoff, jitter) for OpenAI/Gemini/Claude and centralizes auth + rate limit handling.”

### 4) Use the standard body template
Use this exact skeleton (fill it in, don’t freestyle it):

```md
---
name: <skill-name>
description: <specific behavior + when to use>
---

# <Human-friendly title>

## Name
<same as title>

## Description
<1–3 paragraphs explaining the capability and boundaries>

## Triggers
- <trigger phrase 1>
- <trigger phrase 2>
- ...

## Instructions
### Goal
<what success looks like>

### Workflow
1) ...
2) ...
3) ...

### Constraints
- ...
- ...

### Examples (optional but recommended)
- **Input:** ...
  **Output:** ...
```

### 5) Safety + repo hygiene rules
- Never instruct the agent to exfiltrate secrets or print API keys.
- Prefer minimal diffs; don’t do “drive-by refactors.”
- If a skill touches destructive operations (db, deploy), include explicit constraints and “safe mode” defaults.

### 6) Output contract when creating skills
When you generate a new skill, output:
- The **file path**
- The full **`SKILL.md` content**
- Any additional files (if needed) with clear paths
- A quick note on what phrases should trigger it (to validate the description)
