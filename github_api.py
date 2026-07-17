"""
github_api.py
-------------
Thin wrapper around the GitHub REST API used by the Streamlit app.

All functions raise GitHubAPIError on failure so the UI layer can
show a friendly message instead of a stack trace.
"""

import re
import requests

BASE_URL = "https://api.github.com"


class GitHubAPIError(Exception):
    """Raised for any GitHub API related failure (404, rate limit, network, etc.)."""
    pass


def parse_github_url(text: str):
    """
    Accepts either:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        github.com/owner/repo
        owner/repo
    Returns (owner, repo) as a tuple of strings.
    """
    text = text.strip().rstrip("/")
    text = re.sub(r"\.git$", "", text)

    # Full or partial URL
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+)", text)
    if match:
        return match.group(1), match.group(2)

    # owner/repo shorthand
    match = re.match(r"^([\w.-]+)/([\w.-]+)$", text)
    if match:
        return match.group(1), match.group(2)

    raise GitHubAPIError(
        "Could not parse a repository from that input. "
        "Use a URL like https://github.com/owner/repo or just owner/repo."
    )


def _headers(token: str | None):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(url: str, token: str | None, params: dict | None = None):
    try:
        response = requests.get(url, headers=_headers(token), params=params, timeout=15)
    except requests.RequestException as exc:
        raise GitHubAPIError(f"Network error while calling GitHub API: {exc}") from exc

    if response.status_code == 404:
        raise GitHubAPIError("Repository not found. Check the owner/name and try again.")

    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            reset = response.headers.get("X-RateLimit-Reset", "")
            raise GitHubAPIError(
                "GitHub API rate limit exceeded. "
                "Add a personal access token in the sidebar to raise the limit to 5,000 requests/hour."
                + (f" (resets at unix time {reset})" if reset else "")
            )
        raise GitHubAPIError("GitHub API refused the request (403 Forbidden).")

    if not response.ok:
        raise GitHubAPIError(f"GitHub API error {response.status_code}: {response.text[:200]}")

    return response.json(), response.headers


def get_repo_info(owner: str, repo: str, token: str | None = None) -> dict:
    """Core repository metadata: name, description, stars, forks, etc."""
    url = f"{BASE_URL}/repos/{owner}/{repo}"
    data, _ = _get(url, token)
    return {
        "name": data.get("name"),
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "owner": data.get("owner", {}).get("login"),
        "owner_avatar": data.get("owner", {}).get("avatar_url"),
        "owner_url": data.get("owner", {}).get("html_url"),
        "html_url": data.get("html_url"),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "watchers": data.get("subscribers_count", data.get("watchers_count", 0)),
        "open_issues": data.get("open_issues_count", 0),
        "default_branch": data.get("default_branch", "main"),
        "license": (data.get("license") or {}).get("name"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "pushed_at": data.get("pushed_at"),
        "size_kb": data.get("size", 0),
        "topics": data.get("topics", []),
        "homepage": data.get("homepage"),
        "archived": data.get("archived", False),
        "is_fork": data.get("fork", False),
        "visibility": data.get("visibility"),
    }


def get_languages(owner: str, repo: str, token: str | None = None) -> dict:
    """Returns {language: bytes_of_code} for the repository."""
    url = f"{BASE_URL}/repos/{owner}/{repo}/languages"
    data, _ = _get(url, token)
    return data


def get_file_tree(owner: str, repo: str, branch: str, token: str | None = None) -> list:
    """
    Returns a flat list of {path, type, size} for every file/folder in the repo,
    fetched recursively via the git trees API in a single call.
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/git/trees/{branch}"
    data, _ = _get(url, token, params={"recursive": "1"})

    if data.get("truncated"):
        # Repo is very large; GitHub only returns a partial tree.
        pass

    tree = []
    for item in data.get("tree", []):
        tree.append({
            "path": item.get("path"),
            "type": "dir" if item.get("type") == "tree" else "file",
            "size": item.get("size", 0),
        })
    return tree, data.get("truncated", False)


def get_rate_limit(token: str | None = None) -> dict:
    """Useful for showing the user how many requests they have left."""
    url = f"{BASE_URL}/rate_limit"
    data, _ = _get(url, token)
    core = data.get("resources", {}).get("core", {})
    return {
        "limit": core.get("limit"),
        "remaining": core.get("remaining"),
        "reset": core.get("reset"),
    }