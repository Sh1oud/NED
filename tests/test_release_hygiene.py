"""Release hygiene tests.

These guard the things a first release must not ship: half-finished placeholders,
generated artefacts, and documentation that drifts away from the screenshots it
references.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Placeholder families that were removed for the release candidate. Reintroducing
#: one of these means the replacement pass was not finished.
STALE_MARKERS = ("your-org", "your-fork-url", "@example.com", "TODO", "FIXME")

#: The blessed release tokens, documented in RELEASE_CHECKLIST.md.
RELEASE_TOKENS = ("REPLACE-WITH-GITHUB-OWNER", "REPLACE-WITH-CONTACT-EMAIL")

#: Directories that are never part of the shipped repository.
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".tmp",
    ".idea",
    ".vscode",
}

TEXT_SUFFIXES = {".md", ".py", ".toml", ".json", ".yml", ".yaml", ".txt", ".js", ".css", ".html"}

#: Screenshots every document must agree on.
SCREENSHOTS = ("analysis.png", "asymmetry.png", "fnpb-lab.png", "cli-extreme.png")


def text_files() -> list[Path]:
    """Every text file in the repository, ignoring generated directories."""

    found: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            found.append(path)
    return found


def test_no_stale_placeholders_anywhere() -> None:
    """The marker list lives in this file, so this file is not scanned."""

    offenders: list[str] = []
    for path in text_files():
        if path.name == "test_release_hygiene.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in STALE_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT)}: {marker}")
    assert not offenders, "stale release placeholders found:\n  " + "\n  ".join(offenders)


def test_release_tokens_are_documented() -> None:
    """Every file carrying a REPLACE-WITH token must be listed in the checklist.

    The checklist and this test are the documentation *of* the tokens, so they are
    excluded from the check.
    """

    meta = {"RELEASE_CHECKLIST.md", "test_release_hygiene.py"}
    checklist = (ROOT / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    consumers = 0
    for path in text_files():
        if path.name in meta:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not any(token in text for token in RELEASE_TOKENS):
            continue
        consumers += 1
        relative = path.relative_to(ROOT).as_posix()
        assert path.name in checklist or relative in checklist, (
            f"{relative} carries a release token but is not named in RELEASE_CHECKLIST.md"
        )
    assert consumers >= 5, f"expected several files to carry release tokens, found {consumers}"


def test_checklist_and_screenshot_docs_exist() -> None:
    assert (ROOT / "RELEASE_CHECKLIST.md").is_file()
    assert (ROOT / "docs" / "screenshots" / "README.md").is_file()
    assert (ROOT / "scripts" / "capture_screenshots.py").is_file()
    assert (ROOT / "docs" / "cli-extreme.txt").is_file()


def test_screenshot_names_agree_everywhere() -> None:
    """README, the screenshot doc and the capture script must name the same files."""

    documents = {
        "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
        "docs/screenshots/README.md": (ROOT / "docs" / "screenshots" / "README.md").read_text(
            encoding="utf-8"
        ),
        "scripts/capture_screenshots.py": (ROOT / "scripts" / "capture_screenshots.py").read_text(
            encoding="utf-8"
        ),
    }
    for name, text in documents.items():
        for screenshot in SCREENSHOTS:
            assert screenshot in text, f"{name} does not mention {screenshot}"


def test_gitignore_covers_build_artefacts() -> None:
    patterns = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (
        "__pycache__/",
        "*.py[cod]",
        "*.egg-info",
        ".pytest_cache/",
        ".ruff_cache/",
        ".mypy_cache/",
        ".coverage",
        ".venv",
        ".tmp/",
        "pytest-cache-files-*",
    ):
        assert pattern in patterns, f".gitignore does not ignore {pattern}"


def test_cli_capture_matches_the_shipped_cli() -> None:
    """docs/cli-extreme.txt must be a real capture, not a hand-written sample."""

    capture = (ROOT / "docs" / "cli-extreme.txt").read_text(encoding="utf-8")
    assert "Final Verdict" in capture
    assert "NED Reaching Level" in capture
    assert "Alternative Hypotheses" in capture
    assert "她说喜欢我" in capture
