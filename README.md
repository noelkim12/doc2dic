# Doc2Dic

Doc2Dic은 용어집을 기준으로 기획 문서의 용어 일관성을 점검하는 도구입니다. Markdown과 TXT 기획 문서를 로컬 용어집과 비교하고, 발견한 수정 후보는 사람이 확인하는 리뷰 큐로 보냅니다.

MVP의 기준 데이터는 프로젝트 안의 `.doc2dic/glossary.sqlite3` 하나뿐입니다. 개념, 용어 변형, 리뷰 이슈는 이 SQLite 데이터베이스를 기준으로 관리됩니다. 그래프 파일, Graphify 내보내기 결과, 에이전트 배너는 모두 여기서 파생된 결과이며 직접 기준 데이터가 되지 않습니다.

핵심 명령은 외부 API 키 없이 mock provider로 실행할 수 있습니다. sqlite-vec, Graphify 바이너리, 공개 설치 서버는 없어도 기본 점검 흐름은 동작합니다.

## 현재 구현된 기능

| 영역 | 상태 | 설명 |
| --- | --- | --- |
| 개발 모드 패키지 설치와 `doc2dic` 콘솔 명령 | Current | 로컬에서 편집 가능 설치 후 CLI를 실행합니다. |
| `init`, `status`, `concept`, `variant`, `review`, `check`, `analyze`, `graph`, `serve` 명령 그룹 | Current | CLI 명령 그룹이 제공됩니다. |
| 프로젝트 로컬 SQLite 용어집 | Current | `.doc2dic/glossary.sqlite3`가 유일한 기준 데이터입니다. |
| Markdown과 TXT 문서 점검 | Current | mock provider로 결정적 점검과 분석을 실행합니다. |
| 리뷰 큐 | Current | accept, dismiss, alias, forbidden-term, relation 조치를 트랜잭션으로 처리합니다. |
| 그래프 projection | Current | 현재 용어집에서 파생 그래프를 만들고 조회합니다. |
| Graphify 호환 내보내기 | Current | Graphify용 projection 파일과 Markdown corpus를 씁니다. |
| 로컬 API와 웹 모듈 | Current | 앱 모듈에는 구현되어 있지만 `doc2dic serve` 단독 웹 서빙은 아직 아닙니다. |
| MCP stdio 서버 | Current | `doc2dic serve --mcp`로 OpenCode 같은 도구에 연결합니다. |
| OpenCode 로컬 설치와 제거 | Current | 로컬 설정의 `mcp.doc2dic` 항목만 관리합니다. |
| sqlite-vec 기반 검색 | Conditional | 없어도 정확 검색과 fuzzy 흐름은 계속 동작합니다. |
| Graphify 런타임 실행 | Conditional | Graphify 바이너리 없이도 export-only 흐름은 동작합니다. |
| 공개 `curl | sh` 설치 | Conditional | 패키징과 공개 호스팅이 준비된 뒤에만 가능합니다. |

## MVP 범위와 비범위

MVP 범위는 로컬 CLI, 로컬 용어집, Markdown과 TXT 문서 점검, 리뷰 큐, 파생 그래프, Graphify 호환 내보내기, MCP stdio 연결, OpenCode 로컬 설정 연결입니다.

DOCX, PDF, Google Docs, Notion, Confluence 가져오기는 post-MVP입니다. 현재 README는 이 가져오기들이 구현되었다고 주장하지 않습니다.

Graphify 연동은 현재 export-only입니다. `doc2dic graph export --format graphify`는 파생 projection과 Markdown corpus를 생성합니다. Graphify observation import는 post-MVP이며, Graphify 출력은 `.doc2dic/glossary.sqlite3`를 직접 바꾸면 안 됩니다. 용어집 변경은 리뷰 큐를 거쳐야 합니다.

`doc2dic serve --mcp`는 현재 기능입니다. 인자 없는 `doc2dic serve`로 웹을 서빙하는 흐름은 planned MVP입니다. 공개 원격 `curl`과 `sh` 조합 설치도 현재 기능이 아니라, 패키징과 호스팅이 갖춰졌을 때의 조건부 경로입니다.

## 설치 방법

