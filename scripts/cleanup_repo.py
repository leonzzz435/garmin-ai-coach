#!/usr/bin/env python3
"""
Repo cleanup utility:
- Remove internal docstrings (module/class/function) across the codebase
- Delete commented-out code lines
- Replace print(...) calls with logger.info(...) and inject logging boilerplate

Retention policy (Option A):
- Keep docstrings only in entry points/orchestrator facades:
  - main.py
  - services/ai/langchain/master_orchestrator.py
  - services/ai/langchain/analysis_orchestrator.py
  - services/ai/langchain/weekly_plan_orchestrator.py

Usage:
  Dry run (summary only):
    python scripts/cleanup_repo.py --dry-run

  Apply changes:
    python scripts/cleanup_repo.py --apply
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path


def read_text_with_fallback(path: Path) -> tuple[str, str]:
    """
    Read text from path using multiple encodings.
    Returns (text, encoding_used).
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc), enc
        except UnicodeDecodeError:
            continue
    # Last resort: ignore errors under utf-8 to proceed
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return f.read(), "utf-8-ignored"


# Directories/files excluded from processing
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".ipynb_checkpoints",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".pixi",
    ".idea",
    ".vscode",
    "build",
    "dist",
    "data",
    "logs",
    "notebooks",
}

# Exclude this script itself
EXCLUDE_FILES = {
    "scripts/cleanup_repo.py",
}

# Only process source directories within this repo
ALLOW_DIRS = {
    "bot",
    "core",
    "services",
    "utils",
    "scripts",
    "config",
}

# Files where docstrings should be preserved (Option A)
DOCSTRING_KEEP_PATHS = {
    "main.py",
    "services/ai/langchain/master_orchestrator.py",
    "services/ai/langchain/analysis_orchestrator.py",
    "services/ai/langchain/weekly_plan_orchestrator.py",
}

# Heuristic to detect commented-out code lines
COMMENTED_CODE_RE = re.compile(
    r"^\s*#\s*(?:from\b|import\b|class\b|def\b|if\b|for\b|while\b|try\b|except\b|with\b|return\b|await\b|async\b|lambda\b|@|\w+\s*=)"
)

# Detect print calls for naive replacement
PRINT_CALL_RE = re.compile(r"(?<!\w)print\s*\(")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def rel_path(path: Path) -> str:
    try:
        return path.relative_to(project_root()).as_posix()
    except Exception:
        return path.as_posix()


def should_exclude(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    rp = rel_path(path)
    if rp in EXCLUDE_FILES:
        return True
    return False


def iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*.py"):
        if should_exclude(p):
            continue
        rp = rel_path(p)
        # Only include repo source directories or root-level .py files
        if "/" in rp:
            first = rp.split("/", 1)[0]
            if first not in ALLOW_DIRS:
                continue
        files.append(p)
    return files


def _is_str_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Expr):
        v = getattr(node, "value", None)
        if isinstance(v, ast.Str):
            return True
        if isinstance(v, ast.Constant) and isinstance(getattr(v, "value", None), str):
            return True
    return False


def find_docstring_spans(tree: ast.AST) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []

    # Module level
    if isinstance(tree, ast.Module) and tree.body:
        first = tree.body[0]
        if _is_str_expr(first):
            start = getattr(first, "lineno", None)
            end = getattr(first, "end_lineno", None)
            if start and end:
                spans.append((start, end))

    # Class / Function / AsyncFunction level
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body:
                first = node.body[0]
                if _is_str_expr(first):
                    start = getattr(first, "lineno", None)
                    end = getattr(first, "end_lineno", None)
                    if start and end:
                        spans.append((start, end))

    return spans


def remove_docstrings(source: str, keep: bool) -> tuple[str, int]:
    if keep:
        return source, 0

    try:
        tree = ast.parse(source)
    except SyntaxError:
        # If parsing fails, skip docstring removal for safety
        return source, 0

    spans = find_docstring_spans(tree)
    if not spans:
        return source, 0

    lines = source.splitlines(keepends=True)
    removed = 0

    # Remove from bottom to top to keep indexes stable
    for start, end in sorted(spans, key=lambda x: (x[0], x[1]), reverse=True):
        # Convert to 0-based inclusive range
        sidx = max(0, start - 1)
        eidx = min(len(lines) - 1, end - 1)
        for i in range(sidx, eidx + 1):
            if lines[i].strip():
                removed += 1
            lines[i] = ""

    return "".join(lines), removed


def remove_commented_out_code(source: str) -> tuple[str, int]:
    count = 0
    out_lines: list[str] = []
    for ln in source.splitlines(keepends=True):
        if COMMENTED_CODE_RE.match(ln):
            count += 1
            continue
        out_lines.append(ln)
    return "".join(out_lines), count


