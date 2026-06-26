# 기획 용어사전 기반 문서 일관성 검사기 구현 계획

작성일: 2026-06-25  
대상 독자: 개인/소규모 게임 기획·개발 프로젝트를 진행하는 개발자  
목표 실행 환경: `curl` 등 1회 설치 후 전역 CLI 사용, 프로젝트별 `.doc2dic/` SQLite 사전 DB + vector extension, 선택적 로컬 웹 UI, OpenCode subagent 병렬 개발 흐름

---

## 0. 결론 요약

본 프로젝트의 핵심은 단순한 용어사전이 아니라 **기획 문서의 개념 일관성 검사 시스템**이다. 시스템은 기획 문서에서 용어 후보를 추출하고, 기존 사전과 비교하여 다음 문제를 발견한다.

1. 같은 용어가 다른 의미로 쓰이는 문제
2. 같은 의미가 다른 용어로 표현되는 문제
3. 금지어, 폐기어, 비권장 표현이 문서에 다시 등장하는 문제
4. 완전히 새로운 용어를 사전에 등록해야 하는 문제
5. 문서와 사전 사이의 개념 관계가 누락되거나 어긋나는 문제

권장 아키텍처는 다음과 같다.

```text
기획 문서
  ↓
문서 파싱 / 청킹
  ↓
LLM 용어 후보 추출
  ↓
exact / fuzzy / embedding 검색
  ↓
LLM 충돌 분류
  ↓
사람 승인 기반 리뷰 큐
  ↓
프로젝트 로컬 사전 DB
  ↓
웹 그래프 시각화 + graphify 호환 그래프 export
```

가장 중요한 설계 원칙은 다음이다.

```text
프로젝트 로컬 SQLite 사전 DB = 기준이 되는 원본
전역 CLI = 모든 프로젝트에서 같은 명령으로 사전을 초기화/검사/리뷰하는 진입점
Graphify = 그래프화, 질의, 리포트, 보조 분석 레이어
Embedding = 프로젝트 로컬 유사 후보 검색기
LLM = 후보 추출 및 충돌 판정 보조자
사람 = 최종 승인자
```

Graphify는 직접 원본 데이터 모델을 확정하는 도구로 쓰기보다, **용어사전 데이터를 그래프로 투영하거나, 기존 문서에서 관찰 그래프를 만들어 리뷰 큐에 넣는 보조 도구**로 쓰는 것이 안전하다.

---

## 1. 배경과 문제 정의

게임 기획 문서에서는 같은 개념이 여러 표현으로 작성되거나, 같은 용어가 서로 다른 의미로 쓰이는 일이 자주 발생한다. 예를 들어 다음과 같은 상황이다.

```text
문서 A:
스태미나는 회피와 강공격에 소모되는 전투 자원이다.

문서 B:
스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.
```

두 문서 모두 “스태미나”라는 같은 표면 용어를 사용하지만, 첫 번째는 전투 자원이고 두 번째는 던전 입장 피로도에 가깝다. 이 경우 단순 문자열 검색으로는 문제를 발견할 수 없으며, 문맥상 의미를 비교해야 한다.

반대로 다음과 같은 문제도 있다.

```text
문서 A:
경직은 피격 직후 짧은 시간 동안 이동과 공격 입력이 제한되는 상태이다.

문서 B:
강공격에 맞으면 짧은 스턴 상태가 된다.
```

여기서는 “경직”과 “짧은 스턴”이 같은 의미로 쓰였을 가능성이 있으나, 게임 규칙상 “스턴”과 “경직”은 다른 상태일 수 있다. 따라서 자동 치환이 아니라 검토 후보로 올리는 흐름이 필요하다.

본 프로젝트는 이 문제를 해결하기 위해 **프로젝트 단위 Concept 중심 용어사전**, **전역 CLI**, **문서 분석 파이프라인**, **충돌 리뷰 큐**, **선택적 웹 기반 그래프 시각화**, **Graphify 연동**을 구현한다.

---

## 2. 핵심 목표와 비목표

### 2.1 목표

| 목표 | 설명 |
|---|---|
| Concept 중심 용어사전 | “용어”가 아니라 “개념”을 원본 단위로 관리한다. |
| 용어 후보 추출 | 근간 문서와 파생 문서에서 새 용어 후보를 추출한다. |
| 의미 충돌 탐지 | 같은 용어/다른 의미, 같은 의미/다른 용어 후보를 탐지한다. |
| 리뷰 큐 | LLM 판단을 곧바로 DB에 반영하지 않고 사람이 승인한다. |
| 태그 관리 | 각 개념과 용어에 n개의 태그를 부여한다. |
| LLM 친화성 | LLM이 사전을 참조하기 쉬운 카드형 JSON/Markdown 컨텍스트를 제공한다. |
| 프로젝트별 사전 관리 | 각 프로젝트 루트의 `.doc2dic/glossary.sqlite3`와 산출물 디렉터리에 독립적인 사전을 둔다. |
| 전역 CLI 사용성 | 한 번 설치한 `doc2dic` 명령으로 어떤 프로젝트에서도 `init`, `check`, `review`, `export`를 실행한다. |
| Embedding 검색 | Voyage, OpenAI 등 provider를 바꿀 수 있는 embedding 검색 레이어를 둔다. |
| Web 시각화 | CLI가 띄우는 로컬 웹 UI에서 용어, 문서, 이슈, 관계를 그래프로 보여준다. |
| Graphify 연동 | 용어사전 데이터를 graphify-compatible graph로 export하고, graphify 관찰 그래프를 import할 수 있게 한다. |
| OpenCode 병렬 개발 | subagent가 충돌 없이 병렬로 작업할 수 있도록 경계와 산출물을 나눈다. |

### 2.2 비목표

초기 MVP에서는 다음을 목표로 삼지 않는다.

| 비목표 | 이유 |
|---|---|
| 완전 자동 문서 수정 | 기획 용어는 의도적 예외가 많으므로 자동 수정은 위험하다. |
| PDF 중심 워크플로우 | MVP는 Markdown 중심으로 시작한다. PDF, DOCX는 후순위로 둔다. |
| 서버 DB 필수화 | 개인/소규모 프로젝트에서는 PostgreSQL 같은 상주 DB가 운영 부담을 키우므로 기본 경로에서 제외한다. |
| Neo4j 원본 DB화 | 원본은 프로젝트 로컬 사전 DB이며, Neo4j/Graphify는 후속 projection/export 대상이다. |
| 모든 문서 플랫폼 연동 | Google Docs, Notion, Confluence 연동은 후속 단계로 둔다. |
| Graphify 결과 자동 승인 | graphify 결과는 관찰 결과이므로 반드시 리뷰 큐를 통과해야 한다. |

---

## 3. 주요 아키텍처 결정

### ADR-001. 전역 CLI는 Python 패키지로 제공하고, 웹 UI는 로컬 옵션으로 둔다

Python은 문서 파싱, LLM 호출, embedding, graphify 실행, SQLite 조작, 배치 작업에 유리하다. 따라서 기본 제품 표면은 전역 `doc2dic` CLI이며, 사용자는 한 번 설치한 뒤 어떤 프로젝트에서도 `doc2dic init`, `doc2dic check`, `doc2dic review`, `doc2dic export`를 실행한다.

웹 UI는 필수 서버가 아니라 `doc2dic serve`가 현재 프로젝트의 `.doc2dic/glossary.sqlite3`를 열어 제공하는 로컬 옵션이다. 용어 테이블, 리뷰 큐, 문서 하이라이트, 그래프 노드 UI처럼 상호작용이 많은 화면은 React/TypeScript로 구현한다.

권장 스택:

```text
CLI / Core:
- Python 3.12+
- Typer 또는 Click
- Rich
- Pydantic v2
- SQLite
- sqlite-vec 또는 호환 vector extension
- 프로젝트 로컬 migration runner

Local Web UI:
- Node.js LTS
- Vite + React 또는 Next.js 정적 빌드
- TypeScript
- TanStack Query
- React Flow 또는 Cytoscape.js
- FastAPI 또는 Starlette 기반 로컬 API는 `doc2dic serve`에서만 실행

AI / Graph:
- LLM provider adapter
- Embedding provider adapter
- graphifyy CLI 연동
```

### ADR-002. 원본 데이터 모델은 Term이 아니라 Concept 중심으로 둔다

용어는 이름표이고, 개념은 의미이다. 같은 개념에 여러 용어가 붙을 수 있고, 같은 용어가 여러 개념을 가리킬 수도 있다. 따라서 원본 테이블은 `concepts`이고, 용어 표현은 `term_variants`로 분리한다.

```text
Concept: combat.stamina
  preferred term: 스태미나
  aliases: stamina
  forbidden terms: 행동력, 피로도

Concept: economy.energy
  preferred term: 피로도
  aliases: 입장 피로도
```

### ADR-003. Graphify는 원본 DB가 아니라 projection/export/import 레이어로 둔다

Graphify는 폴더를 분석하여 `graph.html`, `GRAPH_REPORT.md`, `graph.json` 같은 산출물을 만들 수 있다. 또한 OpenCode 플랫폼 설치도 지원한다. 그러나 Graphify가 만든 그래프에는 추론 관계와 애매한 관계가 포함될 수 있으므로, 이를 곧바로 원본 사전으로 삼으면 안 된다.

