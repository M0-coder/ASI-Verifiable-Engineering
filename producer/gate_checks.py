#!/usr/bin/env python3
"""Deterministic stdlib-only technical checks for ASI pull-request evidence."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEXT_SUFFIXES = {".py", ".yml", ".yaml", ".json", ".md", ".txt"}


def git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def git_text(root: Path, *args: str) -> str:
    return git_bytes(root, *args).decode("utf-8").strip()


def changed_paths(root: Path, base_sha: str, evaluated_sha: str) -> list[Path]:
    output = git_text(
        root, "diff", "--name-only", "--diff-filter=ACMRT", base_sha, evaluated_sha
    )
    return [root / line for line in output.splitlines() if line]


def changed_python(root: Path, base_sha: str, evaluated_sha: str) -> list[Path]:
    return [
        path
        for path in changed_paths(root, base_sha, evaluated_sha)
        if path.suffix == ".py" and path.is_file()
    ]


def check_text_format(path: Path) -> list[str]:
    payload = path.read_bytes()
    errors: list[str] = []
    if b"\r\n" in payload:
        errors.append("CRLF line endings are forbidden")
    if payload and not payload.endswith(b"\n"):
        errors.append("file must end with a newline")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return ["file is not valid UTF-8"]
    for number, line in enumerate(text.splitlines(), start=1):
        if line.endswith((" ", "\t")):
            errors.append(f"line {number} has trailing whitespace")
    return errors


class LintVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.errors.append(f"line {node.lineno}: bare except is forbidden")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if any(alias.name == "*" for alias in node.names):
            self.errors.append(f"line {node.lineno}: wildcard import is forbidden")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            self.errors.append(f"line {node.lineno}: dynamic {node.func.id} is forbidden")
        self.generic_visit(node)


def lint_python(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [f"syntax error: {exc}"]
    visitor = LintVisitor()
    visitor.visit(tree)
    return visitor.errors


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def repository_local_modules(root: Path) -> set[str]:
    modules = {path.stem for path in root.rglob("*.py") if path.name != "__init__.py"}
    modules.update(path.name for path in root.iterdir() if path.is_dir())
    return modules


def secret_patterns() -> list[re.Pattern[str]]:
    github_classic = "gh" + r"[pousr]_[A-Za-z0-9]{30,}"
    github_fine = "github" + r"_pat_[A-Za-z0-9_]{50,}"
    aws_access = "AK" + r"IA[0-9A-Z]{16}"
    private_key = "-----BEGIN " + r"(?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
    return [
        re.compile(github_classic),
        re.compile(github_fine),
        re.compile(aws_access),
        re.compile(private_key),
    ]


def format_check(root: Path, base: str, evaluated: str) -> int:
    failures: list[str] = []
    for path in changed_paths(root, base, evaluated):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            failures.extend(
                f"{path.relative_to(root)}: {error}" for error in check_text_format(path)
            )
    if failures:
        print("\n".join(failures))
        return 1
    print("format_check: changed text is UTF-8/LF/newline-terminated without trailing whitespace")
    return 0


def lint_check(root: Path, base: str, evaluated: str) -> int:
    failures: list[str] = []
    files = changed_python(root, base, evaluated)
    for path in files:
        failures.extend(f"{path.relative_to(root)}: {error}" for error in lint_python(path))
    if failures:
        print("\n".join(failures))
        return 1
    print(f"lint: parsed {len(files)} changed Python files; no forbidden AST constructs")
    return 0


def build_check(root: Path, base: str, evaluated: str) -> int:
    import py_compile

    files = changed_python(root, base, evaluated)
    with tempfile.TemporaryDirectory(prefix="asi-build-") as tmp:
        for index, path in enumerate(files):
            py_compile.compile(
                str(path), cfile=str(Path(tmp) / f"{index}.pyc"), doraise=True
            )
    print(f"build: compiled {len(files)} changed Python files")
    return 0


def secret_scan(root: Path, base: str, evaluated: str) -> int:
    findings: list[str] = []
    patterns = secret_patterns()
    for path in changed_paths(root, base, evaluated):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in patterns):
                findings.append(f"{path.relative_to(root)}:{number}: high-confidence secret pattern")
    if findings:
        print("\n".join(findings))
        return 1
    print("secret_scan: no high-confidence credential/private-key patterns in changed text")
    return 0


def dependency_scan(root: Path, base: str, evaluated: str) -> int:
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    local = repository_local_modules(root)
    external: dict[str, list[str]] = {}
    for python_path in changed_python(root, base, evaluated):
        bad = sorted(
            module
            for module in imported_roots(python_path)
            if module not in stdlib and module not in local
        )
        if bad:
            external[str(python_path.relative_to(root))] = bad
    if external:
        for display_path, modules in sorted(external.items()):
            print(f"{display_path}: external imports: {', '.join(modules)}")
        return 1
    print("dependency_scan: changed Python uses only stdlib or repository-local modules")
    return 0


def rollback_check(root: Path, base: str, head: str, evaluated: str) -> int:
    subprocess.run(["git", "merge-base", "--is-ancestor", base, evaluated], cwd=root, check=True)
    subprocess.run(["git", "merge-base", "--is-ancestor", head, evaluated], cwd=root, check=True)
    patch = git_bytes(root, "diff", "--binary", base, evaluated)
    result = subprocess.run(
        ["git", "apply", "--check", "--reverse", "--whitespace=nowarn", "-"],
        cwd=root,
        input=patch,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode:
        print(result.stdout.decode("utf-8", errors="replace"))
        return result.returncode
    print("rollback_check: reverse application of exact base..evaluated diff is mechanically valid")
    return 0


def common_identity(subparser: argparse.ArgumentParser) -> None:
    subparser.add_argument("--base-sha", required=True)
    subparser.add_argument("--evaluated-sha", required=True)
    subparser.add_argument("--repo-root", default=".")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="check", required=True)
    for name in ("format", "lint", "build", "secret-scan", "dependency-scan"):
        common_identity(commands.add_parser(name))
    rollback = commands.add_parser("rollback")
    common_identity(rollback)
    rollback.add_argument("--head-sha", required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    root = Path(args.repo_root).resolve()
    if args.check == "format":
        return format_check(root, args.base_sha, args.evaluated_sha)
    if args.check == "lint":
        return lint_check(root, args.base_sha, args.evaluated_sha)
    if args.check == "build":
        return build_check(root, args.base_sha, args.evaluated_sha)
    if args.check == "secret-scan":
        return secret_scan(root, args.base_sha, args.evaluated_sha)
    if args.check == "dependency-scan":
        return dependency_scan(root, args.base_sha, args.evaluated_sha)
    if args.check == "rollback":
        return rollback_check(root, args.base_sha, args.head_sha, args.evaluated_sha)
    raise AssertionError(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
