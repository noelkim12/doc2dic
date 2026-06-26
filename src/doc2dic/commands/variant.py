"""Variant command group."""

from typing import Annotated

import typer

from doc2dic.commands.glossary_context import glossary_service
from doc2dic.domain import TermVariantType
from doc2dic.services.glossary_service import CreateVariantInput

app = typer.Typer(help="Manage term variants for concepts.")


@app.callback()
def variant() -> None:
    """Show variant command group help."""


@app.command("add")
def add_variant(
    concept_id: Annotated[str, typer.Argument(help="Concept id.")],
    label: Annotated[str, typer.Argument(help="Variant label.")],
    variant_type: Annotated[
        TermVariantType,
        typer.Option("--type", help="Variant type."),
    ] = TermVariantType.ALIAS,
    language: Annotated[str, typer.Option("--language")] = "unknown",
    reason: Annotated[str | None, typer.Option("--reason")] = None,
) -> None:
    """Add a term variant to a concept."""
    with glossary_service() as service:
        term_variant = service.add_variant(
            CreateVariantInput(
                concept_id=concept_id,
                label=label,
                variant_type=variant_type,
                language=language,
                reason=reason,
            ),
        )
    typer.echo(f"Created variant: {term_variant.id}")