권장 역할 분담:

```text
프로젝트 로컬 SQLite 사전 DB:
- 승인된 개념과 용어의 원본
- 금지어, 폐기어, 별칭, 태그, 상태 관리

Graphify:
- 용어사전 그래프 export
- 기존 문서 관찰 그래프 생성
- query, report, MCP, Neo4j export 등 보조 기능
```

### ADR-004. LLM 판단은 항상 사람이 승인한다

LLM은 후보 추출과 분류에 강하지만, 기획 의도까지 확정할 수는 없다. 따라서 모든 새 용어, 별칭, 충돌, 금지어 제안은 `term_issues`에 저장하고 사람이 승인해야 한다.

### ADR-005. 기본 저장소는 SQLite + vector extension으로 둔다

프로젝트 목적은 개인/소규모 기획 문서 폴더마다 독립적인 사전을 관리하고, 전역 CLI로 반복 사용하는 것이다. PostgreSQL 같은 상주 서버는 설치·백업·프로젝트 분리 비용이 커서 기본값에 맞지 않는다.

기본 저장소는 다음처럼 둔다.

```text
<project-root>/.doc2dic/
  config.toml
  glossary.sqlite3
  imports/
  cache/
  graph_snapshots/
  glossary_export/
```

SQLite는 관계형 원본 데이터를 저장하고, vector extension은 embedding top-k 검색에만 사용한다. `sqlite-vec` 기준으로 `vec0` virtual table을 만들고, `embeddings.id`와 vector rowid를 맞춰 concept/candidate/chunk embedding을 조회한다. extension 교체 가능성을 위해 vector SQL은 `VectorStore` adapter 뒤에 숨긴다.

---

## 4. 시스템 구성도

```text
┌──────────────────────────────────────────────┐
│ Global CLI: doc2dic                           │
│ - init / status / config                       │
│ - concept / variant / relation CRUD            │
│ - check / analyze / review / search            │
│ - graph export / graphify import / serve       │
└──────────────────────┬───────────────────────┘
                       │ opens current project
┌──────────────────────▼───────────────────────┐
│ Project workspace                              │
│ - docs/**/*.md                                 │
│ - .doc2dic/config.toml                         │
│ - .doc2dic/glossary.sqlite3                    │
│ - .doc2dic/graph_snapshots                     │
└──────────────────────┬───────────────────────┘
                       │ same-process jobs
┌──────────────────────▼───────────────────────┐
│ Core pipeline                                  │
│ - 문서 파싱 / 청킹                              │
│ - exact / fuzzy / sqlite-vec 검색               │
│ - LLM 용어 후보 추출                            │
│ - 충돌 탐지                                     │
│ - 리뷰 큐 반영                                  │
│ - graphify export/import                       │
└──────────────────────┬───────────────────────┘
                       │ optional local serve
┌──────────────────────▼───────────────────────┐
│ Local Web UI: doc2dic serve                    │
│ - 용어사전 테이블                              │
│ - 문서 검사 결과                               │
│ - 리뷰 큐                                      │
│ - 그래프 뷰                                    │
└──────────────────────────────────────────────┘
```

---

## 5. 도메인 모델

### 5.1 핵심 용어 정의

| 용어 | 정의 | 예시 |
|---|---|---|
| Concept | 실제 의미 단위 | `combat.stamina` |
| TermVariant | Concept을 부르는 이름 | `스태미나`, `stamina`, `행동력` |
| Preferred Term | 공식 권장 용어 | `경직` |
| Alias | 허용되는 대체 표현 | `hit stun` |
| Forbidden Term | 쓰면 안 되는 표현 | `짧은 스턴` |
| Deprecated Term | 과거에는 썼지만 이제 쓰지 않는 표현 | `기력` |
| Occurrence | 문서 안에서 용어가 등장한 위치 | `combat_core.md:35` |
| Issue | 사람이 검토해야 하는 문제 후보 | `same_term_different_meaning` |
| Graph Snapshot | 특정 시점의 그래프 산출물 | `graphify-out/graph.json` |

### 5.2 Concept

```ts
type Concept = {
  id: string;                  // 예: "combat.stamina"
  preferredTerm: string;       // 예: "스태미나"
  definition: string;          // 승인된 정의
  scopeNote?: string;          // 사용 범위
  nonGoals?: string[];         // 이 개념이 아닌 것
  examples: string[];
  tags: string[];
  status: "proposed" | "approved" | "deprecated" | "rejected";
  owner?: string;
  createdFrom: SourceRef[];
  createdAt: string;
  updatedAt: string;
};
```

### 5.3 TermVariant

```ts
type TermVariant = {
  id: string;
  conceptId: string;
  label: string;
  normalizedLabel: string;
  language: "ko" | "en" | "ja" | "unknown";
  variantType:
    | "preferred"
    | "alias"
    | "abbreviation"
    | "forbidden"
    | "deprecated"
    | "candidate";
  reason?: string;
  status: "proposed" | "approved" | "rejected";
};
```

### 5.4 TermOccurrence

```ts
type TermOccurrence = {
  id: string;
  documentId: string;
  chunkId?: string;
  conceptId?: string;
  surface: string;
  normalizedSurface: string;
  surroundingText: string;
  sectionTitle?: string;
  startOffset?: number;
  endOffset?: number;
};
```

### 5.5 TermIssue

```ts
type TermIssue = {
  id: string;
  issueType:
    | "same_term_different_meaning"
    | "same_meaning_different_term"
    | "forbidden_term_used"
    | "deprecated_term_used"
    | "new_term_candidate"
    | "ambiguous_usage"
    | "missing_relation_candidate";
  severity: "info" | "warning" | "error";
  status: "open" | "accepted" | "dismissed" | "resolved";
  candidateTerm?: string;
  candidateDefinition?: string;
  candidateConceptIds: string[];
  recommendation: string;
  confidence: number;
  evidence: SourceRef[];
  createdAt: string;
  resolvedAt?: string;
};
```

---

## 6. 데이터베이스 설계

초기 구현은 프로젝트 로컬 SQLite 중심으로 진행한다. 각 프로젝트는 `.doc2dic/glossary.sqlite3` 하나를 원본으로 가지며, 벡터 검색은 SQLite vector extension을 사용한다. 기본 후보는 `sqlite-vec`이다.

운영 원칙:

```text
1. `doc2dic init`은 현재 프로젝트 루트에 `.doc2dic/`를 만들고 schema migration을 적용한다.
2. DB 파일은 프로젝트별로 독립적이다. 전역 CLI는 DB를 공유하지 않는다.
3. JSON 성격의 필드는 SQLite `text`에 canonical JSON으로 저장한다.
4. 시간 필드는 ISO-8601 UTC `text`로 저장한다.
5. UUID는 SQLite native 타입이 없으므로 `text`로 저장한다.
6. embedding vector는 일반 테이블이 아니라 vector extension virtual table에 저장한다.
```

### 6.1 테이블 목록

```text
concepts
term_variants
tags
concept_tags
concept_relations
documents
document_chunks
term_occurrences
term_issues
issue_evidence
embeddings
embedding_vectors
graph_snapshots
jobs
schema_migrations
settings
```

### 6.2 주요 테이블 설계

#### concepts

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | text pk | stable concept id. 예: `combat.stamina` |
| preferred_term | text | 공식 용어 |
| definition | text | 승인된 정의 |
| scope_note | text nullable | 사용 범위 |
| non_goals_json | text | 반례/혼동 방지 정보 JSON |
| examples_json | text | 승인된 예문 JSON |
| status | text | proposed/approved/deprecated/rejected |
| owner | text nullable | 담당자 |
| created_at | text | ISO-8601 생성일 |
| updated_at | text | ISO-8601 수정일 |

#### term_variants

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | text pk | variant id |
| concept_id | text fk | 연결된 concept |
| label | text | 실제 표현 |
| normalized_label | text | 정규화 표현 |
| language | text | ko/en/ja/unknown |
| variant_type | text | preferred/alias/abbreviation/forbidden/deprecated/candidate |
| reason | text nullable | 등록 사유 |
| status | text | proposed/approved/rejected |

#### concept_relations

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | text pk | relation id |
| source_concept_id | text fk | 출발 concept |
| target_concept_id | text fk | 도착 concept |
| relation_type | text | related_to, consumes, conflicts_with 등 |
| confidence | numeric | 0~1 |
| source_document_id | text nullable | 근거 문서 |
| status | text | proposed/approved/rejected |

#### documents

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | text pk | document id |
| title | text | 문서 제목 |
| path | text nullable | 파일 경로 |
| document_type | text | markdown/txt/docx/pdf 등 |
| content_hash | text | 변경 감지용 hash |
| raw_text | text | 추출된 텍스트 |
| status | text | imported/analyzing/analyzed/failed |
| created_at | text | ISO-8601 생성일 |

#### embeddings

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | integer pk | vector table rowid와 맞추는 embedding id |
| owner_type | text | concept/term_candidate/document_chunk/issue |
| owner_id | text | 대상 id |
| model | text | 사용 모델 |
| dimension | int | 차원 수 |
| content_hash | text | 같은 내용 재임베딩 방지용 hash |
| created_at | text | ISO-8601 생성일 |

