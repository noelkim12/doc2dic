"""Concept command group."""

from typing import Annotated

import typer

from doc2dic.commands.glossary_context import glossary_service
from doc2dic.domain import ConceptStatus, ConceptTermType
from doc2dic.services.glossary_service import (
    CreateConceptInput,
    CreateRelationInput,
    UpdateConceptInput,
)

app = typer.Typer(help="Manage glossary concepts.")
relation_app = typer.Typer(help="Manage concept relations.")
app.add_typer(relation_app, name="relation")


@app.callback()
def concept() -> None:
    """Show concept command group help."""


@app.command("list")
def list_concepts(
    status: Annotated[
        ConceptStatus | None,
        typer.Option("--status", help="Filter by concept status."),
    ] = None,
    tag: Annotated[
        str | None,
        typer.Option("--tag", help="Filter by tag label."),
    ] = None,
) -> None:
    """List stored concepts."""
    with glossary_service() as service:
        concepts = service.list_concepts(status=status, tag=tag)
    for item in concepts:
        typer.echo(f"{item.id}\t{item.status.value}\t{item.primary_term}")


@app.command("show")
def show_concept(
    concept_id: Annotated[str, typer.Argument(help="Concept id.")],
) -> None:
    """Show one concept."""
    with glossary_service() as service:
        concept_item = service.get_concept(concept_id)
    typer.echo(f"ID: {concept_item.id}")
    typer.echo(f"Primary term: {concept_item.primary_term}")
    typer.echo(f"Definition: {concept_item.definition}")
    typer.echo(f"Type: {concept_item.term_type.value}")
    typer.echo(f"Status: {concept_item.status.value}")
    typer.echo(f"Tags: {', '.join(concept_item.tags)}")


@app.command("add")
def add_concept(
    primary_term: Annotated[str, typer.Argument(help="Preferred concept label.")],
    definition: Annotated[str, typer.Option("--definition", "-d")],
    term_type: Annotated[
        ConceptTermType,
        typer.Option("--type", help="Concept term type."),
    ] = ConceptTermType.UNKNOWN,
    tag: Annotated[
        list[str] | None,
        typer.Option("--tag", help="Tag label; repeatable."),
    ] = None,
) -> None:
    """Add a concept and its primary variant."""
    with glossary_service() as service:
        concept_item = service.create_concept(
            CreateConceptInput(
                primary_term=primary_term,
                definition=definition,
                term_type=term_type,
                tags=tuple(tag or ()),
            ),
        )
    typer.echo(f"Created concept: {concept_item.id}")


@app.command("edit")
def edit_concept(
    concept_id: Annotated[str, typer.Argument(help="Concept id.")],
    primary_term: Annotated[str | None, typer.Option("--primary-term")] = None,
    definition: Annotated[str | None, typer.Option("--definition", "-d")] = None,
    term_type: Annotated[ConceptTermType | None, typer.Option("--type")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag")] = None,
) -> None:
    """Edit concept fields."""
    with glossary_service() as service:
        concept_item = service.update_concept(
            concept_id,
            UpdateConceptInput(
                primary_term=primary_term,
                definition=definition,
                term_type=term_type,
                tags=None if tag is None else tuple(tag),
            ),
        )
    typer.echo(f"Updated concept: {concept_item.id}")


@app.command("deprecate")
def deprecate_concept(
    concept_id: Annotated[str, typer.Argument(help="Concept id.")],
) -> None:
    """Mark a concept deprecated."""
    with glossary_service() as service:
        concept_item = service.deprecate_concept(concept_id)
    typer.echo(f"Deprecated concept: {concept_item.id}")


@relation_app.command("add")
def add_relation(
    source_concept_id: Annotated[str, typer.Argument(help="Source concept id.")],
    target_concept_id: Annotated[str, typer.Argument(help="Target concept id.")],
    relation_type: Annotated[
        str,
        typer.Option("--type", help="Relation type, such as related_to."),
    ] = "related_to",
    confidence: Annotated[float, typer.Option("--confidence")] = 1.0,
) -> None:
    """Add a relation between two concepts."""
    with glossary_service() as service:
        relation = service.add_relation(
            CreateRelationInput(
                source_concept_id=source_concept_id,
                target_concept_id=target_concept_id,
                relation_type=relation_type,
                confidence=confidence,
            ),
        )
    typer.echo(f"Created relation: {relation.id}")
