"""Dependency-free checks for this package's deliberately simple YAML layout.

This is not a general YAML parser or a behavioral evaluation of the skill.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/learnmed"


def validate():
    content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", content, re.S)
    assert match, "Missing frontmatter"
    fields = {}
    for line in match[1].splitlines():
        key, separator, value = line.partition(": ")
        assert separator and key in {"name", "description"}, "Unexpected YAML layout"
        assert key not in fields, "Repeated metadata key"
        fields[key] = value
    assert set(fields) == {"name", "description"}
    assert fields["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"])
    assert 0 < len(fields["description"]) <= 1024
    assert ": " not in fields["description"] and " #" not in fields["description"]
    assert fields["description"].startswith("Use when ")
    assert len(content.splitlines()) < 500
    ui = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
    for line in ui.splitlines():
        if re.match(r"  (display_name|short_description|default_prompt):", line):
            key, value = line.strip().split(": ", 1)
            parsed = json.loads(value)
            assert isinstance(parsed, str)
            if key == "short_description":
                assert 25 <= len(parsed) <= 64
            if key == "default_prompt":
                assert "$learnmed" in parsed
    assert "  allow_implicit_invocation: true" in ui
    checked_links = 0
    for file in [ROOT / "README.md", *SKILL.rglob("*.md"), *ROOT.glob("docs/*.md")]:
        body = file.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", body):
            if re.match(r"[a-z]+://|#", target):
                continue
            resolved = (file.parent / target.split("#")[0]).resolve()
            resolved.relative_to(ROOT)
            assert resolved.exists(), f"Broken resource link in {file}: {target}"
            checked_links += 1
        assert not re.search(r"\[TODO:|\bTBD\b|PLACEHOLDER", body)
    for file in [*SKILL.rglob("*.json"), ROOT / "docs/evaluation-scenarios.json"]:
        json.loads(file.read_text(encoding="utf-8"))
    print(f"Package checks passed: metadata, UI, JSON, {checked_links} relative links.")


if __name__ == "__main__":
    validate()