#### embedding_vectors

`sqlite-vec` 기준 virtual table이다. 프로젝트 설정의 `embedding_dimension`이 1536이라면 다음과 같이 생성한다.

```sql
create virtual table embedding_vectors using vec0(
  embedding float[1536]
);
```

저장 규칙:

```text
- `embeddings.id`와 `embedding_vectors.rowid`를 동일하게 유지한다.
- KNN 검색은 `where embedding match ? order by distance limit ?` 형태로 실행한다.
- embedding dimension을 바꾸면 기존 vector table을 rebuild한다.
- extension 로딩 실패 시 exact/fuzzy 검색은 계속 동작하고 vector 검색만 disabled 상태로 표시한다.
```

---

## 7. 문서 분석 파이프라인

### 7.1 전체 흐름

```text
1. 문서 경로 지정 또는 폴더 스캔
2. 텍스트 추출
3. 섹션 단위 청킹
4. 등록된 용어 exact/fuzzy 매칭
5. LLM 용어 후보 추출
6. 후보 정의 embedding 생성
7. 기존 Concept top-k 검색
8. LLM 충돌 분류
9. TermIssue 생성
10. 리뷰 큐에서 승인/반려/병합/분리
```

### 7.2 문서 입력 우선순위

| 단계 | 포맷 | 설명 |
|---|---|---|
| MVP | Markdown, TXT | 구현 난도가 낮고 Git 관리에 적합하다. |
| 2차 | DOCX | 기획자가 워드 문서를 쓰는 경우를 지원한다. |
| 3차 | PDF | 레이아웃과 표 처리 난도가 높으므로 후순위로 둔다. |
| 4차 | Google Docs / Notion / Confluence | 플랫폼 연동 단계에서 추가한다. |

### 7.3 용어 후보 추출 JSON Schema

LLM 출력은 반드시 구조화된 JSON으로 받는다. 자유 문장 응답은 저장하지 않는다.

```json
{
  "type": "object",
  "required": ["candidates"],
  "properties": {
    "candidates": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "surface",
          "definition",
          "term_type",
          "tags",
          "evidence",
          "confidence"
        ],
        "properties": {
          "surface": { "type": "string" },
          "definition": { "type": "string" },
          "term_type": {
            "type": "string",
            "enum": ["mechanic", "resource", "state", "action", "stat", "entity", "rule", "ui-label", "lore", "unknown"]
          },
          "tags": {
            "type": "array",
            "items": { "type": "string" }
          },
          "evidence": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["quote"],
              "properties": {
                "quote": { "type": "string" },
                "section_title": { "type": "string" }
              }
            }
          },
          "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
          }
        }
      }
    }
  }
}
```

### 7.4 충돌 분류 JSON Schema

```json
{
  "type": "object",
  "required": ["classification", "reason", "recommendation", "confidence"],
  "properties": {
    "classification": {
      "type": "string",
      "enum": [
        "same_concept",
        "alias_candidate",
        "same_term_different_meaning",
        "same_meaning_different_term",
        "new_concept",
        "ambiguous"
      ]
    },
    "target_concept_id": { "type": ["string", "null"] },
    "reason": { "type": "string" },
    "recommendation": { "type": "string" },
    "confidence": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    }
  }
}
```

---

## 8. 충돌 탐지 전략

충돌 탐지는 한 번의 LLM 호출로 끝내지 않는다. 검색과 분류를 단계적으로 나눈다.

### 8.1 1단계: 정규화 및 exact match

정규화 예시:

```text
쿨 다운 → 쿨다운
Cooldown → cooldown
스태미나  → 스태미나
```

검출 항목:

```text
- 이미 등록된 preferred term
- alias
- forbidden term
- deprecated term
```

### 8.2 2단계: fuzzy match

문자열 유사도 기반으로 오타, 띄어쓰기, 약어 후보를 찾는다.

예시:

```text
쿨다운 / 쿨 다운 / 쿨타임 / cooldown
```

### 8.3 3단계: embedding search

후보 정의와 기존 concept 정의를 embedding으로 비교한다.

검색 대상:

```text
- concept.definition
- concept.scope_note
- concept.examples
- term occurrence 주변 문맥
```

검색 결과는 top-k 후보로만 사용한다. embedding 점수만으로 동일 의미를 확정하지 않는다.

### 8.4 4단계: LLM conflict classifier

LLM은 다음 입력을 받는다.

```text
- 후보 용어
- 후보 정의
- 후보가 나온 근거 문장
- embedding 검색으로 찾은 기존 concept top-k
- 각 concept의 definition, examples, non_goals, forbidden terms
```

출력은 다음 분류 중 하나다.

```text
same_concept
alias_candidate
same_term_different_meaning
same_meaning_different_term
new_concept
ambiguous
```

### 8.5 5단계: 리뷰 큐 등록

LLM 결과는 자동 반영하지 않고 `term_issues`에 저장한다.

---

## 9. 리뷰 큐 UX

리뷰 큐는 본 프로젝트의 핵심 화면이다. 사용자는 AI가 제안한 후보를 보고 다음 액션 중 하나를 선택한다.

| 액션 | 결과 |
|---|---|
| 기존 개념에 연결 | 후보 occurrence를 기존 concept에 연결한다. |
| 별칭으로 등록 | `term_variants`에 alias로 추가한다. |
| 금지어로 등록 | `term_variants`에 forbidden으로 추가한다. |
| 폐기어로 등록 | `term_variants`에 deprecated로 추가한다. |
| 새 개념 생성 | 새 `concept`을 proposed 또는 approved 상태로 생성한다. |
| 기존 개념과 분리 | 같은 표면 용어지만 다른 concept으로 분리한다. |
| 관계 추가 | `concept_relations`에 관계 후보를 등록한다. |
| 무시 | 이슈를 dismissed 처리한다. |

리뷰 화면 예시:

```text
[문제 유형]
same_term_different_meaning

[후보 용어]
스태미나

[기존 의미]
회피, 달리기, 강공격에 소모되는 전투 자원

[새 문맥]
스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.

[AI 추천]
새 concept으로 분리하고, preferred term을 "피로도" 또는 "입장 피로도"로 지정하는 것을 검토한다.

[가능한 액션]
- 기존 개념에 연결
- 새 개념 생성
- 용어 변경 제안
- 무시
```

---

## 10. Graph 모델

### 10.1 내부 그래프 노드

| 노드 타입 | 설명 | 예시 id |
|---|---|---|
| Concept | 승인 또는 후보 개념 | `concept:combat.stamina` |
| Term | 용어 표현 | `term:스태미나` |
| Document | 기획 문서 | `document:combat_core` |
| Issue | 검토 이슈 | `issue:uuid` |
| Tag | 태그. 초기에는 속성으로 두고 필요 시 노드화 | `tag:combat` |

### 10.2 내부 그래프 Edge

| relation | 의미 |
|---|---|
| preferred_label_of | preferred term이 concept을 가리킨다. |
| alias_of | alias가 concept을 가리킨다. |
| forbidden_alias_of | 금지어가 concept을 가리킨다. |
| deprecated_alias_of | 폐기어가 concept을 가리킨다. |
| used_in | concept/term이 문서에 사용된다. |
| defined_in | concept이 문서에서 정의된다. |
| same_meaning_candidate_of | 같은 의미 후보이다. |
| different_meaning_candidate_of | 같은 표면 용어의 다른 의미 후보이다. |
| conflicts_with | 의미 충돌 관계이다. |
| do_not_confuse_with | 혼동하면 안 되는 관계이다. |
| related_to | 일반 관련 관계이다. |
| broader_than | 상위 개념이다. |
| narrower_than | 하위 개념이다. |
| consumes | 자원을 소모한다. |
| produces | 자원을 생성한다. |
| requires | 조건으로 요구한다. |
| unlocks | 해금한다. |
| displayed_as | UI에서 표시된다. |
| implemented_by | 개발 구현 단위와 연결된다. |

### 10.3 게임 기획 특화 relation 후보

```text
has_resource
spends_resource
grants_status
removes_status
triggers
scales_with
gated_by
displayed_as
implemented_by
balanced_by
```

---

## 11. Graphify 연동 계획

### 11.1 Graphify 역할

Graphify는 폴더를 분석해 query 가능한 knowledge graph를 생성하고, `graph.html`, `GRAPH_REPORT.md`, `graph.json` 산출물을 만든다. 본 프로젝트에서는 이 기능을 다음 세 가지 방식으로 활용한다.

### 11.2 방식 A: 용어사전 DB → graphify-compatible graph.json

가장 먼저 구현할 방식이다. 내부 DB의 concept, term, issue, document를 graphify가 이해하기 쉬운 `nodes`/`edges` 구조로 변환한다.

```json
{
  "nodes": [
    {
      "id": "concept:combat.stamina",
      "label": "스태미나",
      "file_type": "concept",
      "source_file": "glossary/concepts/combat.stamina.md",
      "tags": ["combat", "resource", "player-facing"],
      "status": "approved"
    }
  ],
  "edges": [
    {
      "source": "concept:combat.heavy_attack",
      "target": "concept:combat.stamina",
      "relation": "spends_resource",
      "confidence": "EXTRACTED",
      "confidence_score": 0.92,
      "source_file": "docs/combat_core.md"
    }
  ]
}
```

