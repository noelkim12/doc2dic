"""Root command registration for the doc2dic CLI."""

import typer

from doc2dic.commands import (
    analyze,
    check,
    concept,
    graph,
    init,
    install,
    review,
    serve,
    status,
    uninstall,
    variant,
)

app = typer.Typer(
    name="doc2dic",
    help="Build and review a local glossary from project documents.",
    no_args_is_help=True,
)

app.add_typer(init.app, name="init")
app.add_typer(status.app, name="status")
app.add_typer(concept.app, name="concept")
app.add_typer(variant.app, name="variant")
app.add_typer(review.app, name="review")
app.add_typer(check.app, name="check")
app.add_typer(analyze.app, name="analyze")
app.add_typer(graph.app, name="graph")
app.add_typer(serve.app, name="serve")
app.add_typer(install.app, name="install")
app.add_typer(uninstall.app, name="uninstall")


def main() -> None:
    """Run the doc2dic CLI."""
    app()
