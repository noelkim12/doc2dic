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
