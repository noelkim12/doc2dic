# Concept Physical Name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a canonical code identifier (`physical_name`, e.g. `hp`) to each glossary concept so the dictionary maps a logical term (논리명, e.g. `체력`) to the one approved variable name used in code.

**Architecture:** `physical_name` is a first-class, optional, case-insensitively-unique column on `concepts` — NOT a `term_variants` row — because a naming standard needs exactly one authoritative answer per concept and fast `identifier → concept` reverse lookup with a uniqueness guarantee. The change threads one nullable string end-to-end through the existing layers (migration → domain → both persistence write/read paths → service → API + contract → CLI). No new check surface is introduced here.

**Tech Stack:** Python 3.12, SQLite (raw SQL + idempotent versioned migrations), pydantic v2 domain models, FastAPI local API, Typer CLI, pytest, uv.

## Global Constraints

- Migrations are checksum-verified and immutable once applied (`migrations.py:152-170`). NEVER edit `schema.sql` or any existing `*_schema.sql`; add a NEW migration file and bump `LATEST_SCHEMA_VERSION`. (current latest = 4)
- `physical_name` is **optional** (nullable). Concepts with no code form (lore, UI text) leave it `NULL`. Multiple `NULL`s must remain allowed.
- `physical_name` uniqueness is **case-insensitive** (`hp` conflicts with `HP`). Enforced by `collate nocase` on a partial unique index.
- `physical_name` format = a programming identifier: pattern `^[A-Za-z_][A-Za-z0-9_]*$`, `max_length=80`. Stored verbatim (no normalization of the stored value).
- Public concept contract (`contracts/schemas/concept.schema.json`) is `additionalProperties: false`; any new API field MUST be declared there as optional (NOT added to `required`).
- Two concept write paths exist and BOTH must be updated: `ConceptRepository.upsert_concept` (`storage/repositories/concepts.py`) and `upsert_concept_row` (`services/glossary_rows.py`). Two read mappers exist and BOTH must be updated: `ConceptRepository.get_concept` and `concept_from_row` (`services/glossary_row_mapping.py`).
- Run tests with `uv run pytest`. Lint with `uv run ruff check`.

---

## File Structure

- Create: `src/doc2dic/storage/concept_physical_name_schema.sql` — migration v5 SQL (add column + partial unique index).
- Modify: `src/doc2dic/storage/migrations.py` — register migration v5, bump `LATEST_SCHEMA_VERSION`.
- Modify: `src/doc2dic/domain/concept.py` — add `Concept.physical_name` field.
- Modify: `src/doc2dic/storage/repositories/concepts.py` — write + read `physical_name`.
- Modify: `src/doc2dic/services/glossary_row_mapping.py` — read `physical_name` in `concept_from_row`.
- Modify: `src/doc2dic/services/glossary_rows.py` — write `physical_name` (`upsert_concept_row`, `_concept_params`, `ConceptParams`); add `ensure_physical_name_available`.
- Modify: `src/doc2dic/services/glossary_models.py` — add `physical_name` to `CreateConceptInput` / `UpdateConceptInput`.
- Modify: `src/doc2dic/services/glossary_service.py` — set/patch `physical_name`; duplicate guard.
- Modify: `src/doc2dic/server/routes_concepts.py` — request bodies, payload, route wiring.
- Modify: `contracts/schemas/concept.schema.json` — declare optional `physicalName`.
- Modify: `src/doc2dic/commands/concept.py` — `--physical` option on `add`/`edit`, display in `show`.

Tests touched: `tests/integration/test_migrations.py`, `tests/unit/domain/test_concept_physical_name.py` (new), `tests/unit/storage/test_repositories.py`, `tests/unit/services/test_glossary_service.py`, `tests/integration/server/test_concepts_api.py`, `tests/integration/cli/test_concept_variant_relation.py`.

---

### Task 1: Migration v5 — add `physical_name` column + unique index