저장소 루트에서 개발 모드로 설치합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
/home/noel/.local/bin/python -m pip install -e ".[dev]"
doc2dic --help
```

## 프로젝트 초기화와 상태 확인

Doc2Dic을 적용할 프로젝트 폴더에서 초기화합니다.

```bash
cd <project>
doc2dic init
doc2dic status
```

`doc2dic init`은 `.doc2dic/config.toml`과 `.doc2dic/glossary.sqlite3`를 만듭니다. `doc2dic status`는 프로젝트, 데이터베이스, 벡터 검색, Graphify 사용 가능 상태를 보여줍니다.

MCP 서버나 에이전트 컨텍스트에서 missing index, degraded index, missing project 메시지가 나오면 일반 저장소 검색은 계속 쓸 수 있습니다. 다만 `doc2dic init`, 인덱스 재생성, 용어집 변경은 사람이 의도를 확인한 뒤 실행해야 합니다.

## mock provider로 Markdown과 TXT 점검

mock provider를 쓰면 외부 LLM API 키나 임베딩 API 키 없이 핵심 명령을 실행할 수 있습니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
tmpdir="$(mktemp -d)"
cd "$tmpdir"
doc2dic init
DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock doc2dic check /home/noel/projects/personal/doc2dic-workspace/doc2dic/samples/docs/dungeon_draft.md --write-issues
DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock doc2dic analyze /home/noel/projects/personal/doc2dic-workspace/doc2dic/samples/docs/dungeon_draft.md
```

`check --write-issues`는 발견한 문제를 리뷰 큐에 기록합니다. `analyze`는 후보 용어와 충돌 가능성을 분석합니다. 두 명령 모두 용어집을 바로 수정하지 않습니다.

## review queue 처리

대기 중인 리뷰 이슈를 확인합니다.

```bash
doc2dic review list
```

리뷰 큐에서 accept, dismiss, alias, forbidden-term, relation 같은 조치를 선택해야 변경이 `.doc2dic/glossary.sqlite3`에 반영됩니다. 사람이 승인하기 전까지 Doc2Dic은 용어집을 자동으로 고치지 않습니다.

## graph current, export, Graphify 경계

현재 용어집에서 파생된 그래프를 확인합니다.

```bash
doc2dic graph current --json
```

Graphify 호환 파일을 내보냅니다.

```bash
doc2dic graph export --format graphify
```

내보낸 파일은 `.doc2dic/graph_snapshots/` 아래에 생성됩니다. 이 결과는 파생물입니다. Graphify 결과를 다시 가져와 용어집을 자동 변경하는 기능은 post-MVP이며, Graphify 출력은 용어집을 직접 변경할 수 없습니다.

## MCP 서버 실행

OpenCode 같은 MCP 클라이언트에서 프로젝트 용어집을 읽으려면 stdio 서버를 실행합니다.

```bash
doc2dic serve --mcp --path <project>
```

현재 폴더를 대상으로 실행할 때는 `--path`를 생략할 수 있습니다.

```bash
cd <project>
doc2dic serve --mcp
```

MCP 서버도 같은 `.doc2dic/glossary.sqlite3`를 읽습니다. stale banner는 문서가 pending, stale, missing 상태일 수 있음을 알려주는 참고 알림입니다. 이 배너는 용어집 변경 승인도 아니고, 리뷰 큐 결정을 대체하지도 않습니다.

## OpenCode 로컬 설치와 제거

OpenCode 설정에 Doc2Dic MCP 항목을 로컬로 연결합니다.

```bash
doc2dic install --local --target opencode
```

제거할 때는 같은 로컬 항목만 삭제합니다.

```bash
doc2dic uninstall --local --target opencode
```

설치 명령은 로컬 설정의 `mcp.doc2dic` 항목만 쓰거나 갱신합니다. 제거 명령도 그 항목만 지웁니다. 공개 호스팅 기반 `curl`과 `sh` 조합 설치는 현재 구현으로 주장하지 않습니다.

## 빠른 smoke 흐름

