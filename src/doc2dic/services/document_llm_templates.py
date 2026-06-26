"""Deterministic mock LLM templates for sample document fixtures."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from doc2dic.services.document_context_cards import DocumentContextCard


class TermType(StrEnum):
    """Term classes accepted by the LLM candidate schema."""

    MECHANIC = "mechanic"
    RESOURCE = "resource"
    STATE = "state"
    ACTION = "action"
    STAT = "stat"
    ENTITY = "entity"
    RULE = "rule"
    UI_LABEL = "ui-label"
    LORE = "lore"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TermTemplate:
    """Deterministic fixture-backed mock candidate rule."""

    surface: str
    quote: str
    definition: str
    term_type: TermType
    tags: tuple[str, ...]


def templates_for_document(document: DocumentContextCard) -> tuple[TermTemplate, ...]:
    """Return fixture-aligned term templates for a bounded document card."""
    path = document.path
    excerpt = document.excerpt
    if path.endswith("combat_core.md"):
        return _matching_templates(excerpt, COMBAT_TEMPLATES)
    if path.endswith("dungeon_draft.md"):
        return _matching_templates(excerpt, DUNGEON_TEMPLATES)
    if path.endswith("ui_terms.md"):
        return _matching_templates(excerpt, UI_TEMPLATES)
    return _generic_templates(excerpt)


def _matching_templates(
    text: str,
    templates: tuple[TermTemplate, ...],
) -> tuple[TermTemplate, ...]:
    return tuple(template for template in templates if template.surface in text)


def _generic_templates(text: str) -> tuple[TermTemplate, ...]:
    return tuple(
        template for template in ALL_MOCK_TEMPLATES if template.surface in text
    )


COMBAT_TEMPLATES: Final = (
    TermTemplate(
        surface="스태미나",
        quote="스태미나는 회피와 강공격에 소모되는 전투 자원이다.",
        definition="회피와 강공격에 소모되는 전투 자원",
        term_type=TermType.RESOURCE,
        tags=("combat_resource", "combat"),
    ),
    TermTemplate(
        surface="경직",
        quote="경직은 피격 직후 짧은 시간 동안 이동과 공격 입력이 제한되는 상태이다.",
        definition="피격 직후 이동과 공격 입력이 제한되는 상태",
        term_type=TermType.STATE,
        tags=("combat_status",),
    ),
    TermTemplate(
        surface="스턴",
        quote=(
            "스턴은 강한 충격이 누적되면 발생하며, "
            "2초 동안 모든 행동이 불가능한 상태이다."
        ),
        definition="강한 충격 누적으로 모든 행동이 불가능한 상태",
        term_type=TermType.STATE,
        tags=("combat_status",),
    ),
)
DUNGEON_TEMPLATES: Final = (
    TermTemplate(
        surface="스태미나",
        quote="스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.",
        definition="던전 입장 시 소모되고 매일 회복되는 입장 자원",
        term_type=TermType.RESOURCE,
        tags=("entry_resource",),
    ),
    TermTemplate(
        surface="입장 피로도",
        quote="입장 피로도가 부족하면 던전에 들어갈 수 없다.",
        definition="던전 입장 가능 여부를 결정하는 입장 자원",
        term_type=TermType.RESOURCE,
        tags=("entry_resource",),
    ),
    TermTemplate(
        surface="입장권",
        quote=(
            "입장권은 이벤트 던전에만 사용되며, "
            "일반 던전의 입장 피로도를 대체하지 않는다."
        ),
        definition="이벤트 던전 입장에 사용하는 인벤토리 아이템",
        term_type=TermType.ENTITY,
        tags=("inventory_item",),
    ),
)
UI_TEMPLATES: Final = (
    TermTemplate(
        surface="스태미나",
        quote="전투 HUD의 녹색 막대 라벨은 스태미나로 표기한다.",
        definition="전투 HUD 녹색 막대에 표시되는 UI 라벨",
        term_type=TermType.UI_LABEL,
        tags=("ui_label",),
    ),
    TermTemplate(
        surface="입장 피로도",
        quote="던전 로비의 입장 자원 라벨은 입장 피로도로 표기한다.",
        definition="던전 로비 입장 자원에 표시되는 UI 라벨",
        term_type=TermType.UI_LABEL,
        tags=("ui_label",),
    ),
)
ALL_MOCK_TEMPLATES: Final = COMBAT_TEMPLATES + DUNGEON_TEMPLATES + UI_TEMPLATES


__all__ = [
    "TermTemplate",
    "TermType",
    "templates_for_document",
]
