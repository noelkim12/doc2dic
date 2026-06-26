from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import pytest

from doc2dic.domain import ConceptStatus, ConceptTermType, TermVariantType
from doc2dic.services.glossary_service import (
    CreateConceptInput,
    CreateRelationInput,
    CreateVariantInput,
    DuplicateGlossaryItemError,
    GlossaryService,
    InvalidRelationTargetError,
    UpdateConceptInput,
)
from doc2dic.storage import open_database
from doc2dic.storage.migrations import migrate_database
from doc2dic.storage.sqlite_rows import int_cell, require_row

if TYPE_CHECKING:
    import sqlite3


def test_create_concept_when_valid_persists_primary_variant_and_tags(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        concept = service.create_concept(
            CreateConceptInput(
                primary_term="Stamina",
                definition="Resource spent to enter dungeons.",
                term_type=ConceptTermType.RESOURCE,
                tags=("Combat", "resource", "combat"),
            ),
        )
        variants = service.list_variants(concept.id)
        tags = service.list_tags()

    assert concept.id == "concept_stamina"
    assert concept.tags == ("combat", "resource")
    assert variants[0].normalized_label == "stamina"
    assert variants[0].variant_type.value == "primary"
    assert tuple(tag.label for tag in tags) == ("combat", "resource")


def test_list_concepts_when_filtered_by_tag_and_status_returns_matches(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        active = service.create_concept(
            CreateConceptInput(
                "Combo",
                "Chained actions.",
                ConceptTermType.ACTION,
                ("combat",),
            ),
        )
        deprecated = service.create_concept(
            CreateConceptInput(
                "Mana",
                "Old resource.",
                ConceptTermType.RESOURCE,
                ("combat",),
            ),
        )
        _ = service.deprecate_concept(deprecated.id)

        active_items = service.list_concepts(status=ConceptStatus.ACTIVE, tag="combat")

    assert tuple(item.id for item in active_items) == (active.id,)


def test_show_edit_deprecate_when_called_updates_concept(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        concept = service.create_concept(
            CreateConceptInput("Dash", "Move quickly.", ConceptTermType.ACTION),
        )
        edited = service.update_concept(
            concept.id,
            UpdateConceptInput(definition="Short movement burst.", tags=("movement",)),
        )
        deprecated = service.deprecate_concept(concept.id)

    assert edited.definition == "Short movement burst."
    assert edited.tags == ("movement",)
    assert deprecated.status is ConceptStatus.DEPRECATED


def test_add_variant_when_alias_is_unique_attaches_to_concept(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        concept = service.create_concept(
            CreateConceptInput("Health", "Hit points.", ConceptTermType.STAT),
        )
        variant = service.add_variant(
            CreateVariantInput(concept.id, "HP", TermVariantType.ABBREVIATION),
        )
        refreshed = service.get_concept(concept.id)

    assert variant.id == "variant_hp"
    assert refreshed.variant_ids == ("variant_health", "variant_hp")


def test_add_variant_when_primary_duplicate_rolls_back(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        concept = service.create_concept(
            CreateConceptInput("Energy", "Action resource.", ConceptTermType.RESOURCE),
        )

        with pytest.raises(DuplicateGlossaryItemError):
            _ = service.add_variant(
                CreateVariantInput(
                    concept.id,
                    "Energy Points",
                    TermVariantType.PRIMARY,
                ),
            )

        assert _count(connection, "term_variants") == 1
        assert service.get_concept(concept.id).variant_ids == ("variant_energy",)


def test_add_relation_when_target_exists_persists_relation(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        source = service.create_concept(
            CreateConceptInput("Sword", "Weapon item.", ConceptTermType.ENTITY),
        )
        target = service.create_concept(
            CreateConceptInput("Damage", "Health reduction.", ConceptTermType.STAT),
        )
        relation = service.add_relation(
            CreateRelationInput(source.id, target.id, "related_to", 0.8),
        )

        assert relation.source_concept_id == source.id
        assert relation.target_concept_id == target.id
        assert _count(connection, "concept_relations") == 1


def test_add_relation_when_target_invalid_rolls_back(tmp_path: Path) -> None:
    db_path = tmp_path / "glossary.sqlite3"
    _ = migrate_database(db_path)

    with open_database(db_path) as connection:
        service = GlossaryService(connection)
        source = service.create_concept(
            CreateConceptInput("Shield", "Defensive item.", ConceptTermType.ENTITY),
        )

        with pytest.raises(InvalidRelationTargetError):
            _ = service.add_relation(
                CreateRelationInput(source.id, "concept_missing", "related_to"),
            )

        assert _count(connection, "concept_relations") == 0


def _count(
    connection: "sqlite3.Connection",
    table_name: Literal["term_variants", "concept_relations"],
) -> int:
    match table_name:
        case "term_variants":
            sql = "select count(*) as count from term_variants"
        case "concept_relations":
            sql = "select count(*) as count from concept_relations"
    row = cast(
        "sqlite3.Row | None",
        connection.execute(sql).fetchone(),
    )
    return int_cell(require_row(row), "count")
