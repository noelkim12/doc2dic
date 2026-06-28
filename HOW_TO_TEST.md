# Doc2Dic OpenCode 테스트 방법

이 문서는 현재 로컬 저장소의 Doc2Dic을 OpenCode에서 MCP로 연결해 실제로 동작하는지 확인하는 절차만 다룹니다.

## 1. 사전 준비

저장소 루트에서 개발 의존성을 준비합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
uv sync
```

`doc2dic` 콘솔 명령이 실행되는지 확인합니다.

```bash
uv run doc2dic --help
```

## 2. 테스트용 프로젝트 만들기

OpenCode에서 확인할 임시 프로젝트를 하나 만듭니다.

```bash
tmpdir="$(mktemp -d)"
cd "$tmpdir"
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic init
```

초기화가 끝나면 아래 파일이 생겨야 합니다.

```text
.doc2dic/config.toml
.doc2dic/glossary.sqlite3
```

상태 확인도 실행합니다.

```bash
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic status
```

## 3. 샘플 문서로 로컬 데이터 만들기

외부 API 키 없이 mock provider로 샘플 문서를 점검합니다.

```bash
DOC2DIC_LLM_PROVIDER=mock \
DOC2DIC_EMBEDDING_PROVIDER=mock \
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic check \
  /home/noel/projects/personal/doc2dic-workspace/doc2dic/samples/docs/dungeon_draft.md \
  --write-issues
```

리뷰 큐가 조회되는지 확인합니다.

```bash
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic review list
```

## 4. 선택: Voyage embedding 경로 확인

기본 `uv sync`, mock provider 테스트, `scripts/test.sh`, OpenCode MCP 확인 흐름은 live Voyage API key나 네트워크를 요구하지 않습니다. 이 절차는 Voyage embedding adapter와 CLI 연결을 별도로 확인하고 싶을 때만 실행하는 선택 흐름입니다.

### 4.1 Adapter live smoke는 명시적으로 opt-in

저장소 루트에서 live smoke를 직접 실행하려면 opt-in 환경변수와 지원되는 key source를 함께 제공합니다. 아래 예시는 placeholder만 사용합니다.

```bash
cd /home/noel/projects/personal/doc2dic-workspace/doc2dic
VOYAGE_API_KEY="<VOYAGE_API_KEY>" \
DOC2DIC_RUN_LIVE_VOYAGE_TESTS=1 \
/home/noel/.local/bin/python -m pytest tests/integration/test_voyage_smoke.py::test_live_voyage_smoke_gate -q -s
```

`DOC2DIC_RUN_LIVE_VOYAGE_TESTS=1`이 없으면 기본 결과는 skip이며, skip reason은 `reason=opt_in_required`입니다. Opt-in했지만 key가 없으면 live request를 보내지 않고 key 없음으로 skip됩니다.

Credential precedence는 다음 순서입니다.

1. `VOYAGE_API_KEY`
2. `DOC2DIC_EMBEDDING_API_KEY`
3. `DOC2DIC_AUTH_FILE` 또는 기본 auth 파일의 Voyage embedding key

### 4.2 임시 프로젝트에서 CLI 경로 확인

이미 만든 `$tmpdir`에서 provider와 model을 설정한 뒤, LLM은 mock으로 고정하고 embedding만 Voyage로 확인합니다. API key는 환경변수 placeholder로 주거나, `doc2dic config embedding use voyage --model voyage-4-large --prompt-api-key`로 사용자 전역 auth 파일에 저장한 뒤 사용할 수 있습니다.

```bash
cd "$tmpdir"
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic config embedding use voyage --model voyage-4-large

VOYAGE_API_KEY="<VOYAGE_API_KEY>" \
DOC2DIC_LLM_PROVIDER=mock \
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic analyze \
  /home/noel/projects/personal/doc2dic-workspace/doc2dic/samples/docs/dungeon_draft.md
