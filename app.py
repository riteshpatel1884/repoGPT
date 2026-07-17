"""
GitHub Repository Explorer — Phase 1
-------------------------------------
Enter a GitHub repository URL (or owner/repo), fetch its metadata via the
GitHub REST API, and visualize the repo info, languages, and file tree.

Run with:
    streamlit run app.py
"""

import json
from datetime import datetime

import streamlit as st

from github_api import (
    GitHubAPIError,
    get_file_tree,
    get_languages,
    get_rate_limit,
    get_repo_info,
    parse_github_url,
)
from utils import (
    build_tree_text,
    format_date,
    format_number,
    format_size,
    languages_to_percentages,
)
from analyzer import MAX_FILES_FOR_LOC, analyze_repository

st.set_page_config(
    page_title="GitHub Repository Explorer",
    page_icon="🔎",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🔎 GitHub Explorer")
    st.caption("Phase 1 — Repository Explorer")

    token = st.text_input(
        "GitHub Personal Access Token (optional)",
        type="password",
        help=(
            "Without a token you get 60 requests/hour per IP. "
            "With a free token you get 5,000 requests/hour. "
            "Create one at github.com/settings/tokens (no scopes needed for public repos)."
        ),
    )

    if token:
        try:
            limit_info = get_rate_limit(token)
            st.success(
                f"Rate limit: {limit_info['remaining']}/{limit_info['limit']} remaining"
            )
        except GitHubAPIError as e:
            st.warning(str(e))

    st.divider()
    st.markdown(
        "**Next phases will add:**\n"
        "- RAG over code (chunking + embeddings)\n"
        "- AI summaries & architecture diagrams\n"
        "- Bug finding & code review\n"
        "- Interview & resume review modes"
    )

# ---------------------------------------------------------------------------
# Main input
# ---------------------------------------------------------------------------
st.title("GitHub Repository Explorer")
st.caption("Fetch and visualize any public GitHub repository.")

col1, col2 = st.columns([4, 1])
with col1:
    repo_input = st.text_input(
        "Repository URL or owner/repo",
        placeholder="https://github.com/streamlit/streamlit  or  streamlit/streamlit",
        label_visibility="collapsed",
    )
with col2:
    fetch_clicked = st.button("Analyze", type="primary", use_container_width=True)

# Persist results across reruns (e.g. when expanding the tree)
if "repo_data" not in st.session_state:
    st.session_state.repo_data = None
if "analysis_data" not in st.session_state:
    st.session_state.analysis_data = None

if fetch_clicked:
    if not repo_input.strip():
        st.warning("Please enter a repository URL or owner/repo.")
    else:
        try:
            with st.spinner("Fetching repository data..."):
                owner, repo = parse_github_url(repo_input)
                info = get_repo_info(owner, repo, token)
                languages = get_languages(owner, repo, token)
                tree, truncated = get_file_tree(owner, repo, info["default_branch"], token)

            st.session_state.repo_data = {
                "info": info,
                "languages": languages,
                "tree": tree,
                "truncated": truncated,
                "fetched_at": datetime.utcnow().isoformat() + "Z",
            }
            st.session_state.analysis_data = None  # new repo -> stale analysis
        except GitHubAPIError as e:
            st.session_state.repo_data = None
            st.error(str(e))

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
data = st.session_state.repo_data

if data:
    info = data["info"]
    languages = data["languages"]
    tree = data["tree"]

    # --- Header -------------------------------------------------------
    header_col, avatar_col = st.columns([5, 1])
    with header_col:
        st.subheader(f"{info['full_name']}")
        if info["description"]:
            st.write(info["description"])
        badges = []
        if info["archived"]:
            badges.append("🗄️ Archived")
        if info["is_fork"]:
            badges.append("🍴 Fork")
        if info["visibility"]:
            badges.append(f"👁️ {info['visibility'].capitalize()}")
        if badges:
            st.caption(" · ".join(badges))
        st.markdown(f"[View on GitHub]({info['html_url']})")
    with avatar_col:
        if info.get("owner_avatar"):
            st.image(info["owner_avatar"], width=80)

    st.divider()

    # --- Key metrics ----------------------------------------------------
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("⭐ Stars", format_number(info["stars"]))
    m2.metric("🍴 Forks", format_number(info["forks"]))
    m3.metric("🐛 Open Issues", format_number(info["open_issues"]))
    m4.metric("👀 Watchers", format_number(info["watchers"]))
    m5.metric("📦 Size", format_size(info["size_kb"]))
    m6.metric("🌿 Default Branch", info["default_branch"])

    st.divider()

    # --- Detail table -----------------------------------------------------
    detail_col, lang_col = st.columns([1, 1])

    with detail_col:
        st.markdown("#### Repository Details")
        st.table({
            "Field": [
                "Owner", "License", "Homepage", "Created",
                "Last Updated", "Last Push", "Topics",
            ],
            "Value": [
                info["owner"],
                info["license"] or "None",
                info["homepage"] or "—",
                format_date(info["created_at"]),
                format_date(info["updated_at"]),
                format_date(info["pushed_at"]),
                ", ".join(info["topics"]) if info["topics"] else "—",
            ],
        })

    with lang_col:
        st.markdown("#### Languages")
        if languages:
            lang_rows = languages_to_percentages(languages)
            chart_data = {row["language"]: row["percent"] for row in lang_rows}
            st.bar_chart(chart_data)
            st.dataframe(
                lang_rows,
                column_config={
                    "language": "Language",
                    "bytes": "Bytes",
                    "percent": st.column_config.NumberColumn("Percent", format="%.1f%%"),
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("No language data available for this repository.")

    st.divider()

    # --- File tree ----------------------------------------------------
    st.markdown("#### Repository File Tree")
    if data["truncated"]:
        st.warning(
            "This repository is very large — GitHub only returned a partial file tree."
        )
    st.caption(f"{len(tree)} files/folders")
    with st.expander("Show file tree", expanded=True):
        st.code(build_tree_text(tree), language="text")

    st.divider()

    # --- Phase 2: Code analysis ------------------------------------------
    st.markdown("#### Code Analysis")
    st.caption(
        f"Downloads and inspects up to {MAX_FILES_FOR_LOC} files (smallest first) to keep "
        "this fast and rate-limit friendly. `.git`, `node_modules`, `dist`, `build`, `venv` "
        "and similar noise directories are skipped automatically."
    )

    if st.button("Analyze Code", type="primary"):
        progress_bar = st.progress(0.0, text="Starting analysis...")

        def _on_progress(done, total):
            progress_bar.progress(
                done / total if total else 1.0,
                text=f"Reading files... {done}/{total}",
            )

        try:
            analysis = analyze_repository(
                info["owner"], info["name"], info["default_branch"],
                tree, languages, progress_callback=_on_progress,
            )
            st.session_state.analysis_data = analysis
        except Exception as e:  # noqa: BLE001 - surface any analysis failure to the user
            st.error(f"Analysis failed: {e}")
        finally:
            progress_bar.empty()

    analysis = st.session_state.analysis_data
    if analysis:
        loc = analysis["loc"]

        # --- Output summary, matching the requested card layout ---------
        category_label = " / ".join(analysis["categories"]) if analysis["categories"] else "Uncategorized"
        framework_label = ", ".join(analysis["frameworks"]) if analysis["frameworks"] else "No framework detected"

        st.markdown(
            f"##### {framework_label} Project\n"
            f"**{category_label}**"
        )

        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Files", format_number(analysis["file_count"]))
        a2.metric("Lines of Code", format_number(loc["total_loc"]))
        a3.metric("Components", format_number(analysis["components"]))
        a4.metric("API Routes", format_number(analysis["api_routes"]))

        st.caption(
            f"Primary language: **{analysis['primary_language']}**  ·  "
            f"Package manager: **{analysis['package_manager']}**  ·  "
            f"Databases detected: **{', '.join(analysis['databases']) or 'None'}**"
        )
        if loc["sample_capped"]:
            st.caption(
                f"LOC is estimated from a sample of {loc['files_counted']} files "
                f"(smallest-first) out of {analysis['file_count']} total — large repos are capped for speed."
            )

        detail_a, detail_b = st.columns(2)

        with detail_a:
            st.markdown("**File Type Distribution**")
            dist = analysis["file_type_distribution"][:12]
            st.bar_chart({row["extension"]: row["count"] for row in dist})
            st.dataframe(
                dist,
                column_config={"extension": "Extension", "count": "Files", "language": "Language"},
                hide_index=True,
                use_container_width=True,
            )

        with detail_b:
            st.markdown("**Largest Files**")
            st.dataframe(
                [
                    {"path": f["path"], "size": format_size(round(f.get("size", 0) / 1024, 1))}
                    for f in analysis["largest_files"]
                ],
                column_config={"path": "File", "size": "Size"},
                hide_index=True,
                use_container_width=True,
            )

        if analysis["manifests_checked"]:
            st.caption(f"Manifest files inspected: {', '.join(analysis['manifests_checked'])}")

    st.divider()

    # --- Download metadata ----------------------------------------------
    export_payload = {
        "repository": info,
        "languages": languages,
        "file_tree": tree,
        "truncated": data["truncated"],
        "fetched_at": data["fetched_at"],
        "code_analysis": st.session_state.analysis_data,
    }
    st.download_button(
        label="⬇️ Download repository metadata as JSON",
        data=json.dumps(export_payload, indent=2),
        file_name=f"{info['owner']}_{info['name']}_metadata.json",
        mime="application/json",
    )

else:
    st.info("Enter a GitHub repository above and click **Analyze** to get started.")