장점:

```text
- 원본 DB를 오염시키지 않는다.
- graphify 버전 변경 시 adapter만 수정하면 된다.
- 웹 그래프와 graphify 산출물을 같은 내부 그래프 모델에서 만들 수 있다.
```

### 11.3 방식 B: 용어사전 DB → 가상 Markdown corpus → graphify 실행

용어사전 concept을 Markdown 파일로 export한 뒤 graphify CLI로 분석한다.

```text
glossary_export/
  concepts/
    combat.stamina.md
    combat.stagger.md
  variants/
    action_power.md
  issues/
    issue-001-stamina-conflict.md
```

예시 Markdown:

```md
# 스태미나

id: concept:combat.stamina
status: approved
tags: combat, resource, player-facing

## Definition

회피, 달리기, 강공격에 소모되는 전투 자원.

## Preferred Term

스태미나

## Aliases

- stamina

## Forbidden Terms

- 행동력
- 피로도

## Do Not Confuse With

- concept:economy.energy: 던전 입장에 쓰는 계정 단위 자원.
```

장점:

```text
- 사람이 읽기 쉽다.
- Git 버전 관리에 적합하다.
- LLM과 graphify 모두에게 친화적이다.
- Obsidian, MkDocs, Docusaurus 등으로 확장하기 쉽다.
```

### 11.4 방식 C: 기존 문서 폴더 → graphify 관찰 그래프 → 리뷰 큐 import

기존 기획 문서가 많아지면 graphify로 전체 폴더를 분석하고, 그 결과를 용어사전 그래프와 비교한다.

```text
기획 문서 폴더
  ↓
graphify 실행
  ↓
graphify-out/graph.json
  ↓
GraphifyImportService
  ↓
용어사전 DB와 비교
  ↓
TermIssue 생성
```

주의점:

```text
- graphify 결과는 관찰 그래프다.
- 관찰 그래프는 승인된 기획 기준이 아니다.
- import 결과는 반드시 리뷰 큐를 통과해야 한다.
```

### 11.5 Graphify CLI 운영 명령 예시

```bash
# 설치. 실제 버전은 프로젝트에서 pinning한다.
uv tool install graphifyy

# OpenCode 플랫폼용 설치
 graphify install --platform opencode --project

# 현재 폴더 분석
 graphify .

# 산출물 예시
 graphify-out/graph.html
 graphify-out/GRAPH_REPORT.md
 graphify-out/graph.json
```

프로젝트에서는 전역 `doc2dic` CLI가 graphify CLI를 subprocess로 실행하는 방식을 먼저 사용한다. 내부 Python API 직접 import는 후속 최적화로 둔다.

---

## 12. CLI/Core 구현 계획

### 12.1 모듈 구조

```text
src/doc2dic/
  __init__.py
  cli.py
  config.py
  project.py
  paths.py
  output.py
  storage/
    connection.py
    migrations.py
    schema.sql
    vector_store.py
    repositories/
      concepts.py
      documents.py
      issues.py
      graphs.py
  domain/
    concept.py
    term_variant.py
    document.py
    issue.py
    graph.py
  services/
    glossary_service.py
    document_parser.py
    chunking_service.py
    llm_service.py
    embedding_service.py
    conflict_detector.py
    review_service.py
    graph_projection_service.py
    graphify_adapter.py
    graphify_import_service.py
  server/
    app.py
    routes_concepts.py
    routes_documents.py
    routes_issues.py
    routes_search.py
    routes_graphs.py
  tests/

web/
  package.json
  src/
    app/
    components/
    lib/

install.sh
pyproject.toml
```

`server/`와 `web/`는 `doc2dic serve`에서만 사용한다. CLI 명령은 FastAPI 서버를 띄우지 않고 SQLite를 직접 연다.

### 12.2 주요 서비스 책임

| 서비스 | 책임 |
|---|---|
| ProjectResolver | 현재 디렉터리에서 프로젝트 루트와 `.doc2dic/` 위치를 찾는다. |
| MigrationRunner | `.doc2dic/glossary.sqlite3` schema version을 올린다. |
| VectorStore | sqlite vector extension 로딩, vector table 생성, top-k 검색을 캡슐화한다. |
| GlossaryService | Concept, TermVariant, Tag, Relation CRUD와 병합/분리 처리 |
| DocumentParser | Markdown/TXT/DOCX/PDF 텍스트 추출 |
| ChunkingService | 문서를 section/chunk 단위로 분리 |
| LLMService | structured output 기반 용어 후보 추출/충돌 분류 |
| EmbeddingService | embedding 생성, SQLite/vector table 저장, top-k 검색 |
| ConflictDetector | exact/fuzzy/vector/LLM 기반 이슈 생성 |
| ReviewService | 이슈 승인/반려/해결 액션 처리 |
| GraphProjectionService | 내부 DB를 웹 그래프 노드/edge로 변환 |
| GraphifyAdapter | graphify-compatible graph.json 및 가상 Markdown corpus export |
| GraphifyImportService | graphify 관찰 그래프를 리뷰 후보로 import |

### 12.3 CLI 명령 초안

```text
doc2dic --help

doc2dic init [--force]
doc2dic status
doc2dic config get <key>
doc2dic config set <key> <value>

doc2dic concept list [--tag TAG] [--status STATUS]
doc2dic concept show <concept-id>
doc2dic concept add <concept-id> --term <term> --definition <text>
doc2dic concept edit <concept-id>
doc2dic concept deprecate <concept-id>

doc2dic variant add <concept-id> <label> --type alias|forbidden|deprecated|abbreviation
doc2dic relation add <source-id> <relation> <target-id>

doc2dic check <path> [--write-issues]
doc2dic analyze <path> [--llm] [--embedding]
doc2dic review list [--status open]
doc2dic review show <issue-id>
doc2dic review accept <issue-id> --as alias|forbidden|new-concept|relation
doc2dic review dismiss <issue-id>

doc2dic search term <query>
doc2dic search similar --text <text> --limit 10

doc2dic graph current --json
doc2dic graph export --format graphify|app-graph|markdown
doc2dic graphify import <graph-json>

doc2dic serve [--host 127.0.0.1] [--port 8765]
```

### 12.4 로컬 API 초안

`doc2dic serve`는 현재 프로젝트 DB만 여는 로컬 API를 제공한다.

```text
GET    /api/health

GET    /api/concepts
POST   /api/concepts
GET    /api/concepts/{concept_id}
PATCH  /api/concepts/{concept_id}
DELETE /api/concepts/{concept_id}

POST   /api/concepts/{concept_id}/variants
PATCH  /api/variants/{variant_id}
DELETE /api/variants/{variant_id}

POST   /api/documents/analyze-path
GET    /api/documents
GET    /api/documents/{document_id}
GET    /api/documents/{document_id}/occurrences

GET    /api/issues
GET    /api/issues/{issue_id}
POST   /api/issues/{issue_id}/accept
POST   /api/issues/{issue_id}/dismiss
POST   /api/issues/{issue_id}/resolve-as-new-concept
POST   /api/issues/{issue_id}/resolve-as-alias
POST   /api/issues/{issue_id}/resolve-as-forbidden

GET    /api/search/concepts?q=
GET    /api/search/similar-concepts?text=

GET    /api/graphs/current
POST   /api/graphs/rebuild
GET    /api/graphs/snapshots
GET    /api/graphs/snapshots/{snapshot_id}
POST   /api/graphs/graphify/export
POST   /api/graphs/graphify/import
```

---

## 13. Local Web UI 구현 계획

### 13.1 화면 구조

```text
web/
  src/
    app/
    layout.tsx
    page.tsx
    glossary/
      page.tsx
      [conceptId]/page.tsx
    documents/
      page.tsx
      [documentId]/page.tsx
    review/
      page.tsx
    graph/
      page.tsx
    settings/
      page.tsx
    components/
    glossary/
      ConceptTable.tsx
      ConceptForm.tsx
      VariantList.tsx
      RelationEditor.tsx
    documents/
      DocumentUploader.tsx
      DocumentViewer.tsx
      HighlightedText.tsx
      OccurrencePanel.tsx
    review/
      IssueList.tsx
      IssueDetail.tsx
      ReviewActionPanel.tsx
    graph/
      GraphCanvas.tsx
      GraphFilters.tsx
      NodeDetailPanel.tsx
      EdgeDetailPanel.tsx
    shared/
      TagInput.tsx
      StatusBadge.tsx
      ConfidenceBadge.tsx
    lib/
    api.ts
    types.ts
    graph.ts
```

### 13.2 주요 화면

#### 용어사전 화면

기능:

```text
- Concept 목록
- preferred term 검색
- tag 필터
- status 필터
- forbidden/deprecated 용어만 보기
- concept 생성/수정
- variant 추가/수정
```

#### 문서 검사 화면

기능:

```text
- 문서 경로 선택 또는 폴더 스캔
- 분석 상태 표시
- 문서 본문 하이라이트
- 등록된 용어 표시
- 금지어/폐기어 표시
- 새 후보 표시
- 오른쪽 패널에서 이슈 확인
```

#### 리뷰 큐 화면

기능:

```text
- issue type별 필터
- severity별 필터
- confidence 정렬
- evidence 확인
- 승인/반려/새 concept 생성/alias 등록/forbidden 등록
```

#### 그래프 화면

기능:

```text
- Concept, Term, Document, Issue 노드 표시
- relation edge 표시
- tag/status/issue type 필터
- 노드 클릭 시 상세 패널
- edge 클릭 시 근거 문서 표시
- graphify snapshot 선택
```

초기에는 React Flow를 우선 사용한다. 이유는 노드 클릭, 패널 연동, 필터, 편집형 UI를 빠르게 구현하기 쉽기 때문이다. 네트워크 분석형 대규모 그래프가 중요해지면 Cytoscape.js를 추가 검토한다.

---

## 14. Repository 구조

```text
project-root/
  IMPLEMENTATION_PLAN.md
  README.md
  AGENTS.md
  .env.example
  install.sh
  pyproject.toml

  contracts/
    openapi.yaml
    schemas/
      concept.schema.json
      term_variant.schema.json
      issue.schema.json
      llm_term_candidates.schema.json
      llm_conflict_classification.schema.json
      app_graph.schema.json
      graphify_projection.schema.json

  src/
    doc2dic/
      cli.py
      config.py
      project.py
      storage/
      domain/
      services/
      server/

  tests/
    unit/
    integration/

  web/
    package.json
    tsconfig.json
    src/
      app/
      components/
      lib/
    tests/

  samples/
    docs/
      combat_core.md
      dungeon_draft.md
      ui_terms.md
    expected/
      term_candidates.json
      issues.json
      graph.json

  scripts/
    dev-cli.sh
    dev-web.sh
    test.sh
    graphify_export.sh

  docs/
    architecture.md
    data-model.md
    graphify-integration.md
    opencode-workflow.md

  # 런타임 생성물. 보통 .gitignore 대상.
  .doc2dic/
    config.toml
    glossary.sqlite3
    imports/
    cache/
    graph_snapshots/
    glossary_export/

  handoff/
    cli-storage.md
    cli-analysis.md
    cli-graphify.md
    web-shell.md
    web-glossary.md
    web-review.md
    web-graph.md
    qa.md
    packaging.md
```

`handoff/`는 subagent가 작업 종료 시 요약을 남기는 디렉터리다. 병렬 작업 후 main agent가 통합할 때 이 파일들을 읽는다.

---

## 15. OpenCode 병렬 개발 전략

### 15.1 기본 원칙

OpenCode는 primary agent와 subagent를 나누어 사용할 수 있다. primary agent는 대화와 전체 조율을 담당하고, subagent는 특정 작업을 위임받아 수행한다. 프로젝트에서는 다음 규칙을 둔다.

```text
1. primary agent는 계획, 분업, 통합, 최종 리뷰를 담당한다.
2. subagent는 자신에게 배정된 파일 경로만 수정한다.
3. subagent는 다른 subagent를 호출하지 않는다.
4. 모든 병렬 작업은 primary/orchestrator가 직접 분배한다.
5. 공통 contract 파일은 병렬 작업 전에 먼저 확정한다.
6. 각 subagent는 작업 후 handoff/<agent-name>.md를 남긴다.
7. 통합 전에는 test, lint, typecheck를 실행한다.
```

### 15.2 권장 OpenCode agent 구성

OpenCode는 `.opencode/agents/`에 Markdown agent 파일을 둘 수 있다. 아래 파일들을 프로젝트에 추가하는 것을 권장한다.

```text
.opencode/agents/
  cli-storage.md
  cli-analysis.md
  cli-graphify.md
  web-shell.md
  web-glossary.md
  web-review.md
  web-graph.md
  qa.md
  packaging.md
  docs.md
```

### 15.3 Subagent 파일 소유권

| Subagent | 수정 가능 경로 | 읽기 전용 경로 | 주요 산출물 |
|---|---|---|---|
| cli-storage | `src/doc2dic/storage`, `src/doc2dic/domain`, `contracts/schemas` | `web`, `docs` | SQLite schema, migration, vector store, Pydantic schema |
| cli-analysis | `src/doc2dic/services/document_*`, `src/doc2dic/services/llm_service.py`, `src/doc2dic/services/embedding_service.py`, `src/doc2dic/services/conflict_detector.py` | `web`, `src/doc2dic/storage` | 문서 분석 파이프라인 |
| cli-graphify | `src/doc2dic/services/graph_projection_service.py`, `src/doc2dic/services/graphify_*`, `scripts/graphify_export.sh`, `docs/graphify-integration.md` | `web`, `src/doc2dic/storage` | graphify adapter/export/import |
| web-shell | `web/src/app/layout.tsx`, `web/src/app/page.tsx`, `web/src/lib`, `web/src/components/shared` | `src/doc2dic` | 로컬 웹 UI 레이아웃, API client, 공통 컴포넌트 |
| web-glossary | `web/src/app/glossary`, `web/src/components/glossary` | `src/doc2dic`, `web/src/components/shared` | 용어사전 UI |
| web-review | `web/src/app/review`, `web/src/app/documents`, `web/src/components/review`, `web/src/components/documents` | `src/doc2dic`, `web/src/components/shared` | 리뷰 큐, 문서 검사 UI |
| web-graph | `web/src/app/graph`, `web/src/components/graph`, `web/src/lib/graph.ts` | `src/doc2dic`, `web/src/components/shared` | 그래프 시각화 UI |
| qa | `tests`, `web/tests`, `samples/expected`, `scripts/test.sh` | 전체 | 테스트, fixture, 품질 게이트 |
| packaging | `install.sh`, `pyproject.toml`, `.env.example`, `scripts`, CI config | 전체 | 전역 설치, CLI 배포, 개발 스크립트, CI |
| docs | `README.md`, `AGENTS.md`, `docs`, `handoff` 요약 정리 | 전체 | 개발자 문서, 운영 가이드 |

### 15.4 병렬 개발 Wave

#### Wave 0: Contract-first scaffold

담당: primary agent 또는 cli-storage + web-shell 순차 작업

목표:

```text
- repository scaffold 생성
- contracts/schemas 초안 작성
- `doc2dic --help`와 `doc2dic init` 기본 실행 확인
- `doc2dic serve` 로컬 웹 UI 기본 실행 확인
- .env.example 작성
- install.sh 초안 작성
```

완료 조건:

```text
- `doc2dic --help` 동작
- 샘플 디렉터리에서 `doc2dic init`이 `.doc2dic/glossary.sqlite3` 생성
- `doc2dic serve` health check와 web home page 동작
- contracts/schemas에 핵심 JSON schema 존재
- 각 subagent의 파일 소유권이 README/AGENTS.md에 명시됨
```

#### Wave 1: 독립 기반 구현

병렬 가능 subagent:

```text
cli-storage
web-shell
packaging
docs
```

목표:

```text
- SQLite schema, migration, vector store 작성
- API client와 공통 UI 작성
- 전역 CLI 설치 스크립트 작성
- AGENTS.md와 작업 규칙 작성
```

#### Wave 2: 기능별 병렬 구현

병렬 가능 subagent:

```text
cli-analysis
cli-graphify
web-glossary
web-review
web-graph
qa
```

목표:

```text
- 문서 분석 파이프라인 구현
- graph projection/export 구현
- 용어사전 UI 구현
- 리뷰 큐 UI 구현
- 그래프 UI 구현
- fixture 기반 테스트 작성
```

#### Wave 3: 통합

담당: primary agent + qa

목표:

```text
- API contract와 web type 정합성 확인
- 실제 sample docs로 end-to-end 확인
- graphify export 산출물 확인
- README의 실행 방법 검증
```

#### Wave 4: 안정화

담당: qa + packaging + 각 기능 담당

목표:

```text
- 에러 처리
- empty state
- loading state
- test coverage 보강
- LLM/embedding provider mock 정리
- graph snapshot regression test
```

---

## 16. Subagent 작업 지시 템플릿

### 16.1 공통 지시문

각 subagent에게 아래 공통 지시를 붙인다.

```text
이 프로젝트는 기획 용어사전 기반 문서 일관성 검사기이다.
원본 데이터는 프로젝트별 `.doc2dic/glossary.sqlite3`이며, graphify는 보조 그래프 projection/export/import 레이어이다.

반드시 지킬 규칙:
1. 본인에게 배정된 수정 가능 경로만 편집한다.
2. contracts/의 타입과 schema를 먼저 확인한다.
3. API나 schema 변경이 필요하면 handoff 파일에 제안만 남기고 임의 변경하지 않는다.
4. 작업 종료 시 handoff/<agent-name>.md에 변경사항, 미완료 항목, 테스트 결과를 기록한다.
5. subagent가 다른 subagent를 호출하지 않는다.
6. LLM/embedding API key는 코드에 하드코딩하지 않는다.
7. 자동 승인 로직을 만들지 않는다. 모든 추론 결과는 review queue로 보낸다.
```

### 16.2 cli-storage 지시문

