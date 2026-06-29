# MCP Concept Mutation Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an agent create / update / delete glossary concepts through the doc2dic MCP server and succeed on the first call.

**Architecture:** Three new MCP tools live in `src/doc2dic/mcp/` and reuse `GlossaryService` so validation is identical to the API/CLI. Constraints are exposed in the tool input schemas and server instructions; every failure returns agent-actionable guidance text instead of an exception. A companion change adds `physical_name` to the `explore` read surface so the agent can see existing physical names before mutating.

**Tech Stack:** Python 3.12+, pydantic v2, FastMCP (`mcp.server.fastmcp`), SQLite, pytest, ruff, basedpyright.

## Global Constraints

- Reuse `GlossaryService` for all mutations — do NOT add a second validation path.
- `physical_name` constraint copied verbatim from the API: pattern `^[A-Za-z_][A-Za-z0-9_]*$`, `max_length=80`.
- `primary_term`: 1–160 chars. `definition`: 1–2000 chars.
- MCP input field names are snake_case (matches existing MCP schemas), NOT the API's camelCase aliases.
- Mutation tools are `enabled_by_default=True` (default-on; no env opt-in).
- Mutation handlers use a plain `GlossaryService(connection)` with **no** embedding indexer — this avoids depending on an embedding provider in the mutation path (resolves the spec's embedding verify point). New concepts are searchable after the next index rebuild, same as the existing patch/delete routes.
- `physical_name` cannot be unset (empty string is rejected by the pattern) — keep this existing convention; do not add a sentinel.
- Every failure returns guidance text (a normal `str`), never raises out of the tool handler.
- All tool handlers return `str`.

---

### Task 1: Surface `physical_name` in the `explore` read output

**Files:**
- Modify: `src/doc2dic/context/cards.py:39-48` (ConceptCard)
- Modify: `src/doc2dic/context/repository.py:64-80` (`_concept_card`)
- Modify: `src/doc2dic/context/markdown.py:73-94` (`concept_lines`)
- Test: `tests/context/test_explore_context_builder.py`

**Interfaces:**
- Produces: `ConceptCard.physical_name: str | None` (default `None`), rendered by `concept_lines` as a `Physical name:` bullet.

- [ ] **Step 1: Write the failing test**

Add to `tests/context/test_explore_context_builder.py`:

```python
from doc2dic.context.cards import ConceptCard, VariantGroups
from doc2dic.context.markdown import concept_lines


def test_concept_lines_render_physical_name_when_present() -> None:
    card = ConceptCard(
        concept_id="concept_1",
        primary_term="체력",
        definition="플레이어 생존 수치",
        status="active",
        variants=VariantGroups((), (), (), ()),
        source_document=None,
        physical_name="hp",
    )

    lines = concept_lines([card])

    assert any("Physical name: hp" in line for line in lines)


def test_concept_lines_render_placeholder_when_physical_name_missing() -> None:
    card = ConceptCard(
        concept_id="concept_2",
        primary_term="공격력",
        definition="기본 피해량",
        status="active",
        variants=VariantGroups((), (), (), ()),
        source_document=None,
    )

    lines = concept_lines([card])

    assert any("Physical name: none stored" in line for line in lines)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/context/test_explore_context_builder.py -k physical_name -v`
Expected: FAIL — `ConceptCard` has no `physical_name` field / "Physical name" not rendered.

- [ ] **Step 3: Add the field to `ConceptCard`**

In `src/doc2dic/context/cards.py`, in the `ConceptCard` dataclass, add after `source_document`:

```python
    source_document: str | None = None
    physical_name: str | None = None
```

- [ ] **Step 4: Populate it in the repository read**

In `src/doc2dic/context/repository.py`, in `_concept_card`, add the field to the returned `ConceptCard`:

```python
    return ConceptCard(
        concept_id=concept_id,
        primary_term=text_cell(required, "primary_term"),
        definition=text_cell(required, "definition"),
        status=text_cell(required, "status"),
        variants=_variant_groups(connection, concept_id),
        source_document=optional_text_cell(required, "source_document"),
        physical_name=optional_text_cell(required, "physical_name"),
    )
```

- [ ] **Step 5: Render it in `concept_lines`**

In `src/doc2dic/context/markdown.py`, in `concept_lines`, add a bullet after the `Source document` line:

```python
        source = inline(concept.source_document) if concept.source_document else "none stored"
        physical = inline(concept.physical_name) if concept.physical_name else "none stored"
        lines.extend(
            [
                f"- {concept.primary_term} (`{concept.concept_id}`, {concept.status})",
                f"  - Definition: {concept.definition}",
                f"  - Source document: {source}",
                f"  - Physical name: {physical}",
                f"  - Primary variants: {bullet_values(concept.variants.primary)}",
                f"  - Alias variants: {bullet_values(concept.variants.alias)}",
                (
                    "  - Deprecated variants: "
                    f"{bullet_values(concept.variants.deprecated)}"
                ),
                f"  - Forbidden variants: {bullet_values(concept.variants.forbidden)}",
            ],
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/context/test_explore_context_builder.py -v`
Expected: PASS (new + existing context tests).

- [ ] **Step 7: Lint and type-check**

Run: `.venv/bin/ruff check src/doc2dic/context tests/context/test_explore_context_builder.py`
Run: `.venv/bin/basedpyright src/doc2dic/context`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/doc2dic/context tests/context/test_explore_context_builder.py
git commit -m "feat(mcp): surface concept physical_name in explore context"
```

---

### Task 2: Mutation input schemas

**Files:**
- Modify: `src/doc2dic/mcp/schemas.py`
- Test: `tests/mcp/test_mutation_schemas.py` (create)

**Interfaces:**
- Produces:
  - `CreateConceptToolInput(primary_term, definition, term_type=ConceptTermType.UNKNOWN, tags=(), physical_name=None, source_document=None, project_path=cwd)`
  - `UpdateConceptToolInput(concept_id, primary_term=None, definition=None, term_type=None, status=None, tags=None, physical_name=None, source_document=None, project_path=cwd)`
  - `DeleteConceptToolInput(concept_id, confirm=False, project_path=cwd)`

- [ ] **Step 1: Write the failing test**

Create `tests/mcp/test_mutation_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from doc2dic.domain import ConceptStatus, ConceptTermType
from doc2dic.mcp.schemas import (
    CreateConceptToolInput,
    DeleteConceptToolInput,
    UpdateConceptToolInput,
)


def test_create_schema_accepts_valid_physical_name() -> None:
    model = CreateConceptToolInput(
        primary_term="체력",
        definition="플레이어 생존 수치",
        physical_name="hp",
    )

    assert model.physical_name == "hp"
    assert model.term_type is ConceptTermType.UNKNOWN
    assert model.tags == ()


def test_create_schema_rejects_invalid_physical_name_pattern() -> None:
    with pytest.raises(ValidationError):
        CreateConceptToolInput(
            primary_term="체력",
            definition="생존 수치",
            physical_name="2hp",
        )


def test_create_schema_rejects_empty_definition() -> None:
    with pytest.raises(ValidationError):
        CreateConceptToolInput(primary_term="체력", definition="")


def test_update_schema_requires_concept_id() -> None:
    with pytest.raises(ValidationError):
        UpdateConceptToolInput()  # type: ignore[call-arg]


def test_update_schema_accepts_status_patch() -> None:
    model = UpdateConceptToolInput(
        concept_id="concept_1",
        status=ConceptStatus.DEPRECATED,
    )

    assert model.status is ConceptStatus.DEPRECATED
    assert model.primary_term is None


def test_delete_schema_defaults_confirm_false() -> None:
    model = DeleteConceptToolInput(concept_id="concept_1")

    assert model.confirm is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/mcp/test_mutation_schemas.py -v`
Expected: FAIL — `ImportError` for the three schema classes.

- [ ] **Step 3: Add the schemas**

In `src/doc2dic/mcp/schemas.py`, add the imports at the top and the three models at the end:

```python
from doc2dic.domain import ConceptStatus, ConceptTermType


class CreateConceptToolInput(BaseModel):
    """Validated input for `doc2dic_create_concept`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    primary_term: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=2000)
    term_type: ConceptTermType = ConceptTermType.UNKNOWN
    tags: tuple[str, ...] = ()
    physical_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=80,
    )
    source_document: str | None = None
    project_path: Path = Field(default_factory=Path.cwd)


class UpdateConceptToolInput(BaseModel):
    """Validated input for `doc2dic_update_concept`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    concept_id: str = Field(min_length=1)
    primary_term: str | None = Field(default=None, min_length=1, max_length=160)
    definition: str | None = Field(default=None, min_length=1, max_length=2000)
    term_type: ConceptTermType | None = None
    status: ConceptStatus | None = None
    tags: tuple[str, ...] | None = None
    physical_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=80,
    )
    source_document: str | None = None
    project_path: Path = Field(default_factory=Path.cwd)


