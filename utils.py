"""
utils.py
--------
Formatting and file-tree rendering helpers, kept separate from the
Streamlit UI code so they're easy to unit test later.
"""

from datetime import datetime


def format_number(n: int) -> str:
    """1234 -> '1.2k', 1200000 -> '1.2M'"""
    if n is None:
        return "0"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def format_date(iso_string: str) -> str:
    if not iso_string:
        return "Unknown"
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%b %d, %Y")
    except ValueError:
        return iso_string


def format_size(kb: int) -> str:
    if kb is None:
        return "0 KB"
    if kb >= 1024:
        return f"{kb / 1024:.1f} MB"
    return f"{kb} KB"


def languages_to_percentages(languages: dict) -> list:
    """
    Converts {'Python': 4000, 'HTML': 1000} into a sorted list of
    dicts with a percentage field, ready for a chart or table.
    """
    total = sum(languages.values()) or 1
    rows = [
        {"language": lang, "bytes": count, "percent": round(count / total * 100, 1)}
        for lang, count in languages.items()
    ]
    rows.sort(key=lambda r: r["bytes"], reverse=True)
    return rows


def build_tree_text(tree_items: list, max_entries: int = 2000) -> str:
    """
    Renders a flat GitHub tree listing (list of {path, type}) as an
    indented, sorted text tree similar to the `tree` CLI command.
    """
    items = sorted(tree_items, key=lambda i: i["path"])[:max_entries]

    lines = []
    for item in items:
        depth = item["path"].count("/")
        name = item["path"].split("/")[-1]
        prefix = "    " * depth + ("|-- " if depth > 0 else "")
        suffix = "/" if item["type"] == "dir" else ""
        lines.append(f"{prefix}{name}{suffix}")

    text = "\n".join(lines)
    if len(tree_items) > max_entries:
        text += f"\n\n... {len(tree_items) - max_entries} more entries not shown"
    return text


def build_tree_nested(tree_items: list) -> dict:
    """
    Converts the flat tree list into a nested dict structure:
    {"src": {"app.py": None, "utils": {"helpers.py": None}}}
    Leaves (files) map to None; directories map to a dict.
    """
    root = {}
    for item in sorted(tree_items, key=lambda i: i["path"]):
        parts = item["path"].split("/")
        node = root
        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            if is_last and item["type"] == "file":
                node[part] = None
            else:
                node = node.setdefault(part, {})
    return root