```text
목표:
전역 CLI가 사용하는 SQLite schema, migration, Pydantic domain schema, vector store를 구현한다.

수정 가능 경로:
- src/doc2dic/storage
- src/doc2dic/domain
- contracts/schemas

필수 구현:
- Concept
- TermVariant
- Tag
- ConceptRelation
- Document
- DocumentChunk
- TermOccurrence
- TermIssue
- IssueEvidence
- Embedding
- GraphSnapshot
- schema_migrations
- settings
- sqlite-vec 기반 VectorStore

완료 조건:
- `doc2dic init`이 `.doc2dic/glossary.sqlite3` 생성
- migration 재실행이 idempotent
- sqlite-vec 미설치/로딩 실패 시 vector 기능만 disabled 상태로 처리
- pytest에서 storage/domain 기본 테스트 통과
- handoff/cli-storage.md 작성
```

### 16.3 cli-analysis 지시문

```text
목표:
문서 분석, 용어 후보 추출, embedding 검색, 충돌 분류 파이프라인을 구현한다.

수정 가능 경로:
- src/doc2dic/services/document_parser.py
- src/doc2dic/services/chunking_service.py
- src/doc2dic/services/llm_service.py
- src/doc2dic/services/embedding_service.py
- src/doc2dic/services/conflict_detector.py
- src/doc2dic/cli.py의 analyze/check 명령 연결부

필수 구현:
- Markdown/TXT parser
- section-based chunking
- exact/fuzzy term matching
- LLM provider interface
- Embedding provider interface
- mocked provider for tests
- TermIssue 생성 로직
- SQLite/vector store를 통한 similar concept 검색

완료 조건:
- samples/docs를 분석해 samples/expected/issues.json과 유사한 결과 생성
- 외부 API 없이 mock으로 테스트 가능
- `doc2dic check samples/docs`가 CLI 출력과 issue 저장을 모두 검증
- handoff/cli-analysis.md 작성
```

### 16.4 cli-graphify 지시문

```text
목표:
내부 DB graph projection과 graphify 연동 adapter를 구현한다.

수정 가능 경로:
- src/doc2dic/services/graph_projection_service.py
- src/doc2dic/services/graphify_adapter.py
- src/doc2dic/services/graphify_import_service.py
- src/doc2dic/server/routes_graphs.py
- src/doc2dic/cli.py의 graph/graphify 명령 연결부
- scripts/graphify_export.sh
- docs/graphify-integration.md

필수 구현:
- 내부 graph API용 nodes/edges 생성
- graphify-compatible graph.json export
- glossary_export Markdown corpus export
- graphify CLI subprocess wrapper
- graphify-out graph.json import parser
- import 결과를 TermIssue 후보로 변환

완료 조건:
- 샘플 `.doc2dic/glossary.sqlite3` fixture에서 graph.json 생성
- snapshot test 작성
- graphify CLI가 없는 환경에서도 graceful failure
- handoff/cli-graphify.md 작성
```

### 16.5 web-shell 지시문

```text
목표:
로컬 웹 UI의 기본 레이아웃, 라우팅, API client, 공통 컴포넌트를 구현한다.

수정 가능 경로:
- web/src/app/layout.tsx
- web/src/app/page.tsx
- web/src/lib
- web/src/components/shared

필수 구현:
- API client
- error/loading state helper
- StatusBadge
- ConfidenceBadge
- TagInput
- AppShell navigation

완료 조건:
- `doc2dic serve` 또는 web dev server 실행
- 기본 라우팅 동작
- handoff/web-shell.md 작성
```

### 16.6 web-glossary 지시문

```text
목표:
용어사전 목록과 Concept 상세 편집 UI를 구현한다.

수정 가능 경로:
- web/src/app/glossary
- web/src/components/glossary

필수 구현:
- ConceptTable
- ConceptDetail
- ConceptForm
- VariantList
- RelationEditor
- tag/status 필터

완료 조건:
- mock API 또는 실제 API client로 목록/상세 표시
- create/update flow UI 연결
- handoff/web-glossary.md 작성
```

### 16.7 web-review 지시문

```text
목표:
문서 검사 화면과 리뷰 큐 화면을 구현한다.

수정 가능 경로:
- web/src/app/review
- web/src/app/documents
- web/src/components/review
- web/src/components/documents

필수 구현:
- DocumentUploader
- DocumentViewer
- HighlightedText
- IssueList
- IssueDetail
- ReviewActionPanel
- accept/dismiss/resolve action buttons

완료 조건:
- issue type별 필터 동작
- evidence 표시
- review action API 호출 연결
- handoff/web-review.md 작성
```

### 16.8 web-graph 지시문

```text
목표:
웹 그래프 시각화 화면을 구현한다.

수정 가능 경로:
- web/src/app/graph
- web/src/components/graph
- web/src/lib/graph.ts

필수 구현:
- GraphCanvas
- GraphFilters
- NodeDetailPanel
- EdgeDetailPanel
- graph snapshot selector
- tag/status/issue type filter

완료 조건:
- /api/graphs/current 응답으로 그래프 렌더링
- 노드 클릭 시 상세 패널 표시
- edge 클릭 시 relation/evidence 표시
- handoff/web-graph.md 작성
```

### 16.9 qa 지시문

```text
목표:
프로젝트 전체의 테스트 전략과 fixture를 구현한다.

수정 가능 경로:
- tests
- web/tests
- samples
- scripts/test.sh

필수 구현:
- core/storage unit test
- CLI integration test
- local API integration test
- graph snapshot test
- frontend component smoke test
- sample docs와 expected outputs
- mocked LLM/embedding provider

완료 조건:
- scripts/test.sh 하나로 주요 테스트 실행
- CI에서 외부 API 없이 통과
- handoff/qa.md 작성
```

### 16.10 packaging 지시문

```text
목표:
전역 CLI 설치, 개발 스크립트, 환경 변수, CI 초안을 구성한다.

수정 가능 경로:
- install.sh
- pyproject.toml
- .env.example
- scripts
- .github/workflows 또는 선택한 CI 경로

필수 구현:
- `curl ... | sh` 형태의 1회 설치 스크립트
- `uv tool install` 또는 wheel 기반 전역 설치 흐름
- `doc2dic --help` smoke check
- `doc2dic init` smoke check
- 로컬 web dev/serve command
- seed command

완료 조건:
- 새 셸에서 `doc2dic --help` 실행 가능
- 임시 프로젝트에서 `doc2dic init`으로 `.doc2dic/glossary.sqlite3` 생성
- .env.example에 필요한 키 정리
- handoff/packaging.md 작성
```

---

## 17. AGENTS.md 권장 내용

프로젝트 루트에 `AGENTS.md`를 두고 다음 내용을 포함한다.

```md
# AGENTS.md

## Project Summary

This repository implements a glossary-driven planning document consistency checker for game design documents.

The source of truth is the project-local `.doc2dic/glossary.sqlite3` database. Graphify outputs are derived artifacts and must not directly mutate the glossary without review.

## Hard Rules

1. Do not edit files outside your assigned path ownership.
2. Do not hardcode LLM or embedding API keys.
3. Do not auto-approve LLM or graphify findings.
4. All inferred findings must become review queue issues.
5. Update `handoff/<agent-name>.md` after each task.
6. Run relevant tests before finishing.

## Architecture

- Product surface: globally installed Python CLI `doc2dic`
- Local web UI: React/TypeScript launched by `doc2dic serve`
- DB: project-local SQLite + vector extension
- Graph: internal graph projection + graphify-compatible export
- Worker model: same-process CLI jobs for document analysis, embeddings, graphify jobs

## Source of Truth

- `concepts` and `term_variants` are authoritative.
- `.doc2dic/glossary.sqlite3` is project-local and authoritative.
- `graph_snapshots` are derived.
- `graphify-out` is generated.
- `term_issues` is the human review boundary.
```

---

## 18. OpenCode agent config 예시

아래는 `.opencode/agents/cli-graphify.md` 예시다.

```md
---
description: Implements Graphify projection, export, import, and graph snapshot CLI/core features.
mode: subagent
temperature: 0.1
permission:
  edit: allow
  bash:
    "*": ask
    "pytest*": allow
    "python*": allow
    "ruff*": allow
---

You are the CLI Graphify integration agent.

Scope:
- src/doc2dic/services/graph_projection_service.py
- src/doc2dic/services/graphify_adapter.py
- src/doc2dic/services/graphify_import_service.py
- src/doc2dic/server/routes_graphs.py
- src/doc2dic/cli.py graph/graphify command wiring
- scripts/graphify_export.sh
- docs/graphify-integration.md

Do not edit web UI files or storage/domain schema unless explicitly instructed.

The project-local `.doc2dic/glossary.sqlite3` DB is the source of truth. Graphify output is a derived artifact.
All imported graphify findings must become review queue issues, never approved concepts directly.

At the end, write handoff/cli-graphify.md with:
- changed files
- implemented behavior
- test command and result
- known gaps
```

CLI storage agent 예시:

