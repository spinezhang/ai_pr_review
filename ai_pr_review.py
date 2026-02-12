#!/usr/bin/env python3
"""AI-powered Azure DevOps PR assistant.

Commands:
    create  -> Create a new PR in Azure DevOps with an AI-generated description.
    review  -> Review diff with AI and post a PR comment.

Legacy usage is still supported:
    python ai_pr_review.py <source_branch> <target_branch>
This is treated as:
    python ai_pr_review.py review <source_branch> <target_branch>
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
try:
    import anthropic
except ImportError:
    anthropic = None

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


def to_ref(branch):
    if branch.startswith("refs/heads/"):
        return branch
    return f"refs/heads/{branch}"


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
    return (
        "You are a senior embedded software reviewer.\n"
        "Review the diff and produce:\n"
        "1) A concise code review with risks/bugs, regressions, and missing tests.\n"
        "2) Output in Markdown format with sections: Findings, Risks, Test Gaps, Suggestions.\n"
        "Be factual and reference files when possible. If unsure, say so."
    )


def get_pr_description_prompt():
    return (
        "You are a senior embedded software engineer writing pull request descriptions.\n"
        "Generate a concise, high-signal PR description in Markdown with sections:\n"
        "- Summary\n"
        "- Changes\n"
        "- Tests\n"
        "Be specific, actionable, and avoid filler."
    )


def get_user_content(files, diff, range_spec):
    return (
        f"Git range: {range_spec}\n\n"
        f"Files changed:\n{files}\n\n"
        f"Diff:\n{diff}"
    )


def claude_chat(model, system_prompt, user_content):
    if anthropic is None:
        print("[ai_pr_review] anthropic package not installed; skipping Claude request.")
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not api_key:
        print("[ai_pr_review] ANTHROPIC_API_KEY or CLAUDE_API_KEY not set; skipping Claude request.")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text


def openai_chat(model, system_prompt, user_content):
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("NVIDIA_API_KEY")
    api_url = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

    if not api_key:
        print("[ai_pr_review] OPENAI_API_KEY or NVIDIA_API_KEY not set; skipping OpenAI-compatible request.")
        return None

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
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


def ai_chat(model, system_prompt, user_content):
    provider = os.getenv("AI_PROVIDER", "").lower()

    if not provider:
        if model.startswith("claude") or "claude" in model.lower():
            provider = "claude"
        elif model.startswith("gpt") or model.startswith("o1") or model.startswith("nvidia/"):
            provider = "openai"
        else:
            provider = "openai"

    print(f"[ai_pr_review] Using provider: {provider}, model: {model}")

    if provider == "claude" or provider == "anthropic":
        return claude_chat(model, system_prompt, user_content)
    elif provider == "openai" or provider == "chatgpt" or provider == "nvidia":
        return openai_chat(model, system_prompt, user_content)
    else:
        print(f"[ai_pr_review] Unknown provider: {provider}")
        return None


def ai_review(model, files, diff, range_spec):
    return ai_chat(model, get_review_prompt(), get_user_content(files, diff, range_spec))


def ai_pr_description(model, files, diff, range_spec):
    return ai_chat(model, get_pr_description_prompt(), get_user_content(files, diff, range_spec))


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


def create_pr(org_url, project, repo_id, source_branch, target_branch, token, title, description):
    url = (
        f"{org_url}{project}/_apis/git/repositories/{repo_id}/pullrequests"
        f"?api-version=7.1-preview.1"
    )
    data = {
        "sourceRefName": to_ref(source_branch),
        "targetRefName": to_ref(target_branch),
        "title": title,
        "description": description,
    }
    return http_json(
        url,
        "POST",
        data=data,
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


def parse_args():
    parser = argparse.ArgumentParser(description="AI-powered Azure DevOps PR assistant")
    subparsers = parser.add_subparsers(dest="command")

    create_cmd = subparsers.add_parser("create", help="Create PR with AI-generated description")
    create_cmd.add_argument("source_branch")
    create_cmd.add_argument("target_branch")
    create_cmd.add_argument("--title", default="", help="PR title (default: auto-generated)")
    create_cmd.add_argument("--push", action="store_true", help="Push source branch to origin before creating PR")

    review_cmd = subparsers.add_parser("review", help="Review code and post AI comment to an existing PR")
    review_cmd.add_argument("source_branch")
    review_cmd.add_argument("target_branch")
    review_cmd.add_argument("--pr-id", default="", help="PR ID (default: SYSTEM_PULLREQUEST_PULLREQUESTID)")
    review_cmd.add_argument("--update-description", action="store_true", help="Also update PR description from AI")

    parser.add_argument(
        "--model",
        default=os.getenv("AI_MODEL", "claude-opus-4-6"),
        help="AI model name",
    )
    parser.add_argument("--org-url", default=get_env("AZDO_ORG_URL", "SYSTEM_COLLECTIONURI"))
    parser.add_argument("--project", default=get_env("AZDO_PROJECT", "SYSTEM_TEAMPROJECT"))
    parser.add_argument("--repo-id", default=get_env("AZDO_REPO_ID", "BUILD_REPOSITORY_ID"))
    parser.add_argument("--token", default=get_env("AZDO_TOKEN", "SYSTEM_ACCESSTOKEN", "SYSTEM_ACCESS_TOKEN"))

    args = parser.parse_args()
    if args.command:
        return args

    if len(sys.argv) >= 3:
        legacy = argparse.Namespace(
            command="review",
            source_branch=sys.argv[1],
            target_branch=sys.argv[2],
            pr_id=get_env("SYSTEM_PULLREQUEST_PULLREQUESTID"),
            update_description=os.getenv("AI_UPDATE_PR_DESCRIPTION", "false").lower() in ("1", "true", "yes"),
            model=os.getenv("AI_MODEL", "claude-opus-4-6"),
            org_url=get_env("AZDO_ORG_URL", "SYSTEM_COLLECTIONURI"),
            project=get_env("AZDO_PROJECT", "SYSTEM_TEAMPROJECT"),
            repo_id=get_env("AZDO_REPO_ID", "BUILD_REPOSITORY_ID"),
            token=get_env("AZDO_TOKEN", "SYSTEM_ACCESSTOKEN", "SYSTEM_ACCESS_TOKEN"),
        )
        return legacy

    parser.print_help()
    return None


def require_ado_context(args):
    if not (args.org_url and args.project and args.repo_id and args.token):
        print(
            "[ai_pr_review] Missing Azure DevOps context. "
            "Set --org-url, --project, --repo-id, --token "
            "or AZDO_ORG_URL, AZDO_PROJECT, AZDO_REPO_ID, AZDO_TOKEN."
        )
        return False
    return True


def default_title(source_branch, target_branch):
    src = source_branch.replace("refs/heads/", "")
    tgt = target_branch.replace("refs/heads/", "")
    return f"{src} into {tgt}"


def handle_create(args):
    if args.push:
        print(f"[ai_pr_review] Pushing {args.source_branch} to origin...")
        run(["git", "push", "-u", "origin", args.source_branch])

    files, diff, range_spec = collect_diff(args.source_branch, args.target_branch)
    if not diff.strip():
        print("[ai_pr_review] No diff found. Creating PR with fallback description.")
        description = "Summary\n- No diff detected between selected branches."
    else:
        description = ai_pr_description(args.model, files, diff, range_spec)
        if not description:
            description = "Summary\n- AI description generation failed."

    title = args.title.strip() or default_title(args.source_branch, args.target_branch)
    if not require_ado_context(args):
        print("[ai_pr_review] Generated PR description:\n")
        print(description)
        return 1

    pr = create_pr(
        org_url=args.org_url,
        project=args.project,
        repo_id=args.repo_id,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        token=args.token,
        title=title,
        description=description,
    )
    pr_id = pr.get("pullRequestId")
    pr_url = pr.get("url") or ""
    print(f"[ai_pr_review] Created PR #{pr_id}: {title}")
    if pr_url:
        print(f"[ai_pr_review] PR API URL: {pr_url}")
    return 0


def handle_review(args):
    files, diff, range_spec = collect_diff(args.source_branch, args.target_branch)
    if not diff.strip():
        print("[ai_pr_review] No diff found; skipping.")
        return 0

    result = ai_review(args.model, files, diff, range_spec)
    if not result:
        return 1

    print(result)

    pr_id = args.pr_id or get_env("SYSTEM_PULLREQUEST_PULLREQUESTID")
    if not (pr_id and require_ado_context(args)):
        print("[ai_pr_review] Missing Azure DevOps context or token; printing output only.")
        return 0

    comment_body = "## AI Code Review\n\n" + result
    try:
        post_pr_comment(args.org_url, args.project, args.repo_id, pr_id, args.token, comment_body)
        print("[ai_pr_review] Posted PR comment.")
    except Exception as exc:
        print("[ai_pr_review] Failed to post PR comment:", exc)

    if args.update_description:
        try:
            pr = get_pr(args.org_url, args.project, args.repo_id, pr_id, args.token)
            current = pr.get("description") or ""
            marker = "AI Suggested Description"
            if marker in current:
                print("[ai_pr_review] PR description already contains AI section; skipping update.")
                return 0
            generated = ai_pr_description(args.model, files, diff, range_spec) or result
            new_desc = (current + "\n\n---\n" + marker + "\n\n" + generated).strip()
            update_pr_description(args.org_url, args.project, args.repo_id, pr_id, args.token, new_desc)
            print("[ai_pr_review] Updated PR description.")
        except Exception as exc:
            print("[ai_pr_review] Failed to update PR description:", exc)

    return 0


def main():
    args = parse_args()
    if args is None:
        return 1
    if args.command == "create":
        return handle_create(args)
    if args.command == "review":
        return handle_review(args)
    print("[ai_pr_review] Unknown command. Use 'create' or 'review'.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