**Files:**
- Create: `src/doc2dic/storage/concept_physical_name_schema.sql`
- Modify: `src/doc2dic/storage/migrations.py:17` (LATEST_SCHEMA_VERSION), `:80-85` (MIGRATIONS)
- Test: `tests/integration/test_migrations.py`

**Interfaces:**
- Produces: `concepts.physical_name TEXT NULL`; partial unique index `idx_concepts_physical_name` on `physical_name collate nocase`; schema version 5.

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_migrations.py`:

```python
def test_migration_adds_physical_name_column(tmp_path):
    from doc2dic.storage.migrations import migrate_database

    result = migrate_database(tmp_path / "glossary.sqlite3")
    assert result.current_version == 5

    import sqlite3

    with sqlite3.connect(tmp_path / "glossary.sqlite3") as connection:
        cols = {row[1] for row in connection.execute("pragma table_info(concepts)")}
    assert "physical_name" in cols


def test_physical_name_unique_is_case_insensitive(tmp_path):
    import sqlite3

    from doc2dic.storage.migrations import migrate_database

    migrate_database(tmp_path / "glossary.sqlite3")
    with sqlite3.connect(tmp_path / "glossary.sqlite3") as connection:
        connection.execute(
            "insert into concepts(id, primary_term, definition, term_type, status, "
            "tags_json, variants_json, non_goals_json, examples_json, created_at, "
            "updated_at, physical_name) values "
            "('concept_a','체력','def','stat','active','[]','[]','[]','[]',"
            "'2026-06-29T00:00:00Z','2026-06-29T00:00:00Z','hp')",
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "insert into concepts(id, primary_term, definition, term_type, status, "
                "tags_json, variants_json, non_goals_json, examples_json, created_at, "
                "updated_at, physical_name) values "
                "('concept_b','생명','def','stat','active','[]','[]','[]','[]',"
                "'2026-06-29T00:00:00Z','2026-06-29T00:00:00Z','HP')",
            )
```

Ensure `import pytest` is present at the top of the test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_migrations.py::test_migration_adds_physical_name_column -v`
Expected: FAIL — `current_version == 4`, `physical_name` not in columns.

- [ ] **Step 3: Create the migration SQL**

Create `src/doc2dic/storage/concept_physical_name_schema.sql`:

```sql
alter table concepts add column physical_name text;
create unique index if not exists idx_concepts_physical_name
  on concepts(physical_name collate nocase)
  where physical_name is not null;
```

- [ ] **Step 4: Register the migration**

In `src/doc2dic/storage/migrations.py`, change line 17:

```python
LATEST_SCHEMA_VERSION: Final = 5
```

And extend the `MIGRATIONS` tuple (after the version-4 entry):

```python
MIGRATIONS: Final = (
    MigrationDefinition(1, "initial_storage_schema", "schema.sql"),
    MigrationDefinition(2, "search_schema", "search_schema.sql"),
    MigrationDefinition(3, "issue_search_schema", "issue_search_schema.sql"),
    MigrationDefinition(4, "concept_source_schema", "concept_source_schema.sql"),
    MigrationDefinition(5, "concept_physical_name_schema", "concept_physical_name_schema.sql"),
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_migrations.py -v`
Expected: PASS (both new tests + existing migration tests).

- [ ] **Step 6: Commit**

```bash
git add src/doc2dic/storage/concept_physical_name_schema.sql src/doc2dic/storage/migrations.py tests/integration/test_migrations.py
git commit -m "feat(storage): add concepts.physical_name column (migration v5)"
```

---

### Task 2: Domain — `Concept.physical_name` field

**Files:**
- Modify: `src/doc2dic/domain/concept.py:58-76` (Concept model)
- Test: `tests/unit/domain/test_concept_physical_name.py` (create)

**Interfaces:**
- Produces: `Concept.physical_name: str | None` (default `None`, pattern `^[A-Za-z_][A-Za-z0-9_]*$`, max_length 80). All later tasks read/write this attribute.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/test_concept_physical_name.py`:

```python
import pytest
from pydantic import ValidationError