def ensure_logging_boilerplate(lines: list[str]) -> tuple[list[str], bool, bool]:
    """
    Ensure 'import logging' and 'logger = logging.getLogger(__name__)' exist.
    Returns (new_lines, added_import, added_logger_var)
    """
    import_exists = any(re.match(r"^\s*import\s+logging\b", l) for l in lines) or any(
        re.match(r"^\s*from\s+logging\s+import\b", l) for l in lines
    )
    logger_exists = any(
        re.match(r"^\s*logger\s*=\s*logging\.getLogger\(__name__\)\s*$", l) for l in lines
    )

    added_import = False
    added_logger = False

    # Find shebang/encoding header
    insert_at = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    # Skip encoding comment if present
    if insert_at < len(lines) and re.match(r"^#.*coding[:=]\s*utf-?8", lines[insert_at] or ""):
        insert_at += 1

    # Find last import line within first 100 lines
    last_import_idx = -1
    for idx, l in enumerate(lines[: min(100, len(lines))]):
        if re.match(r"^\s*(?:from\s+\S+\s+import|import\s+\S+)", l):
            last_import_idx = idx

    insertion_index = last_import_idx + 1 if last_import_idx != -1 else insert_at

    if not import_exists:
        lines.insert(insertion_index, "import logging\n")
        added_import = True
        insertion_index += 1

    if not logger_exists:
        lines.insert(insertion_index, "logger = logging.getLogger(__name__)\n")
        added_logger = True

    return lines, added_import, added_logger


def replace_prints_with_logging(source: str) -> tuple[str, int, bool, bool]:
    if "print(" not in source:
        return source, 0, False, False

    # Replace print( with logger.info(
    new_source, num = PRINT_CALL_RE.subn("logger.info(", source)

    if num == 0:
        return source, 0, False, False

    # Inject logging import and logger variable if needed
    lines = new_source.splitlines(keepends=True)
    lines, added_import, added_logger = ensure_logging_boilerplate(lines)

    return "".join(lines), num, added_import, added_logger


def process_file(path: Path) -> dict[str, int | bool | str]:
    rp = rel_path(path)
    text, encoding_used = read_text_with_fallback(path)

    keep_docs = rp in DOCSTRING_KEEP_PATHS

    # 1) strip docstrings
    after_docs, docs_removed = remove_docstrings(text, keep_docs)

    # 2) remove commented-out code lines
    after_comments, commented_removed = remove_commented_out_code(after_docs)

    # 3) replace print(...) with logger.info(...)
    after_prints, prints_replaced, added_import, added_logger = replace_prints_with_logging(
        after_comments
    )

    changed = after_prints != text
    return {
        "rel_path": rp,
        "changed": changed,
        "docstrings_removed": docs_removed,
        "commented_code_removed": commented_removed,
        "prints_replaced": prints_replaced,
        "added_import_logging": added_import,
        "added_logger_var": added_logger,
        "new_text": after_prints,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Clean up repo per Option A policy")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to files (otherwise runs in dry-run mode)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without changing files (default)"
    )
    args = parser.parse_args(argv)

    apply_changes = args.apply and not args.dry_run

    root = project_root()
    py_files = iter_python_files(root)

    totals = {
        "files_touched": 0,
        "docstrings_removed": 0,
        "commented_code_removed": 0,
        "prints_replaced": 0,
        "imports_added": 0,
        "loggers_added": 0,
    }

    per_file: list[dict[str, int | bool | str]] = []

    for f in py_files:
        res = process_file(f)
        per_file.append(res)
        if res["changed"]:
            totals["files_touched"] += 1
            totals["docstrings_removed"] += int(res["docstrings_removed"])  # type: ignore[arg-type]
            totals["commented_code_removed"] += int(res["commented_code_removed"])  # type: ignore[arg-type]
            totals["prints_replaced"] += int(res["prints_replaced"])  # type: ignore[arg-type]
            totals["imports_added"] += int(res["added_import_logging"])  # type: ignore[arg-type]
            totals["loggers_added"] += int(res["added_logger_var"])  # type: ignore[arg-type]
            if apply_changes:
                Path(f).write_text(res["new_text"], encoding="utf-8")  # type: ignore[index]

    # Summary
    mode = "APPLY" if apply_changes else "DRY-RUN"
    print(f"[cleanup_repo] Mode: {mode}")
    print(f"[cleanup_repo] Python files scanned: {len(py_files)}")
    print(
        "[cleanup_repo] Files changed: {files_touched}, docstrings removed: {doc}, commented-out code lines removed: {cm}, prints replaced: {pr}, imports added: {ia}, logger vars added: {la}".format(
            files_touched=totals["files_touched"],
            doc=totals["docstrings_removed"],
            cm=totals["commented_code_removed"],
            pr=totals["prints_replaced"],
            ia=totals["imports_added"],
            la=totals["loggers_added"],
        )
    )

    # Show top 20 changed files for visibility
    changed = [r for r in per_file if r["changed"]]
    changed.sort(key=lambda r: (int(r["docstrings_removed"]) + int(r["commented_code_removed"]) + int(r["prints_replaced"])), reverse=True)  # type: ignore[arg-type]
    for r in changed[:20]:
        print(
            " - {p}: docs={d}, commented={c}, prints={pr}".format(
                p=r["rel_path"],
                d=r["docstrings_removed"],
                c=r["commented_code_removed"],
                pr=r["prints_replaced"],
            )
        )

    if not apply_changes:
        print("\nDry-run only. Re-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