```

`check` 경로를 확인하려면 같은 환경에서 `doc2dic check ... --write-issues`를 실행합니다. 이때도 발견 사항은 리뷰 큐 후보로 들어가며 용어집을 바로 수정하지 않습니다.

성공 신호는 CLI 출력에 `Provider`, `Candidates`, `Vector candidates enabled` 같은 항목이 보이는 것입니다. 로컬에 sqlite-vec가 없거나 로드되지 않으면 Voyage adapter live smoke가 성공해도 semantic vector candidates는 disabled 상태로 남을 수 있습니다.

`.doc2dic/glossary.sqlite3`에는 embedding provider와 model 같은 설정만 저장되고 raw API key는 저장되지 않습니다. `.doc2dic/config.toml`, evidence, handoff 파일에도 raw key를 기록하지 마세요.

## 5. MCP 서버 단독 확인

OpenCode에 연결하기 전에 MCP 서버가 대상 프로젝트를 받는지 확인합니다.

```bash
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  doc2dic serve --mcp --path "$tmpdir"
```

이 명령은 stdio 서버를 계속 실행하므로, 프로세스가 시작되고 즉시 에러가 나지 않으면 `Ctrl+C`로 종료합니다.

## 6. OpenCode 로컬 설정에 연결

테스트용 프로젝트 디렉터리에서 OpenCode 설정을 생성하거나 갱신합니다.

```bash
cd "$tmpdir"
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic install --local --target opencode
```

생성된 설정 파일을 확인합니다.

```bash
cat opencode.jsonc
```

`mcp.doc2dic` 항목이 있고, command가 다음 형태를 포함하면 됩니다.

```text
uv --directory /home/noel/projects/personal/doc2dic-workspace/doc2dic run doc2dic serve --mcp --path <테스트용 프로젝트 경로>
```

## 7. OpenCode에서 확인

테스트용 프로젝트 디렉터리에서 OpenCode를 다시 시작합니다.

```bash
cd "$tmpdir"
opencode
```

새 세션에서 아래처럼 요청해 MCP 도구가 실제 프로젝트 용어집을 읽는지 확인합니다.

```text
doc2dic으로 dungeon_draft 문서와 관련된 용어 컨텍스트를 찾아줘.
```

성공 기준은 다음과 같습니다.

- OpenCode가 `doc2dic_explore` MCP 도구를 사용할 수 있습니다.
- 응답에 테스트용 프로젝트의 Doc2Dic 상태나 용어 컨텍스트가 포함됩니다.
- missing project나 missing index가 나오지 않습니다.
- 용어집이 자동으로 수정되지 않고, 수정 후보는 리뷰 큐 기준으로만 설명됩니다.

## 8. 제거

테스트가 끝나면 테스트용 프로젝트의 OpenCode 설정에서 Doc2Dic MCP 항목만 제거합니다.

```bash
cd "$tmpdir"
uv run \
  --project /home/noel/projects/personal/doc2dic-workspace/doc2dic \
  --directory "$tmpdir" \
  doc2dic uninstall --local --target opencode
```

임시 프로젝트까지 지우려면 다음을 실행합니다.

```bash
rm -rf "$tmpdir"
```

## 빠른 점검 체크리스트

- `uv run doc2dic --help`가 성공한다.
- 테스트용 프로젝트에 `.doc2dic/glossary.sqlite3`가 생성된다.
- mock provider로 `check --write-issues`가 성공한다.
- 선택 Voyage 확인은 `DOC2DIC_RUN_LIVE_VOYAGE_TESTS=1`과 placeholder key source를 명시한 경우에만 실행한다.
- Voyage CLI 확인에서 `voyage-4-large` provider/model 설정은 저장되지만 raw API key는 프로젝트 SQLite에 저장되지 않는다.
- `doc2dic serve --mcp --path <project>`가 즉시 실패하지 않는다.
- `doc2dic install --local --target opencode` 후 `opencode.jsonc`에 `mcp.doc2dic`이 생긴다.
- OpenCode 재시작 후 `doc2dic_explore`를 통해 용어 컨텍스트를 조회할 수 있다.
- `doc2dic uninstall --local --target opencode`가 `mcp.doc2dic`만 제거한다.