from doc2dic.domain import Concept, ConceptStatus, ConceptTermType


def _concept(**overrides):
    base = {
        "id": "concept_hp",
        "primary_term": "체력",
        "definition": "캐릭터의 생명 수치",
        "term_type": ConceptTermType.STAT,
        "status": ConceptStatus.ACTIVE,
        "created_at": "2026-06-29T00:00:00Z",
        "updated_at": "2026-06-29T00:00:00Z",
    }
    base.update(overrides)
    return Concept(**base)


def test_physical_name_defaults_to_none():
    assert _concept().physical_name is None


def test_physical_name_accepts_identifier():
    assert _concept(physical_name="hp").physical_name == "hp"
    assert _concept(physical_name="max_hp").physical_name == "max_hp"


def test_physical_name_rejects_non_identifier():
    with pytest.raises(ValidationError):
        _concept(physical_name="체력")
    with pytest.raises(ValidationError):
        _concept(physical_name="max hp")
    with pytest.raises(ValidationError):
        _concept(physical_name="1hp")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/domain/test_concept_physical_name.py -v`
Expected: FAIL — `physical_name` is not a field (ValidationError on unexpected kwarg, or AttributeError).

- [ ] **Step 3: Add the field**

In `src/doc2dic/domain/concept.py`, inside the `Concept` model, add after the `source_document` field (line 76):

```python
    physical_name: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=80,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/domain/test_concept_physical_name.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/doc2dic/domain/concept.py tests/unit/domain/test_concept_physical_name.py
