"""Path boundaries shared by repository review and publication validation."""

from pathlib import PurePosixPath

ROOT_FILES = {"README.md", "AGENTS.md", "LICENSE", ".gitignore", ".env.example"}
SOURCE_ROOTS = {".github", "docs", "schema", "tools", "tests", "work"}
SOURCE_SUFFIXES = {".md", ".json", ".py", ".txt", ".yml", ".yaml", ".toml", ".sh"}
PRIVATE_ROOTS = {"reference", "LOCAL_CONTEXT.md"}
EXCLUDED_PARTS = {
    ".git", ".private", ".scratch", ".cache", ".aws", ".codex", ".agents",
    "archive", "archives", "node_modules", "__pycache__", ".pytest_cache",
    ".venv", "dist", ".astro", "coverage", "bin", "obj", "logs",
}
SECRET_NAMES = {".netrc", "credentials", "credentials.json", "secrets.json", "id_rsa", "id_ed25519"}
EXCLUDED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".log", ".pyc", ".pyo"}


def common_problem(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or "\\" in name or any(c in name for c in "\r\n\t\0") or ".." in path.parts or str(path) != name:
        return "noncanonical relative path"
    if path.parts[0] in PRIVATE_ROOTS or any(part.lower() in EXCLUDED_PARTS for part in path.parts):
        return "private, historical or generated path"
    if path.name.lower() in SECRET_NAMES or (path.name.startswith(".env") and path.name != ".env.example"):
        return "credential/environment filename"
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return "credential or generated file type"
    return None


def repository_path_problem(name):
    problem = common_problem(name)
    if problem:
        return problem
    path = PurePosixPath(name)
    if name in ROOT_FILES:
        return None
    if path.parts[0] not in SOURCE_ROOTS or path.suffix.lower() not in SOURCE_SUFFIXES:
        return "outside the maintained source allowlist"
    return None


def publication_path_problem(name):
    problem = common_problem(name)
    if problem:
        return problem
    # A publication explicitly lists its assets; never ingest repository tooling/queues.
    if PurePosixPath(name).parts[0] in SOURCE_ROOTS | {"README.md", "AGENTS.md", ".gitignore", ".env.example"}:
        return "repository-only material is not a publication asset"
    return None
