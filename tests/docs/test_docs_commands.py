from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[2]
DOC_PATHS: Final = (
    ROOT / "README.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "data-model.md",
    ROOT / "docs" / "opencode-workflow.md",
    ROOT / "docs" / "post-mvp.md",
)
KNOWN_STATUSES: Final = frozenset({"Current", "Planned MVP", "Conditional", "Post-MVP"})
COMMAND_PATTERN: Final = re.compile(
    r"`(doc2dic(?:\s+[^`|]+)?|python -m pytest\s+[^`|]+)`",
)
FORBIDDEN_MVP_CLAIMS: Final = (
    "Graphify observation import is MVP",
    "Graphify observation import is current",
    "Graphify observation import is complete",
    "Graphify import is MVP",
    "Graphify import is current",
    "Graphify import is complete",
)
FORBIDDEN_PUBLIC_INSTALLER_CLAIMS: Final = (
    "public curl installer is current",
    "public curl installer is complete",
    "public release hosting is current",
    "public release hosting is complete",
)


@dataclass(frozen=True, slots=True)
class DocumentedCommand:
    command: str
    status: str
    source: Path


def read_docs() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in DOC_PATHS}


def documented_commands() -> list[DocumentedCommand]:
    commands: list[DocumentedCommand] = []
    for path, content in read_docs().items():
        for line in content.splitlines():
            if "|" not in line or "`" not in line:
                continue
            columns = [column.strip() for column in line.strip().strip("|").split("|")]
            if len(columns) < 2:
                continue
            match = COMMAND_PATTERN.search(columns[0])
            if match is None:
                continue
            status = columns[1]
            commands.append(
                DocumentedCommand(command=match.group(1), status=status, source=path),
            )
    return commands


def run_command(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command.split(),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def command_exists(command: str) -> bool:
    help_result = run_command(f"{command} --help")
    if help_result.returncode == 0 and "Usage:" in help_result.stdout:
        return True

    result = run_command(command)
    combined = f"{result.stdout}\n{result.stderr}"
    return (
        result.returncode == 0
        or "Usage:" in combined
        or "Run `doc2dic init`" in combined
    )


def test_documented_commands_are_current_or_explicitly_labeled() -> None:
    commands = documented_commands()

    assert commands
    for command in commands:
        assert command.status in KNOWN_STATUSES, command


def test_current_doc2dic_commands_exist_in_cli_help() -> None:
    commands = documented_commands()

    for command in commands:
        if command.status != "Current" or not command.command.startswith("doc2dic"):
            continue
        assert command_exists(command.command.removesuffix(" --help")), command


def test_planned_or_deferred_doc2dic_commands_are_not_marked_current() -> None:
    commands = documented_commands()
    planned_commands = {
        command.command: command.status
        for command in commands
        if command.command.startswith("doc2dic") and "--help" not in command.command
    }

    assert (
        planned_commands["doc2dic check samples/docs/dungeon_draft.md --write-issues"]
        == "Current"
    )
    assert planned_commands["doc2dic concept list"] == "Current"
    assert planned_commands["doc2dic graph export --format graphify"] == "Current"
    assert (
        planned_commands["doc2dic graph import graphify-out/graph.json"]
        == "Post-MVP"
    )


def test_docs_defer_non_mvp_integrations() -> None:
    combined = "\n".join(read_docs().values())

    for required in (
        "DOCX ingestion | Post-MVP",
        "PDF ingestion | Post-MVP",
        "Google Docs | Post-MVP",
        "Notion | Post-MVP",
        "Confluence | Post-MVP",
        "Graphify observation import | Post-MVP",
    ):
        assert required in combined


def test_docs_do_not_claim_graphify_import_is_mvp() -> None:
    combined = "\n".join(read_docs().values())

    for forbidden in FORBIDDEN_MVP_CLAIMS:
        assert forbidden not in combined


def test_docs_do_not_claim_public_release_hosting_is_current() -> None:
    combined = "\n".join(read_docs().values()).lower()

    assert "public release hosting | conditional" in combined
    for forbidden in FORBIDDEN_PUBLIC_INSTALLER_CLAIMS:
        assert forbidden not in combined