```md
---
description: Implements SQLite schema, Pydantic domain schemas, local migrations, vector store, and DB fixtures.
mode: subagent
temperature: 0.1
permission:
  edit: allow
  bash:
    "*": ask
    "pytest*": allow
    "doc2dic*": allow
    "ruff*": allow
---

You are the CLI storage agent.

Only edit:
- src/doc2dic/storage
- src/doc2dic/domain
- contracts/schemas

Preserve the Concept-centered model.
Use project-local SQLite plus vector extension. Do not implement LLM, web UI, or graphify runtime logic.
Write handoff/cli-storage.md before finishing.
```

---

## 19. MVP 단계별 구현 계획

### Phase 0. 프로젝트 골격

목표:

```text
- CLI 패키지 구조 생성
- `doc2dic --help` 기본 실행
- `doc2dic init`로 프로젝트 로컬 SQLite DB 생성
- 선택적 web UI 기본 실행
- contracts/schemas 초안 작성
- AGENTS.md 작성
```

완료 기준:

```text
- `doc2dic --help` 응답
- `doc2dic init` 실행 시 `.doc2dic/glossary.sqlite3` 생성
- `doc2dic status`가 현재 프로젝트 사전 상태 출력
- `doc2dic serve` 실행 시 local web home page 렌더링
- README에 실행 방법 존재
```

### Phase 1. 수동 용어사전

목표:

```text
- Concept CRUD
- TermVariant CRUD
- Tag 관리
- Relation 관리
- CLI 기반 용어사전 관리
- 선택적 용어사전 화면
```

완료 기준:

```text
- concept 생성/수정/조회 가능
- preferred/alias/forbidden/deprecated variant 등록 가능
- tag 필터 가능
- 위 기능이 `doc2dic concept`, `doc2dic variant`, `doc2dic search`로 동작
```

### Phase 2. 문서 경로 분석과 등록 용어 탐지

목표:

```text
- Markdown/TXT 경로 지정 또는 폴더 스캔
- 텍스트 추출
- 등록된 용어 exact/fuzzy 탐지
- 금지어/폐기어 사용 이슈 생성
- CLI 검사 리포트와 선택적 문서 하이라이트 UI
```

완료 기준:

```text
- 샘플 문서에서 등록 용어가 하이라이트됨
- forbidden/deprecated term 사용 시 issue 생성
- `doc2dic check samples/docs --write-issues`가 issue를 SQLite에 저장
```

### Phase 3. LLM 용어 후보 추출

목표:

```text
- LLM structured output 기반 후보 추출
- 후보 정의, 태그, evidence 저장
- new_term_candidate issue 생성
```

완료 기준:

```text
- 외부 API mock으로 테스트 통과
- 실제 provider 연결은 env로 제어
- JSON schema validation 실패 시 안전하게 재시도 또는 실패 처리
```

### Phase 4. Embedding 기반 유사 Concept 검색

목표:

```text
- concept definition embedding 저장
- candidate definition embedding 저장
- similar concepts top-k 검색
- LLM conflict classifier 입력 구성
```

완료 기준:

```text
- 후보 용어에 대해 유사 concept 목록 반환
- embedding provider 교체 가능
- SQLite vector extension을 통해 top-k 검색 가능
- vector extension 미사용 환경에서는 exact/fuzzy 경로가 유지되고 경고 표시
```

### Phase 5. 충돌 탐지와 리뷰 큐

목표:

```text
- same_term_different_meaning 탐지
- same_meaning_different_term 탐지
- alias_candidate 탐지
- ambiguous_usage 탐지
- 리뷰 액션 처리
```

완료 기준:

```text
- 이슈 승인 시 DB에 concept/variant/relation 반영
- 이슈 반려 시 원본 사전 변경 없음
- 모든 이슈에 evidence 존재
```

### Phase 6. 웹 그래프 시각화

목표:

```text
- 내부 graph projection CLI/API
- Concept/Term/Document/Issue 노드 렌더링
- edge relation 표시
- tag/status/issue filter
```

완료 기준:

```text
- 노드 클릭 시 상세 패널 표시
- issue node에서 review queue로 이동 가능
```

### Phase 7. Graphify export

목표:

```text
- graphify-compatible graph.json export
- glossary_export Markdown corpus export
- graphify CLI subprocess wrapper
- graphify-out 산출물 저장
```

완료 기준:

```text
- graphify-out/graph.json 생성
- graphify-out/graph.html 생성 가능
- graph snapshot 목록에서 선택 가능
- 산출물이 `.doc2dic/graph_snapshots/` 아래 저장
```

### Phase 8. Graphify observation import

목표:

```text
- 기존 문서 폴더를 graphify로 분석
- graphify-out/graph.json import
- 내부 사전과 비교
- review queue issue 생성
```

완료 기준:

```text
- import 결과가 자동 승인되지 않음
- new concept/relation/conflict 후보가 issue로 생성됨
```

---

## 20. 테스트 전략

### 20.1 Backend 테스트

| 테스트 | 대상 |
|---|---|
| unit test | 정규화, fuzzy match, schema validation |
| service test | GlossaryService, ConflictDetector, GraphProjectionService |
| CLI test | init, concept, check, review, search, graph commands |
| API test | `doc2dic serve`의 concepts, documents, issues, graphs routes |
| migration test | SQLite schema migration up/idempotency |
| snapshot test | graph projection JSON |
| provider mock test | LLM/embedding provider 없이 파이프라인 테스트 |

### 20.2 Frontend 테스트

| 테스트 | 대상 |
|---|---|
| component smoke test | 주요 컴포넌트 렌더링 |
| API client test | error/loading handling |
| graph rendering test | nodes/edges 렌더링 |
| review action test | 버튼 클릭 시 API 호출 |
| e2e smoke test | 문서 경로 분석 → 이슈 확인 → 승인 |

### 20.3 샘플 Fixture

`samples/docs/combat_core.md`

```md
# 전투 기본 규칙

스태미나는 회피와 강공격에 소모되는 전투 자원이다.
경직은 피격 직후 짧은 시간 동안 이동과 공격 입력이 제한되는 상태이다.
스턴은 일정 시간 동안 모든 행동이 불가능한 상태이다.
```

`samples/docs/dungeon_draft.md`

```md
# 던전 입장 규칙

스태미나는 던전에 입장할 때 1 소모되며 매일 오전 5시에 회복된다.
입장 피로도가 부족하면 던전에 들어갈 수 없다.
```

예상 이슈:

```json
[
  {
    "issue_type": "same_term_different_meaning",
    "candidate_term": "스태미나",
    "recommendation": "던전 입장 자원은 별도 concept으로 분리하고 preferred term을 피로도 또는 입장 피로도로 검토한다."
  },
  {
    "issue_type": "same_meaning_different_term",
    "candidate_term": "입장 피로도",
    "recommendation": "던전 입장 자원 concept의 preferred term 또는 alias로 검토한다."
  }
]
```

---

## 21. 품질 게이트

모든 PR 또는 agent 작업 완료 시 다음을 확인한다.

```text
CLI/Core:
- ruff 통과
- pytest 통과
- SQLite migration 확인
- `doc2dic --help`, `doc2dic init`, `doc2dic status` smoke 통과
- 외부 API key 없이 mock test 통과

Local Web UI:
- typecheck 통과
- lint 통과
- 주요 화면 smoke test 통과

Graph:
- graph projection snapshot test 통과
- graphify CLI 미설치 환경에서 graceful failure
- graphify output은 generated artifact로 취급

Security:
- API key hardcoding 없음
- .env.example만 커밋
- 분석 문서 원문 노출 범위 확인

Product:
- LLM/graphify 결과 자동 승인 없음
- 모든 issue에 evidence 존재
- 사람이 승인한 변경만 concepts/term_variants에 반영
```

---

## 22. 환경 변수

`.env.example` 초안:

```bash
APP_ENV=development

# Project-local storage
DOC2DIC_HOME=.doc2dic
DOC2DIC_DB_PATH=.doc2dic/glossary.sqlite3
DOC2DIC_CONFIG_PATH=.doc2dic/config.toml
DOC2DIC_VECTOR_EXTENSION=sqlite-vec
DOC2DIC_EMBEDDING_DIMENSION=1536

# LLM provider
LLM_PROVIDER=mock
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Embedding provider
EMBEDDING_PROVIDER=mock
VOYAGE_API_KEY=
EMBEDDING_MODEL=

# Graphify
GRAPHIFY_ENABLED=true
GRAPHIFY_BIN=graphify
GRAPHIFY_OUTPUT_DIR=.doc2dic/graph_snapshots

# Local web UI
DOC2DIC_SERVE_HOST=127.0.0.1
DOC2DIC_SERVE_PORT=8765
VITE_API_BASE_URL=http://127.0.0.1:8765
```

---

## 23. 전역 CLI 설치 구성 초안

기본 설치 경험은 다음 형태를 목표로 한다.

```bash
curl -fsSL https://example.com/doc2dic/install.sh | sh
```

설치 스크립트 책임:

```text
1. `uv` 존재 여부를 확인하고 없으면 안내한다.
2. release wheel 또는 git URL을 `uv tool install`로 설치한다.
3. `doc2dic --help`를 실행해 PATH 연결을 확인한다.
4. sqlite vector extension 의존성을 확인하고, 미충족 시 exact/fuzzy-only 모드 경고를 출력한다.
5. 프로젝트 DB는 만들지 않는다. DB 생성은 사용자가 프로젝트 루트에서 `doc2dic init`을 실행할 때만 한다.
```