class DeleteConceptToolInput(BaseModel):
    """Validated input for `doc2dic_delete_concept`."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    concept_id: str = Field(min_length=1)
    confirm: bool = False
    project_path: Path = Field(default_factory=Path.cwd)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/mcp/test_mutation_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and type-check**

Run: `.venv/bin/ruff check src/doc2dic/mcp/schemas.py tests/mcp/test_mutation_schemas.py`
Run: `.venv/bin/basedpyright src/doc2dic/mcp/schemas.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/doc2dic/mcp/schemas.py tests/mcp/test_mutation_schemas.py
git commit -m "feat(mcp): add concept mutation input schemas"
```

---

### Task 3: Mutation guidance helpers

**Files:**
- Modify: `src/doc2dic/mcp/guidance.py`
- Test: `tests/mcp/test_mutation_guidance.py` (create)

**Interfaces:**
- Produces (all return `str`):
  - `duplicate_concept_guidance(detail: str)`
  - `concept_not_found_guidance(concept_id: str)`
  - `invalid_mutation_input_guidance(detail: str)`
  - `delete_not_confirmed_guidance(concept_id: str)`

- [ ] **Step 1: Write the failing test**

Create `tests/mcp/test_mutation_guidance.py`:

```python
from doc2dic.mcp.guidance import (
    concept_not_found_guidance,
    delete_not_confirmed_guidance,
    duplicate_concept_guidance,
    invalid_mutation_input_guidance,
)


def test_duplicate_guidance_includes_detail_and_remedy() -> None:
    text = duplicate_concept_guidance("physical name 'hp' already exists")

    assert "# doc2dic MCP guidance" in text
    assert "physical name 'hp' already exists" in text
    assert "explore" in text


def test_not_found_guidance_names_the_id() -> None:
    text = concept_not_found_guidance("concept_404")

    assert "concept_404" in text
    assert "not found" in text


def test_invalid_input_guidance_includes_detail() -> None:
    text = invalid_mutation_input_guidance("physical_name pattern mismatch")

    assert "physical_name pattern mismatch" in text


def test_delete_not_confirmed_guidance_explains_confirm() -> None:
    text = delete_not_confirmed_guidance("concept_1")

    assert "concept_1" in text
    assert "confirm" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/mcp/test_mutation_guidance.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Add the guidance helpers**

Append to `src/doc2dic/mcp/guidance.py`:

```python
def duplicate_concept_guidance(detail: str) -> str:
    """Return guidance for a duplicate term or physical name conflict."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"The mutation was rejected as a duplicate: {detail}.",
            "",
            "## What to do",
            "- Run `doc2dic_explore` to find the existing concept.",
            "- Pick a different term/physical name, or update the existing concept.",
        ),
    )


