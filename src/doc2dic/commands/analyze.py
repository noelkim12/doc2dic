"""Analyze project documents for glossary conflicts."""

from pathlib import Path
from typing import Annotated

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.services.conflict_detector import analyze_document
from doc2dic.services.document_parser import UnsupportedDocumentFormatError
from doc2dic.storage import open_database

app = typer.Typer(
    help="Analyze project documents for glossary candidates.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def analyze(
    paths: Annotated[
        list[str] | None,
        typer.Argument(help="Markdown or TXT document to analyze."),
    ] = None,
    write_issues: Annotated[
        bool,
        typer.Option(
            "--write-issues/--no-write-issues",
            help="Persist generated review issues to the local database.",
        ),
    ] = True,
) -> None:
    """Run provider-backed conflict analysis for one document."""
    path = _parse_analyze_args(paths)
    if path is None:
        typer.echo("Pass a Markdown or TXT path to run analysis.")
        raise typer.Exit(code=0)
    try:
        state = discover_project(Path.cwd())
        with open_database(state.db_path) as connection:
            result = analyze_document(connection, path, write_issues=write_issues)
    except ProjectNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    except UnsupportedDocumentFormatError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=2) from error

    typer.echo(f"Document: {result.check.document.title}")
    typer.echo(f"Provider: {result.provider or 'none'}")
    typer.echo(f"Candidates: {len(result.candidates)}")
    typer.echo(f"Rejected findings: {len(result.rejected_findings)}")
    typer.echo(f"Issues: {len(result.all_issues)}")
    vector_enabled = str(result.vector_candidates.enabled).lower()
    typer.echo(f"Vector candidates enabled: {vector_enabled}")
    if result.failure is not None:
        typer.echo(f"Analysis failure: {result.failure.code.value}")
    if write_issues:
        typer.echo("Issues written: yes")
    else:
        typer.echo("Issues written: no")


def _parse_analyze_args(paths: list[str] | None) -> Path | None:
    """Support one document path under a Typer group callback."""
    if paths is None or len(paths) == 0:
        return None
    if len(paths) > 1:
        message = "Pass exactly one Markdown or TXT path."
        raise typer.BadParameter(message)
    return Path(paths[0])
