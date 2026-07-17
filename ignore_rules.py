"""
ignore_rules.py
---------------
Static lookup tables used by analyzer.py: which paths to skip, how to
map file extensions to languages, and which manifest files signal a
particular framework or package manager.
"""

# Directories we never want to analyze (build output, deps, VCS internals).
IGNORED_DIR_NAMES = {
    ".git", "node_modules", "dist", "build", "venv", ".venv", "env",
    "__pycache__", ".next", ".nuxt", "target", "vendor", "coverage",
    ".pytest_cache", ".mypy_cache", ".idea", ".vscode", "out", "bin",
    "obj", ".tox", "site-packages", ".cache", "public/assets",
}

# Individual files we never want to analyze regardless of directory.
IGNORED_FILE_NAMES = {
    ".DS_Store", "Thumbs.db",
}

# Extensions treated as binary/non-code -> excluded from LOC counting.
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar",
    ".lock",  # lock files are code-ish but not meaningful LOC
}

# Extension -> human readable language name.
EXTENSION_LANGUAGE_MAP = {
    ".py": "Python", ".ipynb": "Jupyter Notebook",
    ".js": "JavaScript", ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript", ".tsx": "TypeScript (TSX)",
    ".java": "Java", ".kt": "Kotlin", ".scala": "Scala",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".c": "C", ".h": "C Header", ".cpp": "C++", ".hpp": "C++ Header",
    ".cs": "C#", ".swift": "Swift", ".m": "Objective-C",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "Sass",
    ".less": "Less", ".vue": "Vue", ".svelte": "Svelte",
    ".sql": "SQL", ".sh": "Shell", ".bash": "Shell",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".xml": "XML",
    ".md": "Markdown", ".dockerfile": "Docker", ".r": "R",
    ".dart": "Dart", ".lua": "Lua", ".pl": "Perl", ".ex": "Elixir",
    ".exs": "Elixir",
}

# Files that indicate a package manager, mapped to its display name.
# Checked by exact filename match.
PACKAGE_MANAGER_FILES = {
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "poetry.lock": "poetry",
    "Pipfile.lock": "pipenv",
    "Pipfile": "pipenv",
    "Gemfile.lock": "bundler",
    "go.sum": "go modules",
    "Cargo.lock": "cargo",
    "composer.lock": "composer",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "build.gradle.kts": "gradle",
}

# Manifest files worth downloading and inspecting for framework detection.
# path suffix -> parser hint used in analyzer.py
FRAMEWORK_MANIFEST_FILES = {
    "package.json": "json",
    "requirements.txt": "text",
    "pyproject.toml": "text",
    "Pipfile": "text",
    "Gemfile": "text",
    "pom.xml": "text",
    "build.gradle": "text",
    "build.gradle.kts": "text",
    "go.mod": "text",
    "Cargo.toml": "text",
    "composer.json": "json",
}

# Dependency/keyword -> (framework name, category)
# Category is one of: Frontend, Backend, Full-Stack, Mobile, Data/ML
FRAMEWORK_SIGNALS = {
    "react": ("React", "Frontend"),
    "next": ("Next.js", "Frontend"),
    "vue": ("Vue.js", "Frontend"),
    "nuxt": ("Nuxt.js", "Frontend"),
    "@angular/core": ("Angular", "Frontend"),
    "svelte": ("Svelte", "Frontend"),
    "gatsby": ("Gatsby", "Frontend"),
    "express": ("Express", "Backend"),
    "koa": ("Koa", "Backend"),
    "fastify": ("Fastify", "Backend"),
    "@nestjs/core": ("NestJS", "Backend"),
    "electron": ("Electron", "Frontend"),
    "django": ("Django", "Backend"),
    "flask": ("Flask", "Backend"),
    "fastapi": ("FastAPI", "Backend"),
    "tornado": ("Tornado", "Backend"),
    "pyramid": ("Pyramid", "Backend"),
    "rails": ("Ruby on Rails", "Backend"),
    "sinatra": ("Sinatra", "Backend"),
    "spring-boot": ("Spring Boot", "Backend"),
    "springframework": ("Spring", "Backend"),
    "laravel/framework": ("Laravel", "Backend"),
    "symfony": ("Symfony", "Backend"),
    "gin-gonic": ("Gin", "Backend"),
    "labstack/echo": ("Echo", "Backend"),
    "gofiber/fiber": ("Fiber", "Backend"),
    "actix-web": ("Actix Web", "Backend"),
    "rocket": ("Rocket", "Backend"),
    "axum": ("Axum", "Backend"),
    "streamlit": ("Streamlit", "Frontend"),
    "torch": ("PyTorch", "Data/ML"),
    "tensorflow": ("TensorFlow", "Data/ML"),
}

# Keyword -> database name, searched inside manifest file text.
DATABASE_SIGNALS = {
    "postgres": "PostgreSQL", "psycopg2": "PostgreSQL", "pg": "PostgreSQL",
    "mysql": "MySQL", "mysql2": "MySQL",
    "mongodb": "MongoDB", "mongoose": "MongoDB", "pymongo": "MongoDB",
    "sqlite": "SQLite", "sqlite3": "SQLite",
    "redis": "Redis", "prisma": "Prisma ORM", "sqlalchemy": "SQLAlchemy",
    "firebase": "Firebase", "supabase": "Supabase", "dynamodb": "DynamoDB",
    "cassandra": "Cassandra", "elasticsearch": "Elasticsearch",
}