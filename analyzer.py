"""
analyzer.py
-----------
Phase 2 — Repository Code Analyzer.

Takes the flat file tree from github_api.get_file_tree() and:
  - filters out noise directories/files (.git, node_modules, dist, ...)
  - detects language mix (reuses the GitHub languages endpoint), framework,
    and package manager
  - computes project statistics: file count, lines of code, file type
    distribution, largest files, rough component/route counts

All GitHub network calls go through fetch_raw_file(), which hits
raw.githubusercontent.com directly (no auth needed for public repos,
and it doesn't count against the REST API rate limit).
"""

import json
import os
from urllib.parse import quote

import requests

from ignore_rules import (
    BINARY_EXTENSIONS,
    DATABASE_SIGNALS,
    EXTENSION_LANGUAGE_MAP,
    FRAMEWORK_MANIFEST_FILES,
    FRAMEWORK_SIGNALS,
    IGNORED_DIR_NAMES,
    IGNORED_FILE_NAMES,
    PACKAGE_MANAGER_FILES,
)

RAW_BASE_URL = "https://raw.githubusercontent.com"

# Safety limits so a huge repo can't blow up the rate limit or hang the UI.
MAX_FILES_FOR_LOC = 300
MAX_FILE_SIZE_BYTES = 300_000  # skip individual files bigger than this


class AnalyzerError(Exception):
    pass


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def is_ignored_path(path: str) -> bool:
    parts = path.split("/")
    if any(part in IGNORED_DIR_NAMES for part in parts[:-1]):
        return True
    if parts[-1] in IGNORED_FILE_NAMES:
        return True
    return False


def filter_tree(tree: list) -> list:
    """Removes ignored directories/files and directory entries themselves,
    returning only real files worth analyzing."""
    return [
        item for item in tree
        if item["type"] == "file" and not is_ignored_path(item["path"])
    ]


# ---------------------------------------------------------------------------
# File fetching
# ---------------------------------------------------------------------------
def fetch_raw_file(owner: str, repo: str, branch: str, path: str, timeout: int = 10):
    """Fetches raw file content as text. Returns None on failure or if
    the file looks binary/undecodable, instead of raising, so callers can
    just skip it."""
    encoded_path = "/".join(quote(part) for part in path.split("/"))
    url = f"{RAW_BASE_URL}/{owner}/{repo}/{branch}/{encoded_path}"
    try:
        response = requests.get(url, timeout=timeout)
        if not response.ok:
            return None
        return response.text
    except requests.RequestException:
        return None
    except UnicodeDecodeError:
        return None


# ---------------------------------------------------------------------------
# Language / file-type stats
# ---------------------------------------------------------------------------
def file_type_distribution(files: list) -> list:
    """Counts files by extension. Returns a list of
    {extension, count, language} sorted by count descending."""
    counts = {}
    for item in files:
        _, ext = os.path.splitext(item["path"])
        ext = ext.lower() or "(no extension)"
        counts[ext] = counts.get(ext, 0) + 1

    rows = [
        {
            "extension": ext,
            "count": count,
            "language": EXTENSION_LANGUAGE_MAP.get(ext, "Other"),
        }
        for ext, count in counts.items()
    ]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def largest_files(files: list, top_n: int = 10) -> list:
    ranked = sorted(files, key=lambda f: f.get("size", 0), reverse=True)
    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Lines of code
# ---------------------------------------------------------------------------
def count_lines_of_code(owner: str, repo: str, branch: str, files: list,
                         max_files: int = MAX_FILES_FOR_LOC,
                         max_file_size: int = MAX_FILE_SIZE_BYTES,
                         progress_callback=None) -> dict:
    """
    Downloads a capped number of code files and sums their line counts.
    Skips known binary extensions and anything above max_file_size.
    Returns totals plus a per-language breakdown and how many files were
    actually sampled (for transparency in the UI, since huge repos are
    capped for speed / rate-limit reasons).
    """
    candidates = [
        f for f in files
        if os.path.splitext(f["path"])[1].lower() not in BINARY_EXTENSIONS
        and f.get("size", 0) <= max_file_size
    ]
    # Prioritize smaller files first so we sample broadly within the cap
    # instead of burning the whole budget on a handful of huge files.
    candidates.sort(key=lambda f: f.get("size", 0))
    sampled = candidates[:max_files]

    total_loc = 0
    loc_by_language = {}
    files_counted = 0

    for i, item in enumerate(sampled):
        if progress_callback:
            progress_callback(i + 1, len(sampled))

        content = fetch_raw_file(owner, repo, branch, item["path"])
        if content is None:
            continue

        lines = content.splitlines()
        line_count = len(lines)
        total_loc += line_count
        files_counted += 1

        ext = os.path.splitext(item["path"])[1].lower()
        lang = EXTENSION_LANGUAGE_MAP.get(ext, "Other")
        loc_by_language[lang] = loc_by_language.get(lang, 0) + line_count

    return {
        "total_loc": total_loc,
        "files_counted": files_counted,
        "files_skipped": len(files) - len(candidates),
        "sample_capped": len(candidates) > max_files,
        "loc_by_language": dict(
            sorted(loc_by_language.items(), key=lambda kv: kv[1], reverse=True)
        ),
    }


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------
def detect_package_manager(files: list) -> str:
    filenames = {os.path.basename(f["path"]) for f in files}
    for filename, manager in PACKAGE_MANAGER_FILES.items():
        if filename in filenames:
            return manager
    if "requirements.txt" in filenames:
        return "pip"
    if "pyproject.toml" in filenames:
        return "poetry / pip"
    return "Unknown"


