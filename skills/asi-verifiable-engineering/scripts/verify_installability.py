#!/usr/bin/env python3
"""Build, extract, and verify a deterministic portable Agent Skill archive."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

FRONTMATTER_NAME = re.compile(r"^name:\s*([a-z0-9-]+)\s*$", re.MULTILINE)
LOCAL_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)#]+)(?:#[^)]+)?\)")
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def package_files(skill_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in skill_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not permitted in a portable Skill: {path}")
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            raise ValueError(f"Generated Python artifact is not permitted: {path}")
        files.append(path)
    if not files:
        raise ValueError("The Skill package is empty.")
    return sorted(files, key=lambda item: item.relative_to(skill_dir).as_posix())


def validate_skill_tree(skill_dir: Path) -> dict[str, object]:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError("SKILL.md is missing.")
    text = skill_file.read_text(encoding="utf-8")
    match = FRONTMATTER_NAME.search(text)
    if not match:
        raise ValueError("SKILL.md frontmatter has no valid name.")
    if match.group(1) != skill_dir.name:
        raise ValueError("SKILL.md name does not match its package directory.")

    broken_links: list[str] = []
    for target in LOCAL_LINK.findall(text):
        candidate = skill_dir / target
        if not candidate.exists():
            broken_links.append(target)
    if broken_links:
        raise ValueError("Broken local links: " + ", ".join(sorted(broken_links)))

    python_files = sorted(skill_dir.rglob("*.py"))
    for path in python_files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    files = package_files(skill_dir)
    return {
        "name": skill_dir.name,
        "file_count": len(files),
        "python_file_count": len(python_files),
        "broken_links": broken_links,
    }


def build_archive(skill_dir: Path, archive: Path) -> list[Path]:
    files = package_files(skill_dir)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as bundle:
        for path in files:
            relative = Path(skill_dir.name) / path.relative_to(skill_dir)
            info = zipfile.ZipInfo(relative.as_posix(), FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    return files


def digest_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def verify_installability(skill_dir: Path) -> dict[str, object]:
    skill_dir = skill_dir.resolve()
    source_validation = validate_skill_tree(skill_dir)
    with tempfile.TemporaryDirectory(prefix="asi-skill-package-") as temp:
        temp_root = Path(temp)
        first_archive = temp_root / "skill-1.zip"
        second_archive = temp_root / "skill-2.zip"
        files = build_archive(skill_dir, first_archive)
        build_archive(skill_dir, second_archive)
        first_digest = sha256_file(first_archive)
        second_digest = sha256_file(second_archive)
        deterministic = first_digest == second_digest

        extract_root = temp_root / "extracted"
        with zipfile.ZipFile(first_archive) as bundle:
            for member in bundle.infolist():
                destination = (extract_root / member.filename).resolve()
                try:
                    destination.relative_to(extract_root.resolve())
                except ValueError as exc:
                    raise ValueError(
                        f"Archive contains an unsafe path: {member.filename}"
                    ) from exc
            bundle.extractall(extract_root)

        extracted_skill = extract_root / skill_dir.name
        extracted_validation = validate_skill_tree(extracted_skill)
        source_digests = digest_map(skill_dir)
        extracted_digests = digest_map(extracted_skill)
        content_preserved = source_digests == extracted_digests
        passed = deterministic and content_preserved
        return {
            "verification_version": 1,
            "package_name": skill_dir.name,
            "archive_format": "zip",
            "archive_digest": first_digest,
            "deterministic_rebuild": deterministic,
            "content_preserved_after_extract": content_preserved,
            "source_validation": source_validation,
            "extracted_validation": extracted_validation,
            "file_count": len(files),
            "limitations": [
                "This verifies portable package construction and extraction.",
                "It does not prove installation in a specific ChatGPT, Codex, or API account.",
            ],
            "passed": passed,
        }


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_installability.py SKILL_DIR", file=sys.stderr)
        return 2
    try:
        report = verify_installability(Path(sys.argv[1]))
    except (OSError, SyntaxError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Installability verification failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
