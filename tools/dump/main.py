#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tools/dump/main.py
"""Собирает код проекта TWAP parser в один текстовый файл."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Iterable

INCLUDE_DIRS = (
    "app",
    # "tests",
    "tools",
)

INCLUDE_FILES = (
    ".env.example",
    ".gitignore",
    "Dockerfile",
    "README.md",
    "docker-compose.yml",
    "requirements.txt",
)

IGNORE_DIRS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "mysql_data",
    "node_modules",
    "sessions",
    "venv",
    ".venv",
    "tools",
}

ALLOWED_NAMES = {
    ".env.example",
    ".gitignore",
    "dockerfile",
}

IGNORE_FILES = {
    ".env",
    ".DS_Store",
    "Thumbs.db",
    "project_bundle.txt",
    "files_list.txt",
}

ALLOWED_EXTS = {
    ".env",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".txt",
    ".yaml",
    ".yml",
}

MAX_FILE_SIZE_BYTES = 512 * 1024
DEFAULT_OUTPUT = "project_bundle.txt"
DEFAULT_FILES_LIST = "files_list.txt"


def is_project_root(path: Path) -> bool:
    return (
        (path / "docker-compose.yml").is_file()
        and (path / "requirements.txt").is_file()
        and (path / "app").is_dir()
        and (path / "app" / "cli.py").is_file()
    )


def detect_project_root(cli_root: str | None) -> Path:
    if cli_root:
        return Path(cli_root).expanduser().resolve()

    env_root = os.getenv("PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        if output:
            root = Path(output).resolve()
            if is_project_root(root):
                return root
    except Exception:
        pass

    script_path = Path(__file__).resolve()
    for path in (script_path.parent, *script_path.parents):
        if is_project_root(path):
            return path

    cwd = Path.cwd().resolve()
    for path in (cwd, *cwd.parents):
        if is_project_root(path):
            return path

    return cwd


def norm_abs(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def relpath(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve().relative_to(root.resolve())
    except ValueError:
        return None


def is_allowed_file(path: Path, include_env: bool) -> bool:
    name = path.name
    name_low = name.lower()

    if path.is_symlink() or name in IGNORE_FILES:
        return False

    if not include_env and name == ".env":
        return False

    if name_low in ALLOWED_NAMES:
        return True

    if name_low in {ext.lower() for ext in ALLOWED_EXTS}:
        return True

    return path.suffix.lower() in ALLOWED_EXTS


def is_ignored_path(path: Path, root: Path) -> bool:
    rel = relpath(path, root)
    return rel is not None and any(part in IGNORE_DIRS for part in rel.parts)


def walk_files(base: Path, root: Path, include_env: bool) -> list[Path]:
    if not base.exists():
        return []

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(base, topdown=True):
        dirnames[:] = [name for name in dirnames if name not in IGNORE_DIRS]

        for filename in filenames:
            path = Path(dirpath) / filename
            if not path.is_file() or is_ignored_path(path, root):
                continue
            if not is_allowed_file(path, include_env):
                continue
            if MAX_FILE_SIZE_BYTES and path.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
            files.append(path.resolve())

    return files


def collect_files(root: Path, include_env: bool) -> list[Path]:
    files: list[Path] = []

    for directory in INCLUDE_DIRS:
        files.extend(walk_files(root / directory, root, include_env))

    for filename in INCLUDE_FILES:
        path = root / filename
        if path.is_file() and is_allowed_file(path, include_env):
            files.append(path.resolve())

    if include_env and (root / ".env").is_file():
        files.append((root / ".env").resolve())

    return unique_sorted(files, root)


def unique_sorted(paths: Iterable[Path], root: Path) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []

    for path in paths:
        key = norm_abs(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)

    return sorted(result, key=lambda path: (relpath(path, root) or path).as_posix())


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def resolve_output_path(value: str, script_dir: Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (script_dir / path).resolve()


def write_files_list(files: list[Path], root: Path, path: Path) -> None:
    lines = [(relpath(file, root) or file).as_posix() for file in files]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_bundle(files: list[Path], root: Path, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(f"# Bundled from project root: {root.as_posix()}\n\n")

        for index, file in enumerate(files):
            rel = relpath(file, root)
            file_name = rel.as_posix() if rel else file.as_posix()
            output.write(f"# {file_name}\n")
            try:
                output.write(read_text(file).rstrip() + "\n")
            except Exception as exc:
                output.write(f"<<ERROR READING FILE: {exc}>>\n")

            if index != len(files) - 1:
                output.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Собрать TWAP project в один файл")
    parser.add_argument("--root", default=None, help="Корень проекта. По умолчанию автоопределение.")
    parser.add_argument("--out", default=DEFAULT_OUTPUT, help="Файл дампа рядом со скриптом.")
    parser.add_argument("--files-list", default=DEFAULT_FILES_LIST, help="Список файлов рядом со скриптом.")
    parser.add_argument("--include-env", action="store_true", help="Включить .env. По умолчанию .env исключён.")
    args = parser.parse_args()

    root = detect_project_root(args.root)
    script_dir = Path(__file__).resolve().parent
    out_path = resolve_output_path(args.out, script_dir)
    files_list_path = resolve_output_path(args.files_list, script_dir)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    files_list_path.parent.mkdir(parents=True, exist_ok=True)

    excluded = {norm_abs(out_path), norm_abs(files_list_path)}
    files = [file for file in collect_files(root, args.include_env) if norm_abs(file) not in excluded]

    write_files_list(files, root, files_list_path)
    write_bundle(files, root, out_path)

    print(f"OK: собрано файлов: {len(files)} -> {out_path}")
    print(f"FILES_LIST = {files_list_path}")
    print(f"ROOT = {root.as_posix()}")


if __name__ == "__main__":
    main()