아래 명령은 임시 프로젝트를 만들고, mock provider로 점검과 분석을 실행한 뒤, 리뷰 큐와 그래프 export까지 확인합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
/home/noel/.local/bin/python -m pip install -e ".[dev]"
tmpdir="$(mktemp -d)"
cd "$tmpdir"
doc2dic init
doc2dic status
DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock doc2dic check /home/noel/projects/personal/doc2dic-workspace/doc2dic/samples/docs/dungeon_draft.md --write-issues
DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock doc2dic analyze /home/noel/projects/personal/doc2dic-workspace/doc2dic/samples/docs/dungeon_draft.md
doc2dic review list
doc2dic graph current --json
doc2dic graph export --format graphify
```

## 명령 상태 표

| 명령 | 상태 | 설명 |
| --- | --- | --- |
| `doc2dic --help` | Current | 사용 가능한 명령 그룹을 보여줍니다. |
| `doc2dic init` | Current | `.doc2dic/config.toml`과 `.doc2dic/glossary.sqlite3`를 만듭니다. |
| `doc2dic status` | Current | 프로젝트, 데이터베이스, 벡터, Graphify 상태를 보고합니다. |
| `doc2dic concept list` | Current | 로컬 저장소의 용어집 개념을 나열합니다. |
| `doc2dic variant add` | Current | 기존 개념에 용어 변형을 추가합니다. |
| `doc2dic review list` | Current | 사람이 처리해야 할 리뷰 이슈를 나열합니다. |
| `doc2dic check samples/docs/dungeon_draft.md --write-issues` | Current | mock provider 선택 시 결정적 문서 점검을 실행합니다. |
| `doc2dic analyze samples/docs/dungeon_draft.md` | Current | 후보 추출과 충돌 분석을 실행합니다. |
| `doc2dic graph current --json` | Current | 현재 파생 그래프 projection을 JSON으로 출력합니다. |
| `doc2dic graph export --format graphify` | Current | Graphify 호환 projection 파일을 씁니다. Graphify 런타임 실행은 조건부입니다. |
| `doc2dic serve --help` | Current | serve 명령 도움말을 보여줍니다. 현재 구현된 런타임 경로는 MCP stdio입니다. |
| `doc2dic serve --mcp` | Current | 현재 프로젝트용 MCP stdio 서버를 시작합니다. 다른 repo에 연결할 때는 `--path <project>`를 씁니다. |
| `doc2dic serve --mcp --path <project>` | Current | 지정한 프로젝트의 MCP stdio 서버를 시작합니다. |
| `doc2dic install --local --target opencode` | Current | OpenCode 로컬 설정에 `mcp.doc2dic` 항목을 쓰거나 갱신합니다. |
| `doc2dic uninstall --local --target opencode` | Current | OpenCode 로컬 설정에서 `mcp.doc2dic` 항목만 제거합니다. |
| `doc2dic install --help` | Current | 로컬 에이전트 설치 옵션을 보여줍니다. 현재 구현 대상은 `--local --target opencode`입니다. |
| `doc2dic uninstall --help` | Current | 로컬 에이전트 제거 옵션을 보여줍니다. 현재 구현 대상은 `--local --target opencode`입니다. |
| `doc2dic serve` | Planned MVP | 이 명령으로 웹을 직접 서빙하는 흐름은 아직 구현되지 않았습니다. |
| `curl ... \| sh` | Conditional | 공개 패키징과 호스팅이 추가된 뒤 가능한 원격 설치 경로입니다. |
| `doc2dic graph import graphify-out/graph.json` | Post-MVP | 예시일 뿐입니다. Graphify observation import는 구현되지 않았습니다. |

## 로컬 검증 명령

README나 문서 명령 표를 바꾼 뒤에는 문서 명령 일관성 테스트를 실행합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
/home/noel/.local/bin/python -m pytest tests/docs/test_docs_commands.py -q
```

임시 프로젝트 quickstart를 다시 확인하려면 smoke gate를 실행합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
scripts/test.sh --smoke
```

소유권 문서를 바꾼 경우에만 아래 테스트를 실행합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
/home/noel/.local/bin/python -m pytest tests/contracts/test_agent_ownership_docs.py -q
```

## 관련 문서

1. `docs/architecture.md`: MVP 아키텍처와 신뢰 경계를 설명합니다.
2. `docs/data-model.md`: 용어집, 리뷰, 문서, 그래프 데이터 형태를 설명합니다.
3. `docs/opencode-workflow.md`: 이 저장소의 에이전트 소유권 흐름을 설명합니다.
4. `docs/graphify-integration.md`: Graphify 내보내기 경계와 연동 흐름을 설명합니다.
5. `docs/post-mvp.md`: 뒤로 미룬 통합과 비범위를 정리합니다.