def concept_not_found_guidance(concept_id: str) -> str:
    """Return guidance for a missing concept id on update/delete."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"Concept `{concept_id}` was not found.",
            "",
            "## What to do",
            "- Run `doc2dic_explore` to confirm the concept id.",
        ),
    )


def invalid_mutation_input_guidance(detail: str) -> str:
    """Return guidance for input that failed schema validation."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"The request was rejected as invalid input: {detail}.",
            "",
            "## What to do",
            "- physical_name must match `^[A-Za-z_][A-Za-z0-9_]*$` (max 80).",
            "- primary_term: 1-160 chars; definition: 1-2000 chars.",
        ),
    )


def delete_not_confirmed_guidance(concept_id: str) -> str:
    """Return guidance when a delete is requested without confirmation."""
    return "\n".join(
        (
            "# doc2dic MCP guidance",
            "",
            f"Delete of `{concept_id}` was not performed.",
            "",
            "## What to do",
            "- This is a permanent cascade delete of variants, tags, and relations.",
            "- Re-call with `confirm=true` to proceed.",
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/mcp/test_mutation_guidance.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and type-check**

Run: `.venv/bin/ruff check src/doc2dic/mcp/guidance.py tests/mcp/test_mutation_guidance.py`
Run: `.venv/bin/basedpyright src/doc2dic/mcp/guidance.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/doc2dic/mcp/guidance.py tests/mcp/test_mutation_guidance.py
git commit -m "feat(mcp): add concept mutation guidance helpers"
```

---

### Task 4: Mutation tool handlers

**Files:**
- Modify: `src/doc2dic/mcp/tools.py`
- Test: `tests/mcp/test_mutation_tools.py` (create)

**Interfaces:**
- Consumes: schemas from Task 2, guidance from Task 3, `GlossaryService`, `CreateConceptInput`, `UpdateConceptInput`, `DuplicateGlossaryItemError`, `GlossaryItemNotFoundError`, `_project_paths`/`missing_project_guidance`/`degraded_index_guidance` (already in `tools.py`/`guidance.py`).
- Produces (all return `str`):
  - `run_doc2dic_create_concept(primary_term, definition, term_type="unknown", tags=None, physical_name=None, source_document=None, project_path=None)`
  - `run_doc2dic_update_concept(concept_id, primary_term=None, definition=None, term_type=None, status=None, tags=None, physical_name=None, source_document=None, project_path=None)`
  - `run_doc2dic_delete_concept(concept_id, confirm=False, project_path=None)`

- [ ] **Step 1: Write the failing test**

Create `tests/mcp/test_mutation_tools.py`:

```python
from pathlib import Path

from doc2dic.mcp.tools import (
    run_doc2dic_create_concept,
    run_doc2dic_delete_concept,
    run_doc2dic_update_concept,
)
from doc2dic.storage.migrations import migrate_database


def _init_project(tmp_path: Path) -> str:
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    return str(tmp_path)


def test_create_concept_succeeds_and_reports_id(tmp_path: Path) -> None:
    project = _init_project(tmp_path)

    response = run_doc2dic_create_concept(
        primary_term="체력",
        definition="플레이어 생존 수치",
        physical_name="hp",
        project_path=project,
    )

    assert "# doc2dic concept created" in response
    assert "concept_" in response
    assert "hp" in response


def test_create_concept_duplicate_physical_name_returns_guidance(
    tmp_path: Path,
) -> None:
    project = _init_project(tmp_path)
    _ = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        physical_name="hp",
        project_path=project,
    )

    response = run_doc2dic_create_concept(
        primary_term="생명력",
        definition="다른 정의",
        physical_name="HP",
        project_path=project,
    )

    assert "# doc2dic MCP guidance" in response
    assert "duplicate" in response


def test_create_concept_invalid_physical_name_returns_guidance(
    tmp_path: Path,
) -> None:
    project = _init_project(tmp_path)

    response = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        physical_name="2hp",
        project_path=project,
    )

    assert "invalid input" in response


def test_create_concept_missing_project_returns_guidance(tmp_path: Path) -> None:
    response = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        project_path=str(tmp_path),
    )

    assert "not initialized" in response


def test_update_concept_changes_definition(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    created = run_doc2dic_create_concept(
        primary_term="체력",
        definition="옛 정의",
        project_path=project,
    )
    concept_id = _extract_concept_id(created)

    response = run_doc2dic_update_concept(
        concept_id=concept_id,
        definition="새 정의",
        project_path=project,
    )

    assert "# doc2dic concept updated" in response
    assert concept_id in response


def test_update_concept_not_found_returns_guidance(tmp_path: Path) -> None:
    project = _init_project(tmp_path)

    response = run_doc2dic_update_concept(
        concept_id="concept_missing",
        definition="x",
        project_path=project,
    )

    assert "not found" in response
    assert "concept_missing" in response


def test_delete_concept_requires_confirm(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    created = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        project_path=project,
    )
    concept_id = _extract_concept_id(created)

    response = run_doc2dic_delete_concept(
        concept_id=concept_id,
        confirm=False,
        project_path=project,
    )

    assert "not performed" in response
    assert "confirm" in response


def test_delete_concept_with_confirm_succeeds(tmp_path: Path) -> None:
    project = _init_project(tmp_path)
    created = run_doc2dic_create_concept(
        primary_term="체력",
        definition="생존 수치",
        project_path=project,
    )
    concept_id = _extract_concept_id(created)

    response = run_doc2dic_delete_concept(
        concept_id=concept_id,
        confirm=True,
        project_path=project,
    )

    assert "# doc2dic concept deleted" in response
    assert concept_id in response


def _extract_concept_id(text: str) -> str:
    for token in text.replace("`", " ").split():
        if token.startswith("concept_"):
            return token
    raise AssertionError(f"no concept id in: {text}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/mcp/test_mutation_tools.py -v`
Expected: FAIL — `ImportError` for the three handlers.

- [ ] **Step 3: Add the handlers**

In `src/doc2dic/mcp/tools.py`, extend the imports:

```python
from doc2dic.mcp.guidance import (
    concept_not_found_guidance,
    degraded_index_guidance,
    delete_not_confirmed_guidance,
    duplicate_concept_guidance,
    invalid_mutation_input_guidance,
    invalid_project_guidance,
    missing_project_guidance,
    status_guidance,
)
from doc2dic.mcp.schemas import (
    AnalyzeToolInput,
    CreateConceptToolInput,
    DeleteConceptToolInput,
    ExploreToolInput,
    StatusToolInput,
    SuggestTagsToolInput,
    UpdateConceptToolInput,
)
from doc2dic.services.glossary_models import (
    CreateConceptInput,
    DuplicateGlossaryItemError,
    GlossaryItemNotFoundError,
    UpdateConceptInput,
)
from doc2dic.services.glossary_service import GlossaryService
```

Then add the three handlers (after `run_doc2dic_suggest_tags`):

```python
def run_doc2dic_create_concept(
    primary_term: str,
    definition: str,
    term_type: str = "unknown",
    tags: tuple[str, ...] | None = None,
    physical_name: str | None = None,
    source_document: str | None = None,
    project_path: str | Path | None = None,
) -> str:
    """Create a glossary concept and return a success summary or guidance."""
    try:
        parsed = CreateConceptToolInput(
            primary_term=primary_term,
            definition=definition,
            term_type=term_type,  # type: ignore[arg-type]
            tags=tags or (),
            physical_name=physical_name,
            source_document=source_document,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
    except ValidationError as error:
        return invalid_mutation_input_guidance(str(error))
    try:
        paths = _project_paths(parsed.project_path)
    except (OSError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            concept = GlossaryService(connection).create_concept(
                CreateConceptInput(
                    primary_term=parsed.primary_term,
                    definition=parsed.definition,
                    term_type=parsed.term_type,
                    tags=parsed.tags,
                    source_document=parsed.source_document,
                    physical_name=parsed.physical_name,
                ),
            )
    except DuplicateGlossaryItemError as error:
        return duplicate_concept_guidance(str(error))
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(
        (
            "# doc2dic concept created",
            "",
            f"- Concept: `{concept.id}`",
            f"- Primary term: {concept.primary_term}",
            f"- Physical name: {concept.physical_name or 'none'}",
            f"- Status: {concept.status.value}",
        ),
    )


def run_doc2dic_update_concept(
    concept_id: str,
    primary_term: str | None = None,
    definition: str | None = None,
    term_type: str | None = None,
    status: str | None = None,
    tags: tuple[str, ...] | None = None,
    physical_name: str | None = None,
    source_document: str | None = None,
    project_path: str | Path | None = None,
) -> str:
    """Patch a glossary concept and return a success summary or guidance."""
    try:
        parsed = UpdateConceptToolInput(
            concept_id=concept_id,
            primary_term=primary_term,
            definition=definition,
            term_type=term_type,  # type: ignore[arg-type]
            status=status,  # type: ignore[arg-type]
            tags=tags,
            physical_name=physical_name,
            source_document=source_document,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
    except ValidationError as error:
        return invalid_mutation_input_guidance(str(error))
    try:
        paths = _project_paths(parsed.project_path)
    except (OSError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            concept = GlossaryService(connection).update_concept(
                parsed.concept_id,
                UpdateConceptInput(
                    primary_term=parsed.primary_term,
                    definition=parsed.definition,
                    term_type=parsed.term_type,
                    status=parsed.status,
                    tags=parsed.tags,
                    source_document=parsed.source_document,
                    physical_name=parsed.physical_name,
                ),
            )
    except GlossaryItemNotFoundError:
        return concept_not_found_guidance(parsed.concept_id)
    except DuplicateGlossaryItemError as error:
        return duplicate_concept_guidance(str(error))
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(
        (
            "# doc2dic concept updated",
            "",
            f"- Concept: `{concept.id}`",
            f"- Primary term: {concept.primary_term}",
            f"- Physical name: {concept.physical_name or 'none'}",
            f"- Status: {concept.status.value}",
        ),
    )


def run_doc2dic_delete_concept(
    concept_id: str,
    confirm: bool = False,
    project_path: str | Path | None = None,
) -> str:
    """Delete a glossary concept after confirmation, or return guidance."""
    try:
        parsed = DeleteConceptToolInput(
            concept_id=concept_id,
            confirm=confirm,
            project_path=Path.cwd() if project_path is None else Path(project_path),
        )
    except ValidationError as error:
        return invalid_mutation_input_guidance(str(error))
    if not parsed.confirm:
        return delete_not_confirmed_guidance(parsed.concept_id)
    try:
        paths = _project_paths(parsed.project_path)
    except (OSError, ValueError):
        return invalid_project_guidance(str(project_path))

    if not paths.db_path.exists():
        return missing_project_guidance(paths.root)

    try:
        with open_database(paths.db_path) as connection:
            GlossaryService(connection).delete_concept(parsed.concept_id)
    except GlossaryItemNotFoundError:
        return concept_not_found_guidance(parsed.concept_id)
    except sqlite3.DatabaseError:
        return degraded_index_guidance(paths.root)

    return "\n".join(
        (
            "# doc2dic concept deleted",
            "",
            f"- Concept: `{parsed.concept_id}`",
            "- Cascade removed variants, tags, and relations.",
        ),
    )
```

Note: `ValidationError` is already imported at the top of `tools.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/mcp/test_mutation_tools.py -v`
Expected: PASS (all 9 tests).

- [ ] **Step 5: Lint and type-check**

Run: `.venv/bin/ruff check src/doc2dic/mcp/tools.py tests/mcp/test_mutation_tools.py`
Run: `.venv/bin/basedpyright src/doc2dic/mcp/tools.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/doc2dic/mcp/tools.py tests/mcp/test_mutation_tools.py
git commit -m "feat(mcp): add create/update/delete concept tool handlers"
```

---

### Task 5: Register, wire, and re-instruct (default-on)

**Files:**
- Modify: `src/doc2dic/mcp/registry.py`
- Modify: `src/doc2dic/mcp/server.py`
- Modify: `src/doc2dic/mcp/instructions.py`
- Test: `tests/mcp/test_doc2dic_explore.py` (update existing assertions)
- Test: `tests/mcp/test_mutation_server.py` (create — end-to-end call_tool)

**Interfaces:**
- Consumes: `run_doc2dic_create_concept` / `run_doc2dic_update_concept` / `run_doc2dic_delete_concept` from Task 4.
- Produces: tool names `doc2dic_create_concept`, `doc2dic_update_concept`, `doc2dic_delete_concept` registered and default-on; rewritten `SERVER_INSTRUCTIONS`.

- [ ] **Step 1: Write the failing end-to-end test**

Create `tests/mcp/test_mutation_server.py`:

```python
from pathlib import Path

import anyio

from doc2dic.mcp.registry import active_tool_names
from doc2dic.mcp.server import Doc2DicMcpServer, build_doc2dic_mcp_server
from doc2dic.storage.migrations import migrate_database


def test_mutation_tools_are_default_on() -> None:
    names = active_tool_names()

    assert "doc2dic_create_concept" in names
    assert "doc2dic_update_concept" in names
    assert "doc2dic_delete_concept" in names


def test_create_concept_tool_round_trips_through_server(tmp_path: Path) -> None:
    db_path = tmp_path / ".doc2dic" / "glossary.sqlite3"
    db_path.parent.mkdir()
    _ = migrate_database(db_path)
    server = build_doc2dic_mcp_server(tmp_path)

    response = anyio.run(
        _call_tool_text,
        server,
        "doc2dic_create_concept",
        {
            "primary_term": "체력",
            "definition": "플레이어 생존 수치",
            "physical_name": "hp",
            "project_path": str(tmp_path),
        },
    )

    assert "# doc2dic concept created" in response
    assert "hp" in response


async def _call_tool_text(
    server: Doc2DicMcpServer,
    tool_name: str,
    arguments: dict[str, object],
) -> str:
    content, structured = await server.call_tool(tool_name, arguments)
    assert content[0].text == structured["result"]
    return structured["result"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/mcp/test_mutation_server.py -v`
Expected: FAIL — tool names not in `active_tool_names()`, tool not registered.

- [ ] **Step 3: Register the tools**

In `src/doc2dic/mcp/registry.py`, add name constants after `STATUS_TOOL_NAME`:

```python
CREATE_CONCEPT_TOOL_NAME: Final = "doc2dic_create_concept"
UPDATE_CONCEPT_TOOL_NAME: Final = "doc2dic_update_concept"
DELETE_CONCEPT_TOOL_NAME: Final = "doc2dic_delete_concept"
```

In `TOOL_DEFINITIONS`, insert three entries after the `SUGGEST_TAGS_TOOL_NAME` entry and before `STATUS_TOOL_NAME`:

```python
    CREATE_CONCEPT_TOOL_NAME: ToolDefinition(
        name=CREATE_CONCEPT_TOOL_NAME,
        description="Create a glossary concept (direct write).",
        enabled_by_default=True,
    ),
    UPDATE_CONCEPT_TOOL_NAME: ToolDefinition(
        name=UPDATE_CONCEPT_TOOL_NAME,
        description="Update a glossary concept (direct write).",
        enabled_by_default=True,
    ),
    DELETE_CONCEPT_TOOL_NAME: ToolDefinition(
        name=DELETE_CONCEPT_TOOL_NAME,
        description="Delete a glossary concept and its cascade (direct write).",
        enabled_by_default=True,
    ),
```

In `TOOL_ALIASES`, add:

```python
    "create_concept": CREATE_CONCEPT_TOOL_NAME,
    CREATE_CONCEPT_TOOL_NAME: CREATE_CONCEPT_TOOL_NAME,
    "update_concept": UPDATE_CONCEPT_TOOL_NAME,
    UPDATE_CONCEPT_TOOL_NAME: UPDATE_CONCEPT_TOOL_NAME,
    "delete_concept": DELETE_CONCEPT_TOOL_NAME,
    DELETE_CONCEPT_TOOL_NAME: DELETE_CONCEPT_TOOL_NAME,
```

- [ ] **Step 4: Wire the handlers in the server**

In `src/doc2dic/mcp/server.py`, extend the registry import:

```python
from doc2dic.mcp.registry import (
    ANALYZE_TOOL_NAME,
    CREATE_CONCEPT_TOOL_NAME,
    DEFAULT_TOOL_NAME,
    DELETE_CONCEPT_TOOL_NAME,
    STATUS_TOOL_NAME,
    SUGGEST_TAGS_TOOL_NAME,
    UPDATE_CONCEPT_TOOL_NAME,
    active_tool_names,
)
from doc2dic.mcp.tools import (
    run_doc2dic_analyze,
    run_doc2dic_create_concept,
    run_doc2dic_delete_concept,
    run_doc2dic_explore,
    run_doc2dic_status,
    run_doc2dic_suggest_tags,
    run_doc2dic_update_concept,
)
```

Then add three registration blocks inside `_register_enabled_tools` (after the `SUGGEST_TAGS_TOOL_NAME` block):

```python
    if CREATE_CONCEPT_TOOL_NAME in enabled_names:

        @server.tool(
            name=CREATE_CONCEPT_TOOL_NAME,
            description="Create a glossary concept (direct write).",
        )
        def doc2dic_create_concept(
            primary_term: str,
            definition: str,
            term_type: str = "unknown",
            tags: list[str] | None = None,
            physical_name: str | None = None,
            source_document: str | None = None,
            project_path: str | None = None,
        ) -> str:
            return run_doc2dic_create_concept(
                primary_term,
                definition,
                term_type=term_type,
                tags=tuple(tags) if tags is not None else None,
                physical_name=physical_name,
                source_document=source_document,
                project_path=project_path or default_project_root,
            )

        _ = doc2dic_create_concept

    if UPDATE_CONCEPT_TOOL_NAME in enabled_names:

        @server.tool(
            name=UPDATE_CONCEPT_TOOL_NAME,
            description="Update a glossary concept (direct write).",
        )
        def doc2dic_update_concept(
            concept_id: str,
            primary_term: str | None = None,
            definition: str | None = None,
            term_type: str | None = None,
            status: str | None = None,
            tags: list[str] | None = None,
            physical_name: str | None = None,
            source_document: str | None = None,
            project_path: str | None = None,
        ) -> str:
            return run_doc2dic_update_concept(
                concept_id,
                primary_term=primary_term,
                definition=definition,
                term_type=term_type,
                status=status,
                tags=tuple(tags) if tags is not None else None,
                physical_name=physical_name,
                source_document=source_document,
                project_path=project_path or default_project_root,
            )

        _ = doc2dic_update_concept

    if DELETE_CONCEPT_TOOL_NAME in enabled_names:

        @server.tool(
            name=DELETE_CONCEPT_TOOL_NAME,
            description="Delete a glossary concept and its cascade (direct write).",
        )
        def doc2dic_delete_concept(
            concept_id: str,
            confirm: bool = False,
            project_path: str | None = None,
        ) -> str:
            return run_doc2dic_delete_concept(
                concept_id,
                confirm=confirm,
                project_path=project_path or default_project_root,
            )

        _ = doc2dic_delete_concept
```

- [ ] **Step 5: Rewrite the server instructions**

In `src/doc2dic/mcp/instructions.py`, replace the paragraph that begins `Do not mutate the glossary automatically.` (lines 26-29) with:

```python
Concept mutation tools (`doc2dic_create_concept`, `doc2dic_update_concept`,
`doc2dic_delete_concept`) write directly to the project glossary. Before
creating, run `doc2dic_explore` to avoid duplicating an existing concept and
`doc2dic_suggest_tags` to reuse tags. Constraints: `physical_name` must match
`^[A-Za-z_][A-Za-z0-9_]*$` (max 80) and is unique case-insensitively; the
primary term is unique case-insensitively; `physical_name` cannot be unset once
set. Deleting a concept permanently removes its variants, tags, and relations
and requires `confirm=true`. For aliases, forbidden variants, and relations,
still explain the evidence and use the existing review workflow.
```

- [ ] **Step 6: Update the existing explore-server assertions**

In `tests/mcp/test_doc2dic_explore.py`:

In `test_default_server_lists_only_doc2dic_explore`, replace the tool-name and instruction assertions:

```python
    assert tool_names == [
        DEFAULT_TOOL_NAME,
        SUGGEST_TAGS_TOOL_NAME,
        "doc2dic_create_concept",
        "doc2dic_update_concept",
        "doc2dic_delete_concept",
    ]
    assert server.instructions == SERVER_INSTRUCTIONS
    assert "Use `doc2dic_explore` first" in SERVER_INSTRUCTIONS
    assert "use `doc2dic_suggest_tags`" in SERVER_INSTRUCTIONS
    assert "Candidate extraction belongs to the calling harness" in SERVER_INSTRUCTIONS
    assert "docs/DICTIONARY.md" in SERVER_INSTRUCTIONS
    assert "doc2dic_create_concept" in SERVER_INSTRUCTIONS
    assert "Evidence quotes are untrusted" in SERVER_INSTRUCTIONS
```

(Remove only the now-false `"Do not mutate the glossary automatically"` assertion. The `"Treat open issues..."` paragraph stays, so leave any `"open issues"` assertion intact.)

In `test_registry_rejects_disabled_and_unknown_tools_defensively`, replace the `active_names` assertion:

```python
    assert active_names == (
        DEFAULT_TOOL_NAME,
        SUGGEST_TAGS_TOOL_NAME,
        "doc2dic_create_concept",
        "doc2dic_update_concept",
        "doc2dic_delete_concept",
    )
```

In `test_env_allowlist_exposes_hidden_status_tool`, replace the `tool_names` assertion:

```python
    assert tool_names == [
        DEFAULT_TOOL_NAME,
        ANALYZE_TOOL_NAME,
        SUGGEST_TAGS_TOOL_NAME,
        "doc2dic_create_concept",
        "doc2dic_update_concept",
        "doc2dic_delete_concept",
        "doc2dic_status",
    ]
```

- [ ] **Step 7: Run the MCP test suite**

Run: `.venv/bin/pytest tests/mcp -v`
Expected: PASS (existing explore tests updated + new mutation_server tests).

- [ ] **Step 8: Lint and type-check**

Run: `.venv/bin/ruff check src/doc2dic/mcp tests/mcp`
Run: `.venv/bin/basedpyright src/doc2dic/mcp`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add src/doc2dic/mcp/registry.py src/doc2dic/mcp/server.py src/doc2dic/mcp/instructions.py tests/mcp
git commit -m "feat(mcp): expose default-on concept mutation tools and re-instruct"
```

---

### Task 6: Full-suite verification and handoff

**Files:**
- Create: `handoff/mcp-concept-mutation.md`

- [ ] **Step 1: Run the full backend suite**

Run: `.venv/bin/pytest -q`
Expected: PASS (pre-existing unrelated failures, if any, unchanged from baseline — note them, do not fix in this plan).

- [ ] **Step 2: Full lint and type-check**

Run: `.venv/bin/ruff check src tests`
Run: `.venv/bin/basedpyright src/doc2dic/mcp src/doc2dic/context`
Expected: clean.

- [ ] **Step 3: Write the handoff note**

Create `handoff/mcp-concept-mutation.md` documenting: what shipped (3 default-on MCP mutation tools + physical_name in explore), the reversal of the `doc2dic-mcp-read-only` decision, the embedding-indexer-omitted decision, and the v1 scope boundaries (no variant/relation mutation, no physical_name unset).

- [ ] **Step 4: Commit**

```bash
git add handoff/mcp-concept-mutation.md
git commit -m "docs(handoff): MCP concept mutation tools"
```

- [ ] **Step 5: Update agent memory**

After merge, update the `doc2dic-mcp-read-only` memory file to record that MCP now has default-on concept mutation tools (the read-only invariant is intentionally retired).
