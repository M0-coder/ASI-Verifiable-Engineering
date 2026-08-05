#!/usr/bin/env python3
"""Validate an Agent Skills package and ASI repository invariants."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SECRET_PATTERNS = {
    "GitHub classic token": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "GitHub fine-grained token": re.compile(
        r"github_pat_[A-Za-z0-9_]{20,}"
    ),
    "OpenAI-style key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Private key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
}

REQUIRED_PACKAGE_FILES = {
    "SKILL.md",
    "references/core-doctrine.md",
    "references/annex-a-ai-code.md",
    "references/annex-b-assurance.md",
    "references/annex-c-control-matrix.md",
    "references/annex-d-policy-as-code.md",
    "references/annex-e-automated-acceptance.md",
    "assets/policy.example.yml",
    "assets/audit-report.md",
    "assets/change-budget.md",
    "assets/evidence-manifest.example.json",
    "scripts/check_format.py",
    "scripts/evaluate_change.py",
    "scripts/generate_ci_evidence.py",
    "scripts/run_gate.py",
    "scripts/scan_secrets.py",
    "scripts/scan_supply_chain.py",
    "scripts/validate_evidence.py",
    "scripts/validate_policy.py",
    "scripts/verify_change_budget.py",
}

REQUIRED_REPOSITORY_FILES = {
    ".asi/change-budget.json",
    ".asi/policy.yml",
    ".github/workflows/validate-skill.yml",
    "mypy.ini",
    "requirements-ci.lock",
    "tests/test_adversarial_controls.py",
    "tests/test_integration_evidence.py",
}


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError(
            "SKILL.md must begin with YAML frontmatter delimited by ---."
        )
    closing = text.find("\n---\n", 4)
    if closing == -1:
        raise ValueError("SKILL.md frontmatter is not closed with ---.")

    raw = text[4:closing]
    body = text[closing + 5 :]
    fields: dict[str, str] = {}
    current_parent: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and current_parent:
            key, separator, value = line.strip().partition(":")
            if separator:
                fields[f"{current_parent}.{key}"] = value.strip().strip('"\'')
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Invalid frontmatter line: {line!r}")
        key = key.strip()
        value = value.strip().strip('"\'')
        if value:
            fields[key] = value
            current_parent = None
        else:
            current_parent = key
    return fields, body


def repository_root(skill_dir: Path) -> Path:
    current = skill_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "VERSION").is_file() and (candidate / ".github").exists():
            return candidate
    raise ValueError("Could not locate repository root from skill directory.")


def _has_invalid_trailing_whitespace(path: Path, content: str) -> bool:
    for line in content.splitlines(True):
        raw = line.rstrip("\n\r")
        trailing_spaces = len(raw) - len(raw.rstrip(" "))
        if trailing_spaces == 0:
            continue
        if path.suffix.lower() == ".md" and trailing_spaces == 2:
            continue
        return True
    return False


def validate_package(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    skill_dir = skill_dir.resolve()
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [f"Missing required file: {skill_file}"]

    text = skill_file.read_text(encoding="utf-8")
    try:
        fields, body = parse_frontmatter(text)
    except ValueError as exc:
        return [str(exc)]

    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name:
        errors.append("Frontmatter field `name` is required.")
    elif len(name) > 64:
        errors.append("Frontmatter `name` exceeds 64 characters.")
    elif not NAME_RE.fullmatch(name):
        errors.append(
            "Frontmatter `name` must contain lowercase letters, numbers, "
            "and single hyphens only."
        )
    elif name != skill_dir.name:
        errors.append(
            f"Frontmatter name {name!r} must match directory {skill_dir.name!r}."
        )

    if not description:
        errors.append("Frontmatter field `description` is required.")
    elif len(description) > 1024:
        errors.append("Frontmatter `description` exceeds 1024 characters.")
    elif "use" not in description.lower() and "ús" not in description.lower():
        errors.append("Description should state when to use the skill.")

    compatibility = fields.get("compatibility")
    if compatibility and len(compatibility) > 500:
        errors.append("Frontmatter `compatibility` exceeds 500 characters.")
    if len(text.splitlines()) > 500:
        errors.append("SKILL.md must remain at or below 500 lines.")

    missing_package = sorted(
        path for path in REQUIRED_PACKAGE_FILES if not (skill_dir / path).is_file()
    )
    if missing_package:
        errors.append("Missing package files: " + ", ".join(missing_package))

    for target in LINK_RE.findall(body):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if clean and not (skill_dir / clean).exists():
            errors.append(f"Broken local reference in SKILL.md: {target}")
        if clean.count("/") > 1:
            errors.append(
                "Reference is nested too deeply for progressive disclosure: "
                f"{target}"
            )

    try:
        root = repository_root(skill_dir)
    except ValueError as exc:
        errors.append(str(exc))
        return errors

    missing_repository = sorted(
        path for path in REQUIRED_REPOSITORY_FILES if not (root / path).is_file()
    )
    if missing_repository:
        errors.append(
            "Missing repository controls: " + ", ".join(missing_repository)
        )
    if (root / ".asi" / "evidence-inputs").exists():
        errors.append("Legacy .asi/evidence-inputs directory must not exist.")

    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if fields.get("metadata.version") != version:
        errors.append(
            f"metadata.version {fields.get('metadata.version')!r} does not "
            f"match VERSION {version!r}."
        )

    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if _has_invalid_trailing_whitespace(path, content):
            errors.append(
                f"Invalid trailing whitespace detected: {path.relative_to(root)}"
            )
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                errors.append(
                    f"Potential {label} detected in {path.relative_to(root)}"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args(argv)
    errors = validate_package(args.skill_dir)
    if errors:
        print("ASI Skill validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"ASI Skill package is valid: {args.skill_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