git commit -m "feat(domain): add Concept.physical_name field"
```

---

### Task 3: Persistence — write & read `physical_name` on both paths

**Files:**
- Modify: `src/doc2dic/storage/repositories/concepts.py:26-94` (`upsert_concept`, `get_concept`)
- Modify: `src/doc2dic/services/glossary_row_mapping.py:32-49` (`concept_from_row`)
- Modify: `src/doc2dic/services/glossary_rows.py:21-36` (`ConceptParams`), `:106-126` (`upsert_concept_row`), `:227-243` (`_concept_params`)
- Test: `tests/unit/storage/test_repositories.py`

**Interfaces:**
- Consumes: `Concept.physical_name` (Task 2).
- Produces: round-trip persistence of `physical_name` via both `ConceptRepository` and `upsert_concept_row` + `concept_from_row`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/storage/test_repositories.py` (reuse the module's existing connection/repository fixtures; if a migrated-connection fixture named `connection` is not present, build one with `migrate_database` + `sqlite3.connect(..., row_factory=sqlite3.Row)` mirroring the existing tests in this file):

```python
def test_concept_physical_name_round_trips(connection):
    from doc2dic.domain import Concept, ConceptStatus, ConceptTermType
    from doc2dic.storage.repositories.concepts import ConceptRepository

    repo = ConceptRepository(connection)
    concept = Concept(
        id="concept_hp",
        primary_term="체력",
        definition="캐릭터의 생명 수치",
        term_type=ConceptTermType.STAT,
        status=ConceptStatus.ACTIVE,
        created_at="2026-06-29T00:00:00Z",
        updated_at="2026-06-29T00:00:00Z",
        physical_name="hp",
    )
    repo.upsert_concept(concept)

    loaded = repo.get_concept("concept_hp")
    assert loaded is not None
    assert loaded.physical_name == "hp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/storage/test_repositories.py::test_concept_physical_name_round_trips -v`
Expected: FAIL — `loaded.physical_name is None` (column written but not read, or not written at all).

- [ ] **Step 3a: Update `ConceptRepository.upsert_concept`**

In `src/doc2dic/storage/repositories/concepts.py`, change the INSERT column list, value placeholders, conflict-update set, and params tuple to include `physical_name`:

- Column list: add `physical_name` after `source_document`.
- Placeholders: add one more `?` (now 15 columns).
- `on conflict ... do update set`: add `physical_name = excluded.physical_name,` (before `updated_at = excluded.updated_at`).
- Params tuple: add `concept.physical_name,` after `concept.source_document,`.

The resulting statement:

```python
                """
                insert into concepts(
                  id, primary_term, definition, term_type, status, tags_json,
                  variants_json, scope_note, non_goals_json, examples_json, owner,
                  source_document, physical_name, created_at, updated_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(id) do update set
                  primary_term = excluded.primary_term,
                  definition = excluded.definition,
                  term_type = excluded.term_type,
                  status = excluded.status,
                  tags_json = excluded.tags_json,
                  variants_json = excluded.variants_json,
                  scope_note = excluded.scope_note,
                  non_goals_json = excluded.non_goals_json,
                  examples_json = excluded.examples_json,
                  owner = excluded.owner,
                  source_document = excluded.source_document,
                  physical_name = excluded.physical_name,
                  updated_at = excluded.updated_at
                """,
                (
                    concept.id,
                    concept.primary_term,
                    concept.definition,
                    concept.term_type.value,
                    concept.status.value,
                    canonical_json(concept.tags),
                    canonical_json(concept.variant_ids),
                    concept.scope_note,
                    canonical_json(concept.non_goals),
                    canonical_json(concept.examples),
                    concept.owner,
                    concept.source_document,
                    concept.physical_name,
                    concept.created_at,
                    concept.updated_at,
                ),
```

- [ ] **Step 3b: Update `ConceptRepository.get_concept`**

In the same file, add to the `Concept(...)` construction in `get_concept` (after `source_document=...`):

```python
            physical_name=optional_text_cell(row, "physical_name"),
```

- [ ] **Step 3c: Update `concept_from_row`**

In `src/doc2dic/services/glossary_row_mapping.py`, add to the `Concept(...)` construction (after `source_document=...`, line 48):

```python
        physical_name=optional_text_cell(row, "physical_name"),
```

- [ ] **Step 3d: Update `glossary_rows.py` write path**

In `src/doc2dic/services/glossary_rows.py`:

Extend the `ConceptParams` type alias with one more `str | None` entry (15 total):

```python
type ConceptParams = tuple[
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str | None,
    str,
    str,
    str | None,
    str | None,
    str | None,
    str,
    str,
]
```

In `upsert_concept_row`, add `physical_name` to the column list (after `source_document`), add one `?`, and add `physical_name = excluded.physical_name,` to the conflict-update set:

```python
        """
        insert into concepts(
          id, primary_term, definition, term_type, status, tags_json,
          variants_json, scope_note, non_goals_json, examples_json, owner,
          source_document, physical_name, created_at, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(id) do update set
          primary_term = excluded.primary_term,
          definition = excluded.definition,
          term_type = excluded.term_type,
          status = excluded.status,
          tags_json = excluded.tags_json,
          variants_json = excluded.variants_json,
          source_document = excluded.source_document,
          physical_name = excluded.physical_name,
          updated_at = excluded.updated_at
        """,
```

In `_concept_params`, add `concept.physical_name,` after `concept.source_document,`:

```python
        concept.source_document,
        concept.physical_name,
        concept.created_at,
        concept.updated_at,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/storage/test_repositories.py -v`
Expected: PASS (new round-trip test + existing repository tests).

- [ ] **Step 5: Commit**

```bash
git add src/doc2dic/storage/repositories/concepts.py src/doc2dic/services/glossary_row_mapping.py src/doc2dic/services/glossary_rows.py tests/unit/storage/test_repositories.py
git commit -m "feat(storage): persist concept physical_name on both write/read paths"
```

---

### Task 4: Service — set/patch `physical_name` with duplicate guard

**Files:**
- Modify: `src/doc2dic/services/glossary_models.py:29-50` (`CreateConceptInput`, `UpdateConceptInput`)
- Modify: `src/doc2dic/services/glossary_rows.py` (add `ensure_physical_name_available`)
- Modify: `src/doc2dic/services/glossary_service.py:94-176` (`create_concept`, `update_concept`)
- Test: `tests/unit/services/test_glossary_service.py`

**Interfaces:**
- Consumes: `Concept.physical_name`, `upsert_concept_row`, `DuplicateGlossaryItemError`.
- Produces: `CreateConceptInput.physical_name: str | None = None`; `UpdateConceptInput.physical_name: str | None = None`; `ensure_physical_name_available(connection, physical_name, exclude_concept_id=None)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/services/test_glossary_service.py` (reuse this module's existing service fixture; if it is named differently, mirror the existing tests' setup):

```python
def test_create_concept_with_physical_name(glossary_service):
    from doc2dic.services.glossary_service import CreateConceptInput
    from doc2dic.domain import ConceptTermType

    concept = glossary_service.create_concept(
        CreateConceptInput(
            primary_term="체력",
            definition="생명 수치",
            term_type=ConceptTermType.STAT,
            physical_name="hp",
        ),
    )
    assert concept.physical_name == "hp"
    assert glossary_service.get_concept(concept.id).physical_name == "hp"


def test_duplicate_physical_name_rejected(glossary_service):
    from doc2dic.services.glossary_service import CreateConceptInput
    from doc2dic.services.glossary_models import DuplicateGlossaryItemError
    from doc2dic.domain import ConceptTermType

    glossary_service.create_concept(
        CreateConceptInput(
            primary_term="체력", definition="d", term_type=ConceptTermType.STAT,
            physical_name="hp",
        ),
    )
    with pytest.raises(DuplicateGlossaryItemError):
        glossary_service.create_concept(
            CreateConceptInput(
                primary_term="생명력", definition="d", term_type=ConceptTermType.STAT,
                physical_name="HP",
            ),
        )
```

Ensure `import pytest` is present.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/services/test_glossary_service.py::test_create_concept_with_physical_name -v`
Expected: FAIL — `CreateConceptInput` has no `physical_name` argument.

- [ ] **Step 3a: Add input fields**

In `src/doc2dic/services/glossary_models.py`, add to `CreateConceptInput` (after `source_document`):

```python
    physical_name: str | None = None
```

And to `UpdateConceptInput` (after `source_document`):

```python
    physical_name: str | None = None
```

- [ ] **Step 3b: Add the duplicate guard helper**

In `src/doc2dic/services/glossary_rows.py`, add after `ensure_label_available` (around line 80):

```python
def ensure_physical_name_available(
    connection: sqlite3.Connection,
    physical_name: str,
    exclude_concept_id: str | None = None,
) -> None:
    """Raise when another concept already claims this case-insensitive identifier."""
    row = cast(
        "sqlite3.Row | None",
        connection.execute(
            """
            select id from concepts
            where physical_name = ? collate nocase and id is not ?
            """,
            (physical_name, exclude_concept_id),
        ).fetchone(),
    )
    if row is not None:
        message = f"duplicate physical name: {physical_name}"
        raise DuplicateGlossaryItemError(message)
```

- [ ] **Step 3c: Wire into `create_concept`**

In `src/doc2dic/services/glossary_service.py`, import the helper by adding `ensure_physical_name_available` to the existing `from doc2dic.services.glossary_rows import (...)` block (lines 36-47).

In `create_concept`, compute the cleaned value and pass it to the `Concept(...)` constructor (add after `source_document=...`, line 110):

```python
            physical_name=_clean_optional(command.physical_name),
```

Inside the `with self._transaction():` block, before `upsert_concept_row(...)`, add the guard:

```python
            if concept.physical_name is not None:
                ensure_physical_name_available(self._connection, concept.physical_name)
```

- [ ] **Step 3d: Wire into `update_concept`**

In `update_concept`, compute the patched value mirroring `source_document` (after the `source_document = ...` block, line 158):

```python
        physical_name = (
            _clean_optional(command.physical_name)
            if command.physical_name is not None
            else current.physical_name
        )
```

Add `"physical_name": physical_name,` to the `model_copy(update={...})` dict (after `"source_document": source_document,`).

Inside the `with self._transaction():` block, before `upsert_concept_row(...)`, add the guard (skip when unchanged):

```python
            if (
                physical_name is not None
                and physical_name != current.physical_name
            ):
                ensure_physical_name_available(
                    self._connection, physical_name, exclude_concept_id=concept_id
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/services/test_glossary_service.py -v`
Expected: PASS (both new tests + existing service tests).

- [ ] **Step 5: Commit**

```bash
git add src/doc2dic/services/glossary_models.py src/doc2dic/services/glossary_rows.py src/doc2dic/services/glossary_service.py tests/unit/services/test_glossary_service.py
git commit -m "feat(glossary): set and guard concept physical_name in service"
```

---

### Task 5: API — request bodies, payload, contract

**Files:**
- Modify: `contracts/schemas/concept.schema.json`
- Modify: `src/doc2dic/server/routes_concepts.py:36-65` (bodies), `:81-95` (payload), `:129-146` + `:162-185` (routes), `:254-265` (`_concept_payload`)
- Test: `tests/integration/server/test_concepts_api.py`

**Interfaces:**
- Consumes: `CreateConceptInput.physical_name`, `UpdateConceptInput.physical_name`, `Concept.physical_name`.
- Produces: API accepts/returns `physicalName` (camelCase alias).

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/server/test_concepts_api.py` (reuse the module's existing test client fixture):

```python
def test_create_and_get_concept_with_physical_name(client):
    created = client.post(
        "/api/concepts",
        json={
            "primaryTerm": "체력",
            "definition": "생명 수치",
            "termType": "stat",
            "physicalName": "hp",
        },
    )
    assert created.status_code == 201
    assert created.json()["physicalName"] == "hp"

    concept_id = created.json()["id"]
    fetched = client.get(f"/api/concepts/{concept_id}")
    assert fetched.json()["physicalName"] == "hp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/server/test_concepts_api.py::test_create_and_get_concept_with_physical_name -v`
Expected: FAIL — `extra="forbid"` rejects `physicalName`, or response lacks the key.

- [ ] **Step 3a: Add `physicalName` to request bodies**

In `src/doc2dic/server/routes_concepts.py`, add to `ConceptCreateBody` (after `tags`):

```python
    physical_name: str | None = Field(
        default=None,
        alias="physicalName",
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
        max_length=80,
    )
```

Add the identical field to `ConceptPatchBody` (after `tags`).

- [ ] **Step 3b: Add `physicalName` to the payload**

In `ConceptPayload`, add (after `status`):

```python
    physical_name: str | None = Field(default=None, alias="physicalName")
```

In `_concept_payload`, pass it (after `status=...`):

```python
        physicalName=concept.physical_name,
```

- [ ] **Step 3c: Wire routes**

In `create_concept`, add to `CreateConceptInput(...)`:

```python
                physical_name=body.physical_name,
```

In `patch_concept`, add to `UpdateConceptInput(...)`:

```python
                physical_name=body.physical_name,
```

- [ ] **Step 3d: Update the contract**

In `contracts/schemas/concept.schema.json`, add to `properties` (after `"status"`, leave `required` unchanged):

```json
    "physicalName": { "type": ["string", "null"], "pattern": "^[A-Za-z_][A-Za-z0-9_]*$", "maxLength": 80 },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/server/test_concepts_api.py -v`
Expected: PASS (new test + existing API tests, including any contract-validation test).

- [ ] **Step 5: Commit**

```bash
git add contracts/schemas/concept.schema.json src/doc2dic/server/routes_concepts.py tests/integration/server/test_concepts_api.py
git commit -m "feat(api): accept and return concept physicalName"
```

---

### Task 6: CLI — `--physical` on add/edit, display in show

**Files:**
- Modify: `src/doc2dic/commands/concept.py:43-117` (`show_concept`, `add_concept`, `edit_concept`)
- Test: `tests/integration/cli/test_concept_variant_relation.py`

**Interfaces:**
- Consumes: `CreateConceptInput.physical_name`, `UpdateConceptInput.physical_name`, `Concept.physical_name`.
- Produces: CLI `concept add --physical hp`, `concept edit <id> --physical hp`, `concept show` prints physical name.

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/cli/test_concept_variant_relation.py` (reuse the module's existing Typer `CliRunner` + project fixtures):

```python
def test_concept_add_with_physical_name(runner, project_env):
    add = runner.invoke(
        app,
        ["add", "체력", "-d", "생명 수치", "--type", "stat", "--physical", "hp"],
    )
    assert add.exit_code == 0
    concept_id = add.stdout.strip().split()[-1]

    show = runner.invoke(app, ["show", concept_id])
    assert "hp" in show.stdout
```

Match `app`, `runner`, and `project_env` to whatever the existing tests in this file import/use (the concept Typer app is `doc2dic.commands.concept.app`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/cli/test_concept_variant_relation.py::test_concept_add_with_physical_name -v`
Expected: FAIL — `--physical` is not a known option.

- [ ] **Step 3a: Add `--physical` to `add_concept`**

In `src/doc2dic/commands/concept.py`, add a parameter to `add_concept` (after `source`):

```python
    physical: Annotated[
        str | None,
        typer.Option("--physical", help="Canonical code identifier (물리명), e.g. hp."),
    ] = None,
```

Pass it into `CreateConceptInput(...)`:

```python
                physical_name=physical,
```

- [ ] **Step 3b: Add `--physical` to `edit_concept`**

Add the same `physical` parameter to `edit_concept` (after `source`), and pass into `UpdateConceptInput(...)`:

```python
                physical_name=physical,
```

- [ ] **Step 3c: Display in `show_concept`**

In `show_concept`, add after the `Source:` echo (line 56):

```python
    typer.echo(f"Physical name: {concept_item.physical_name or '(none)'}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/cli/test_concept_variant_relation.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + lint**

Run: `uv run pytest && uv run ruff check`
Expected: PASS / no errors.

- [ ] **Step 6: Commit**

```bash
git add src/doc2dic/commands/concept.py tests/integration/cli/test_concept_variant_relation.py
git commit -m "feat(cli): manage concept physical_name via add/edit/show"
```

---

## Notes & deferred work (Plan 2)

- **Code-surface checking** (scan source files → tokenize identifiers → match against `physical_name` and forbidden code identifiers → raise `term_issues`) is a separate subsystem and a separate plan. It introduces new file-type handling and identifier tokenization.
- **Forbidden/legacy code identifiers** via a new `TermVariantType.PHYSICAL` value are deferred to Plan 2, where they gain a consumer (the code scanner). Adding the enum value now would be dead code (YAGNI).
- **Casing/composition generation** (`hp` → `maxHp`/`max_hp`, compounds like 최대 체력 → `max_hp`) is explicitly out of scope; `physical_name` stores one verbatim canonical string in v1.
- **Graphify export / search index**: `physical_name` is not surfaced to the graph projection or FTS in this plan. Add only if a consumer needs it.

## Self-Review

- **Spec coverage:** canonical singular physical name (Tasks 2-4, UNIQUE index Task 1), reverse-lookup uniqueness (Task 1 index + Task 4 guard), nullable for code-less concepts (Global Constraints + default None), end-to-end exposure (Tasks 5-6). ✓
- **Placeholder scan:** all code steps contain literal code; test fixtures reference existing-module conventions with explicit fallback instructions rather than invented names. ✓
- **Type consistency:** `physical_name: str | None` used uniformly; `ensure_physical_name_available(connection, physical_name, exclude_concept_id=None)` signature matches both call sites (create passes no exclude, update passes `exclude_concept_id=concept_id`); `ConceptParams` widened to 15 entries to match the 15-column insert. ✓