개발용 명령:

```bash
scripts/dev-cli.sh      # editable install 후 CLI 실행
scripts/dev-web.sh      # local web UI dev server
scripts/test.sh         # Python + web tests
```

Docker Compose는 기본 개발 경로가 아니다. 외부 DB가 필요한 통합 테스트나 배포형 서버 모드가 생길 때 별도 후속 단계로 추가한다.

---

## 24. Graphify adapter 세부 설계

### 24.1 Export 대상

Graphify export에는 다음 데이터를 포함한다.

```text
Concept nodes:
- id
- label
- definition
- tags
- status
- source_file

Term nodes:
- id
- label
- variant_type
- status

Document nodes:
- id
- title
- path
- document_type

Issue nodes:
- id
- issue_type
- severity
- confidence
- recommendation

Edges:
- preferred_label_of
- alias_of
- forbidden_alias_of
- deprecated_alias_of
- used_in
- conflicts_with
- same_meaning_candidate_of
- different_meaning_candidate_of
- do_not_confuse_with
- related_to
```

### 24.2 Snapshot 저장 구조

```text
.doc2dic/graph_snapshots/
  2026-06-25T120000Z/
    app_graph.json
    graphify_projection.json
    glossary_export/
      concepts/
      variants/
      issues/
    graphify-out/
      graph.json
      graph.html
      GRAPH_REPORT.md
```

### 24.3 Import 정책

Graphify import는 다음 규칙을 따른다.

```text
1. graphify node를 바로 Concept으로 만들지 않는다.
2. graphify edge를 바로 ConceptRelation으로 만들지 않는다.
3. 모든 import 후보는 TermIssue 또는 RelationIssue로 만든다.
4. 중복 후보는 normalized label, source file, relation type으로 deduplicate한다.
5. confidence가 낮거나 근거가 부족하면 ambiguous_usage로 처리한다.
```

---

## 25. LLM 친화적 Context Card

LLM에게 사전을 넘길 때는 전체 DB를 던지지 않고 concept card를 사용한다.

```text
[CONCEPT]
id: combat.stagger
preferred_term: 경직
definition: 피격 직후 짧은 시간 동안 이동, 공격, 스킬 입력이 제한되는 상태
use_when: 짧은 피격 반응을 설명할 때
do_not_confuse_with:
- combat.stun: 더 긴 시간 동안 완전히 행동 불능이 되는 상태
- combat.knockback: 위치가 강제로 밀려나는 효과
tags: combat, status-effect, player-facing
approved_examples:
- 강공격에 맞으면 0.4초 동안 경직된다.
forbidden_terms:
- 멈춤
- 짧은 스턴
```

이 card는 다음 상황에서 사용한다.

```text
- LLM conflict classifier 입력
- 문서 작성 보조 context
- graphify Markdown corpus export
- 사람이 읽는 concept 상세 화면
```

---

## 26. 보안 및 개인정보 원칙

```text
1. 분석 문서는 기본적으로 프로젝트 로컬 SQLite DB와 `.doc2dic/` 스토리지에만 저장한다.
2. 외부 LLM provider에 보낼 텍스트 범위를 chunk 단위로 제한한다.
3. API key는 환경 변수로만 관리한다.
4. 로그에는 원문 문서 전체를 남기지 않는다.
5. evidence quote는 최소한의 문장 범위만 저장한다.
6. graphify 산출물에 민감 문서가 포함될 수 있으므로 export 디렉터리 공개 여부를 명확히 한다.
```

---

## 27. 주요 리스크와 대응

| 리스크 | 설명 | 대응 |
|---|---|---|
| LLM 오판 | 비슷한 용어를 같은 개념으로 잘못 판단할 수 있다. | 모든 결과를 리뷰 큐로 보낸다. |
| embedding 과신 | “스턴”과 “경직”처럼 가까운 용어가 규칙상 다를 수 있다. | embedding은 후보 검색에만 사용한다. |
| graph 복잡도 증가 | occurrence까지 모두 노드화하면 그래프가 복잡해진다. | MVP에서는 concept/term/document/issue 중심으로 제한한다. |
| subagent 파일 충돌 | 병렬 작업 중 같은 파일을 수정할 수 있다. | 파일 소유권 표를 지킨다. |
| graphify 버전 변화 | CLI나 schema가 바뀔 수 있다. | graphify adapter test와 버전 pinning을 둔다. |
| 자동 승인 유혹 | 편의를 위해 AI 결과를 바로 반영하고 싶어질 수 있다. | DB mutation은 review action에서만 허용한다. |
| 문서 포맷 복잡도 | DOCX/PDF 표, 이미지 처리 난도가 높다. | Markdown MVP 후 확장한다. |
| SQLite vector extension 설치 차이 | OS/환경별 extension 로딩 방식이 다를 수 있다. | `VectorStore` adapter, 설치 smoke check, exact/fuzzy-only fallback을 둔다. |
| 프로젝트 DB 파일 충돌 | 여러 프로세스가 동시에 `.doc2dic/glossary.sqlite3`를 쓸 수 있다. | SQLite WAL mode, 짧은 transaction, CLI write lock 안내를 둔다. |

---

## 28. 최종 MVP 완료 기준

MVP는 다음 시나리오가 끝까지 동작하면 완료로 본다.

```text
1. 사용자가 한 번 `curl ... | sh`로 `doc2dic`을 전역 설치한다.
2. 사용자가 게임 프로젝트 루트에서 `doc2dic init`을 실행한다.
3. 시스템이 `.doc2dic/glossary.sqlite3`와 기본 설정을 생성한다.
4. 사용자가 `doc2dic check samples/docs/combat_core.md --write-issues`를 실행한다.
5. 시스템이 스태미나, 경직, 스턴 후보를 추출한다.
6. 사용자가 `doc2dic review` 또는 `doc2dic serve`의 리뷰 큐에서 후보를 승인해 Concept으로 등록한다.
7. 사용자가 `doc2dic check samples/docs/dungeon_draft.md --write-issues`를 실행한다.
8. 시스템이 “스태미나”의 다른 의미 사용 가능성을 issue로 생성한다.
9. 시스템이 “입장 피로도”를 새 concept 또는 alias 후보로 제안한다.
10. 사용자가 리뷰 큐에서 새 concept 생성을 승인한다.
11. `doc2dic concept list`와 웹 용어사전 화면에 두 concept이 분리되어 표시된다.
12. `doc2dic graph export --format graphify`를 실행하면 `.doc2dic/graph_snapshots/.../graphify_projection.json`이 생성된다.
13. graphify export를 실행하면 `.doc2dic/graph_snapshots/.../graphify-out/graph.json`과 `graph.html`이 생성된다.
```

---

## 29. 추천 첫 작업 순서

처음 OpenCode에서 실행할 때는 다음 순서를 권장한다.

```text
1. primary plan agent로 이 IMPLEMENTATION_PLAN.md를 읽고 전체 작업을 요약시킨다.
2. cli-storage와 web-shell을 먼저 실행해 contract와 기본 골격을 만든다.
3. packaging agent가 install.sh, pyproject.toml, .env.example을 구성한다.
4. cli-analysis, cli-graphify, web-glossary, web-review, web-graph를 병렬 실행한다.
5. qa agent가 sample docs와 mock provider 기반 테스트를 만든다.
6. primary build agent가 handoff 파일을 읽고 통합한다.
7. 전체 test/lint/typecheck를 실행한다.
```

최초 프롬프트 예시:

```text
이 저장소의 IMPLEMENTATION_PLAN.md를 읽고 Wave 0부터 진행해줘.
먼저 contracts와 CLI scaffold를 만든 뒤, 파일 소유권에 맞춰 subagent 작업을 병렬로 나눠줘.
기본 저장소는 프로젝트 로컬 `.doc2dic/glossary.sqlite3`와 SQLite vector extension으로 구성해줘.
subagent는 다른 subagent를 호출하지 않게 하고, 각 작업이 끝나면 handoff 파일을 남기게 해줘.
```

---

## 30. 참고 자료

- OpenCode Agents: https://opencode.ai/docs/agents/
- OpenCode Config: https://opencode.ai/docs/config/
- OpenCode Agent Skills: https://opencode.ai/docs/skills/
- Graphify GitHub Repository: https://github.com/safishamsi/graphify
- Graphify Architecture: https://github.com/safishamsi/graphify/blob/v8/ARCHITECTURE.md
- sqlite-vec: https://github.com/asg017/sqlite-vec
- React Flow: https://reactflow.dev/
- Cytoscape.js: https://js.cytoscape.org/

---

## 31. 한 줄 정리

본 프로젝트는 **프로젝트 로컬 SQLite 기반 Concept 중심 용어사전**을 원본으로 두고, **전역 `doc2dic` CLI로 모든 프로젝트에서 사용하며, LLM과 embedding은 후보 탐색에 사용하고, Graphify는 graph projection과 관찰 그래프 분석에 활용하며, 모든 변경은 리뷰 큐를 통해 사람이 승인하는 구조**로 구현한다.
