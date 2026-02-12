# AI PR Assistant

AI-powered Azure DevOps pull request helper with two commands:

- `create`: creates a new PR and auto-generates the PR description.
- `review`: reviews code changes and posts AI review comments to an existing PR.

## Supported AI Providers

- **Claude (Anthropic)**: e.g. `claude-sonnet-4-5-20250929`, `claude-opus-4-6`
- **OpenAI**: e.g. `gpt-4o`, `gpt-4-turbo`
- **NVIDIA (OpenAI-compatible)**: e.g. `nvidia/nemotron-3-nano-30b-a3b`

## Requirements

- Python 3
- Git available in PATH
- Azure DevOps repo/project/org access for posting/creating PRs
- At least one AI API key

## Environment Variables

### AI settings

| Variable | Default | Description |
|---|---|---|
| `AI_MODEL` | `claude-opus-4-6` | Model used for generation/review |
| `AI_PROVIDER` | auto-detect | Force provider: `claude`, `anthropic`, `openai`, `chatgpt`, `nvidia` |
| `OPENAI_API_URL` | `https://api.openai.com/v1/chat/completions` | Custom OpenAI-compatible endpoint |

### API keys

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `NVIDIA_API_KEY` | NVIDIA API key for OpenAI-compatible endpoint |

### Azure DevOps context

You can pass these as CLI flags or environment variables.

| Variable | Description |
|---|---|
| `AZDO_ORG_URL` | Azure DevOps org URL, e.g. `https://dev.azure.com/myorg/` |
| `AZDO_PROJECT` | Project name |
| `AZDO_REPO_ID` | Repository ID |
| `AZDO_TOKEN` | Personal access token or pipeline access token |

Pipeline fallbacks are also supported in review mode:
- `SYSTEM_COLLECTIONURI`
- `SYSTEM_TEAMPROJECT`
- `BUILD_REPOSITORY_ID`
- `SYSTEM_ACCESSTOKEN` / `SYSTEM_ACCESS_TOKEN`
- `SYSTEM_PULLREQUEST_PULLREQUESTID`

## Command Usage

### Create a new PR with AI description

```bash
python ai_pr_review.py create <source_branch> <target_branch> [--title "..."] [--push]
```

Example:

```bash
export OPENAI_API_KEY=sk-xxxx
export AI_MODEL=gpt-4o
export AZDO_ORG_URL="https://dev.azure.com/myorg/"
export AZDO_PROJECT="MyProject"
export AZDO_REPO_ID="<repo-id>"
export AZDO_TOKEN="<token>"

python ai_pr_review.py create feature/new-api main --title "Add new API"
```

Notes:
- `--push` runs `git push -u origin <source_branch>` before PR creation.
- If `--repo-id`/`AZDO_REPO_ID` is missing, `create` attempts to infer it from `git remote origin` (via `git config` or `.git/config`).
- If Azure DevOps context is missing, the script prints generated description and exits.

### Review code and post PR comment

```bash
python ai_pr_review.py review <source_branch> <target_branch> [--pr-id <id>] [--update-description]
```

Example:

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxx
export AI_MODEL=claude-opus-4-6

python ai_pr_review.py review feature/new-api main --pr-id 123 --update-description
```

Notes:
- If `--pr-id` is omitted, the script uses `SYSTEM_PULLREQUEST_PULLREQUESTID`.
- `--update-description` appends an `AI Suggested Description` section to the PR description.

## Legacy Compatibility

Old usage still works:

```bash
python ai_pr_review.py <source_branch> <target_branch>
```

This is treated as:

```bash
python ai_pr_review.py review <source_branch> <target_branch>
```

In legacy mode, description updates are controlled by `AI_UPDATE_PR_DESCRIPTION=true`.

## Troubleshooting

### Missing provider SDK

If `anthropic` is not installed and you choose a Claude model/provider, Claude requests are skipped.

### API errors

- Verify API key validity and model name.
- Check permissions and quota.
- If using custom endpoint, verify `OPENAI_API_URL`.

### No diff found

The script compares `<target_branch>...<source_branch>`. Ensure branches exist locally and contain expected changes.

### Diff too large

Diffs are truncated at 120KB and file list at 100 files.
