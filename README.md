# AI PR Review Script

An automated PR review tool that uses AI models (Claude or ChatGPT) to review code changes and generate PR descriptions.

## Supported AI Providers

- **Claude (Anthropic)**: claude-sonnet-4-5-20250929, claude-opus-4-6, claude-haiku-4-5-20251001
- **ChatGPT (OpenAI)**: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
- **NVIDIA**: nvidia/nemotron-3-nano-30b-a3b (uses OpenAI-compatible API)

## Environment Variables

### Required (at least one API key)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` or `CLAUDE_API_KEY` | API key for Claude models |
| `OPENAI_API_KEY` | API key for OpenAI/ChatGPT models |
| `NVIDIA_API_KEY` | API key for NVIDIA models (fallback) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_MODEL` | `claude-sonnet-4-5-20250929` | Model to use for review |
| `AI_PROVIDER` | (auto-detect) | Force specific provider: `claude`, `anthropic`, `openai`, `chatgpt`, `nvidia` |
| `OPENAI_API_URL` | `https://api.openai.com/v1/chat/completions` | Custom OpenAI-compatible endpoint |
| `AI_UPDATE_PR_DESCRIPTION` | `false` | Set to `true` to auto-update PR description |

## Usage Examples

### Using Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
export AI_MODEL=claude-sonnet-4-5-20250929
python ci/ai_pr_review.py feature/my-branch main
```

### Using ChatGPT (OpenAI)

```bash
export OPENAI_API_KEY=sk-xxxxx
export AI_MODEL=gpt-4o
python ci/ai_pr_review.py feature/my-branch main
```

### Using NVIDIA Models

```bash
export NVIDIA_API_KEY=nvapi-xxxxx
export AI_MODEL=nvidia/nemotron-3-nano-30b-a3b
python ci/ai_pr_review.py feature/my-branch main
```

### Force a Specific Provider

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
export AI_MODEL=claude-sonnet-4-5-20250929
export AI_PROVIDER=claude
python ci/ai_pr_review.py feature/my-branch main
```

## Azure DevOps Integration

The script automatically integrates with Azure DevOps pipelines when the following environment variables are present:

- `SYSTEM_PULLREQUEST_PULLREQUESTID`
- `SYSTEM_COLLECTIONURI`
- `SYSTEM_TEAMPROJECT`
- `BUILD_REPOSITORY_ID`
- `SYSTEM_ACCESSTOKEN`

## How It Works

1. **Collects Git Diff**: Retrieves the diff between source and target branches
2. **AI Review**: Sends the diff to the selected AI provider for analysis
3. **Generates Output**:
   - Code review with risks, bugs, and regressions
   - PR description with Summary, Changes, and Tests sections
4. **Posts to PR**: Comments on the PR with the review (if Azure DevOps context is available)
5. **Updates Description**: Optionally updates the PR description with AI suggestions

## Provider Auto-Detection

The script automatically detects the provider based on the model name:

- Models starting with `claude` → Claude (Anthropic)
- Models starting with `gpt` or `o1` → OpenAI
- Models starting with `nvidia/` → OpenAI-compatible (NVIDIA)
- Default → OpenAI-compatible API

You can override this by setting the `AI_PROVIDER` environment variable.

## API Rate Limits

Be aware of API rate limits for your chosen provider:

- **Claude**: Depends on your plan (free tier has limits)
- **OpenAI**: Varies by model and plan
- **NVIDIA**: Check NVIDIA NIM documentation

## Troubleshooting

### "API key not set" error
Ensure you've set the correct API key environment variable for your chosen provider.

### "Unknown provider" error
Check that `AI_PROVIDER` is set to a valid value or let it auto-detect from the model name.

### "API error" messages
- Verify your API key is valid and has sufficient credits
- Check that the model name is correct
- For custom endpoints, verify `OPENAI_API_URL` is set correctly

### Diff too large
The script truncates diffs larger than 120KB. Consider reviewing large PRs in smaller chunks.
