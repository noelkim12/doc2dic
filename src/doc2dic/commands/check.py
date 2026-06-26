"""Run deterministic document consistency checks."""

from pathlib import Path
from typing import Annotated

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.services.conflict_detector import analyze_document
from doc2dic.services.document_check import check_document
from doc2dic.services.document_parser import UnsupportedDocumentFormatError
from doc2dic.storage import open_database

app = typer.Typer(
    help="Run glossary consistency checks.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def check(
    paths: Annotated[
        list[str] | None,
        typer.Argument(help="Markdown or TXT document to check."),
    ] = None,
    write_issues: Annotated[
        bool,
        typer.Option(
            "--write-issues",
            help="Persist generated review issues to the local database.",
        ),
    ] = False,
) -> None:
    """Parse a document, persist occurrences, and optionally write issues."""
    path, should_write_issues = _parse_check_args(paths, write_issues)
    if path is None:
        typer.echo("Pass a Markdown or TXT path to run checks.")
        raise typer.Exit(code=0)
    try:
        state = discover_project(Path.cwd())
        with open_database(state.db_path) as connection:
            if should_write_issues:
                analysis = analyze_document(connection, path, write_issues=True)
                result = analysis.check
                issue_count = len(analysis.all_issues)
            else:
                result = check_document(connection, path, write_issues=False)
                issue_count = len(result.issues)
    except ProjectNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    except UnsupportedDocumentFormatError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    typer.echo(f"Document: {result.document.title}")
    typer.echo(f"Chunks: {len(result.chunks)}")
    typer.echo(f"Occurrences: {len(result.occurrences)}")
    typer.echo(f"Issues: {issue_count}")
    if should_write_issues:
        typer.echo("Issues written: yes")
    else:
        typer.echo("Issues written: no")


def _parse_check_args(
    paths: list[str] | None,
    write_issues: bool,
) -> tuple[Path | None, bool]:
    """Support `doc2dic check <path> --write-issues` under a Typer group."""
    if paths is None:
        return None, write_issues
    remaining: list[str] = []
    should_write_issues = write_issues
    for value in paths:
        if value == "--write-issues":
            should_write_issues = True
            continue
        remaining.append(value)
    if len(remaining) > 1:
        message = "Pass exactly one Markdown or TXT path."
        raise typer.BadParameter(message)
    if len(remaining) == 0:
        return None, should_write_issues
    return Path(remaining[0]), should_write_issues