# ---------------------------------------------------------------------------
# Framework + database detection
# ---------------------------------------------------------------------------
def _extract_dependency_keys(manifest_name: str, content: str) -> set:
    """Pulls a flat set of lowercase dependency names / keywords out of a
    manifest file so we can match them against FRAMEWORK_SIGNALS."""
    keys = set()
    if manifest_name == "package.json":
        try:
            data = json.loads(content)
            for section in ("dependencies", "devDependencies"):
                keys.update(k.lower() for k in data.get(section, {}).keys())
        except json.JSONDecodeError:
            pass
    elif manifest_name == "composer.json":
        try:
            data = json.loads(content)
            for section in ("require", "require-dev"):
                keys.update(k.lower() for k in data.get(section, {}).keys())
        except json.JSONDecodeError:
            pass
    else:
        # Plain text manifests (requirements.txt, Gemfile, pom.xml, go.mod, Cargo.toml...)
        # just do a lowercase keyword search across the whole file.
        keys.add(content.lower())
    return keys


def detect_frameworks_and_databases(owner: str, repo: str, branch: str, files: list) -> dict:
    """Fetches whichever known manifest files exist in the repo and scans
    them for framework and database signals."""
    filenames_present = {
        f["path"]: os.path.basename(f["path"]) for f in files
    }
    manifest_paths = [
        path for path, name in filenames_present.items()
        if name in FRAMEWORK_MANIFEST_FILES
    ]

    frameworks_found = []
    categories_found = set()
    databases_found = set()

    for path in manifest_paths:
        name = filenames_present[path]
        content = fetch_raw_file(owner, repo, branch, path)
        if content is None:
            continue

        keys = _extract_dependency_keys(name, content)
        haystack = " ".join(keys) if len(keys) > 1 else (keys.pop() if keys else "")

        for signal, (framework_name, category) in FRAMEWORK_SIGNALS.items():
            if signal in haystack or signal in keys:
                if framework_name not in frameworks_found:
                    frameworks_found.append(framework_name)
                categories_found.add(category)

        for signal, db_name in DATABASE_SIGNALS.items():
            if signal in haystack:
                databases_found.add(db_name)

    # Folder-based hints for Database category even without a matched manifest
    # keyword (e.g. a bare "migrations" or "prisma" directory).
    for f in files:
        lower_path = f["path"].lower()
        if "migrations/" in lower_path or "/prisma/" in lower_path or lower_path.endswith(".sql"):
            categories_found.add("Database")
            break

    return {
        "frameworks": frameworks_found,
        "categories": sorted(categories_found),
        "databases": sorted(databases_found),
        "manifests_checked": [filenames_present[p] for p in manifest_paths],
    }


# ---------------------------------------------------------------------------
# Component / API route heuristics
# ---------------------------------------------------------------------------
COMPONENT_EXTENSIONS = {".jsx", ".tsx", ".vue", ".svelte"}
ROUTE_HINT_DIR_NAMES = {"routes", "api", "controllers", "endpoints"}
ROUTE_HINT_FILE_NAMES = {"urls.py", "routes.py", "router.py"}


def estimate_components_and_routes(files: list) -> dict:
    component_count = sum(
        1 for f in files
        if os.path.splitext(f["path"])[1].lower() in COMPONENT_EXTENSIONS
    )

    route_count = 0
    for f in files:
        path_lower = f["path"].lower()
        parts = path_lower.split("/")
        base = os.path.basename(path_lower)
        if any(part in ROUTE_HINT_DIR_NAMES for part in parts[:-1]) and \
           os.path.splitext(base)[1] in {".js", ".ts", ".py", ".java", ".go", ".rb", ".php"}:
            route_count += 1
        elif base in ROUTE_HINT_FILE_NAMES:
            route_count += 1

    return {"components": component_count, "api_routes": route_count}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def analyze_repository(owner: str, repo: str, branch: str, raw_tree: list,
                        primary_languages: dict, progress_callback=None) -> dict:
    """
    Runs the full Phase 2 analysis pipeline and returns a single dict
    ready to render in the UI.
    """
    files = filter_tree(raw_tree)

    loc_result = count_lines_of_code(owner, repo, branch, files, progress_callback=progress_callback)
    fw_result = detect_frameworks_and_databases(owner, repo, branch, files)
    comp_result = estimate_components_and_routes(files)

    top_language = max(primary_languages, key=primary_languages.get) if primary_languages else "Unknown"

    return {
        "primary_language": top_language,
        "package_manager": detect_package_manager(files),
        "frameworks": fw_result["frameworks"],
        "categories": fw_result["categories"],
        "databases": fw_result["databases"],
        "manifests_checked": fw_result["manifests_checked"],
        "file_count": len(files),
        "loc": loc_result,
        "file_type_distribution": file_type_distribution(files),
        "largest_files": largest_files(files),
        "components": comp_result["components"],
        "api_routes": comp_result["api_routes"],
    }