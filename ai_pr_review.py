#!/usr/bin/env python3
"""
AI-powered PR review script that supports both Claude (Anthropic) and ChatGPT (OpenAI) models.

Environment Variables:
    AI_MODEL: Model to use (default: claude-sonnet-4-5-20250929)
              Examples:
              - Claude: claude-sonnet-4-5-20250929, claude-opus-4-6, claude-haiku-4-5-20251001
              - OpenAI: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
              - NVIDIA: nvidia/nemotron-3-nano-30b-a3b

    AI_PROVIDER: Force a specific provider (optional, auto-detected from model name)
                 Values: claude, anthropic, openai, chatgpt, nvidia

    API Keys (at least one required):
    - ANTHROPIC_API_KEY or CLAUDE_API_KEY: For Claude models
    - OPENAI_API_KEY: For OpenAI/ChatGPT models
    - NVIDIA_API_KEY: For NVIDIA models (fallback if OPENAI_API_KEY not set)

    OPENAI_API_URL: Custom OpenAI-compatible API endpoint (optional)
                    Default: https://api.openai.com/v1/chat/completions

    AI_UPDATE_PR_DESCRIPTION: Set to 'true' to update PR description (default: false)

Usage:
    python ai_pr_review.py <source_branch> <target_branch>

Examples:
    # Use Claude
    export ANTHROPIC_API_KEY=sk-ant-xxx
    export AI_MODEL=claude-sonnet-4-5-20250929
    python ai_pr_review.py feature/my-branch main

    # Use ChatGPT
    export OPENAI_API_KEY=sk-xxx
    export AI_MODEL=gpt-4o
    python ai_pr_review.py feature/my-branch main
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
import anthropic

MAX_DIFF_CHARS = 120000
MAX_FILES = 100


def run(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()


def get_env(*names, default=""):
    for name in names:
        val = os.getenv(name)
        if val:
            return val
    return default


def collect_diff(source_branch, target_branch):
    range_spec = f"{target_branch}...{source_branch}"

    try:
        names = run(["git", "diff", "--name-only", range_spec])
    except Exception:
        names = ""

    try:
        diff = run(["git", "diff", range_spec])
    except Exception:
        diff = ""

    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n\n[diff truncated]"

    files = "\n".join(names.splitlines()[:MAX_FILES])
    if len(names.splitlines()) > MAX_FILES:
        files += "\n[files list truncated]"

    return files, diff, range_spec


def http_json(url, method, data=None, headers=None):
    body = None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_review_prompt():
    """Returns the system prompt for code review."""
    return (
        "You are a senior embedded software reviewer.\n"
        "Review the diff and produce:\n"
        "1) A concise code review with risks/bugs, regressions, and missing tests.\n"
        "2) A PR description with sections: Summary, Changes, Tests.\n"
        "3) Output in Markdown format with clear sections and bullet points.\n"
        "Be factual and reference files when possible. If unsure, say so."
    )


def get_user_content(files, diff, range_spec):
    """Returns the user content for the review request."""
    return (
        f"Git range: {range_spec}\n\n"
        f"Files changed:\n{files}\n\n"
        f"Diff:\n{diff}"
    )


def claude_review(claude_model, files, diff, range_spec):
    """Review code using Claude (Anthropic) API."""
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not api_key:
        print("[ai_pr_review] ANTHROPIC_API_KEY or CLAUDE_API_KEY not set; skipping Claude review.")
        return None

    prompt = get_review_prompt()
    user_content = get_user_content(files, diff, range_spec)
    messages = [{"role": "user", "content": prompt + "\n\n" + user_content}]

    client = anthropic.Anthropic()
    message = client.messages.create(model=claude_model, max_tokens=4096, messages=messages)
    return message.content[0].text


def openai_review(model, files, diff, range_spec):
    """Review code using OpenAI-compatible API (OpenAI, NVIDIA, etc.)."""
    api_key = os.getenv("OPENAI_API_KEY")
    api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

    if not api_key:
        print("[ai_pr_review] OPENAI_API_KEY not set; skipping OpenAI review.")
        return None

    prompt = get_review_prompt()
    user_content = get_user_content(files, diff, range_spec)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        print("[ai_pr_review] OpenAI API error:", e.read().decode("utf-8"))
        return None
    except Exception as e:
        print("[ai_pr_review] OpenAI API error:", str(e))
        return None


def ai_review(model, files, diff, range_spec):
    """Route to the appropriate AI provider based on model name or provider setting."""
    provider = os.getenv("AI_PROVIDER", "").lower()

    # Auto-detect provider from model name if not explicitly set
    if not provider:
        if model.startswith("claude") or "claude" in model.lower():
            provider = "claude"
        elif model.startswith("gpt") or model.startswith("o1") or model.startswith("nvidia/"):
            provider = "openai"
        else:
            # Default to OpenAI-compatible API
            provider = "openai"

    print(f"[ai_pr_review] Using provider: {provider}, model: {model}")

    if provider == "claude" or provider == "anthropic":
        return claude_review(model, files, diff, range_spec)
    elif provider == "openai" or provider == "chatgpt" or provider == "nvidia":
        return openai_review(model, files, diff, range_spec)
    else:
        print(f"[ai_pr_review] Unknown provider: {provider}")
        return None


def post_pr_comment(org_url, project, repo_id, pr_id, token, content):
    url = (
        f"{org_url}{project}/_apis/git/repositories/{repo_id}/pullRequests/"
        f"{pr_id}/threads?api-version=7.1-preview.1"
    )
    data = {
        "comments": [
            {"parentCommentId": 0, "content": content, "commentType": 1}
        ],
        "status": 1,
    }
    return http_json(
        url,
        "POST",
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )


def update_pr_description(org_url, project, repo_id, pr_id, token, description):
    url = (
        f"{org_url}{project}/_apis/git/repositories/{repo_id}/pullRequests/"
        f"{pr_id}?api-version=7.1-preview.1"
    )
    return http_json(
        url,
        "PATCH",
        data={"description": description},
        headers={"Authorization": f"Bearer {token}"},
    )


def get_pr(org_url, project, repo_id, pr_id, token):
    url = (
        f"{org_url}{project}/_apis/git/repositories/{repo_id}/pullRequests/"
        f"{pr_id}?api-version=7.1-preview.1"
    )
    return http_json(
        url,
        "GET",
        headers={"Authorization": f"Bearer {token}"},
    )


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} source_branch target_branch")
        return 1
    else:
        source_branch = sys.argv[1]
        target_branch = sys.argv[2]
    pr_id = get_env("SYSTEM_PULLREQUEST_PULLREQUESTID")
    if not pr_id:
        print("[ai_pr_review] Not a PR build; skipping.")
        return 0

    files, diff, range_spec = collect_diff(source_branch, target_branch)
    if not diff.strip():
        print("[ai_pr_review] No diff found; skipping.")
        return 0

    model = os.getenv("AI_MODEL", "claude-opus-4-6")
    result = ai_review(model, files, diff, range_spec)
    if not result:
        return 0
    print(result)

    org_url = get_env("SYSTEM_COLLECTIONURI")
    project = get_env("SYSTEM_TEAMPROJECT")
    repo_id = get_env("BUILD_REPOSITORY_ID")
    token = get_env("SYSTEM_ACCESSTOKEN", "SYSTEM_ACCESS_TOKEN")

    if not (org_url and project and repo_id and token):
        print("[ai_pr_review] Missing Azure DevOps context or token; printing output only.")
        print(result)
        return 0

    comment_body = "## AI Code Review and PR Description\n\n" + result
    try:
        post_pr_comment(org_url, project, repo_id, pr_id, token, comment_body)
        print("[ai_pr_review] Posted PR comment.")
    except Exception as exc:
        print("[ai_pr_review] Failed to post PR comment:", exc)

    update_flag = os.getenv("AI_UPDATE_PR_DESCRIPTION", "false").lower() in ("1", "true", "yes")
    if update_flag:
        try:
            pr = get_pr(org_url, project, repo_id, pr_id, token)
            current = pr.get("description") or ""
            marker = "AI Suggested Description"
            if marker in current:
                print("[ai_pr_review] PR description already contains AI section; skipping update.")
                return 0
            new_desc = (current + "\n\n---\n" + marker + "\n\n" + result).strip()
            update_pr_description(org_url, project, repo_id, pr_id, token, new_desc)
            print("[ai_pr_review] Updated PR description.")
        except Exception as exc:
            print("[ai_pr_review] Failed to update PR description:", exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
