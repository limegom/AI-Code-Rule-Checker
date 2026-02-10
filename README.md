# [서강대학교 러너톤] AI Code Rule Checker (발전 버전: Agentic)

많은 인원이 같이 코딩할 때, 팀마다 규칙이 생긴다.  
규칙을 모두 기억하고 지키기 어렵다는 문제를 해결하기 위해, AI가 팀의 코딩 규칙을 대신 기억하여 틀리면 알려주고 고쳐주는 것을 목표로 한다.

- 팀 이름: 0001
- 구성원: 김종원
- 작성일: 2026-01-30
- 기술 스택: Python FastAPI, LangChain Tool Calling Agent, OpenAI Chat model

## 무엇이 발전했나

교안의 핵심 개념을 프로젝트에 직접 반영한다. fileciteturn0file0

1) Tool Calling Agent
- 사용자의 입력을 보고 에이전트가 스스로 도구를 선택한다.
- 예: 규칙 질문 → list_rules/search_rules, 코드 검사 → check_code, 규칙 추가 → add_rule

2) AgentExecutor 제어
- max_iterations / max_execution_time / handle_parsing_errors로 루프 안전성을 확보한다.

3) 메모리(멀티턴)
- RunnableWithMessageHistory로 session_id별 대화 문맥을 자동 주입한다.

4) Agentic RAG(규칙 검색)
- rules.json을 벡터 인덱스(Chroma)로 구축하고, search_rules 도구로 유사 규칙을 검색한다.

## 기능(MVP+)

### A. 단일 엔드포인트 에이전트
- `POST /agent`에 자연어 또는 코드를 넣으면 에이전트가 작업을 선택한다.

### B. 코드 규칙 점검(deterministic)
- `POST /check`는 deterministic checker만으로 동작한다.
- 현재 포함 규칙(예시):
  - PY-IMPORT-ALPHA: 상단 import 알파벳 정렬(자동 수정)
  - PY-NO-TRAILING-WS: 라인 끝 공백 제거(자동 수정)
  - PY-NO-WILDCARD-IMPORT: wildcard import 금지
  - PY-LINE-LENGTH-88: 라인 길이 88자 권장

### C. 규칙 관리
- `GET /rules`: rules.json 조회
- `POST /rules`: 간단 규칙 추가(또는 에이전트에게 "규칙 추가해줘" 요청)

## 실행

### 1) 설치

```bash
pip install -r requirements.txt
cp .env.example .env
# .env에 OPENAI_API_KEY 설정
```

### 2) FastAPI 실행

```bash
uvicorn app:app --reload
```

- 헬스체크: `GET /health`

## API 예시

### 1) 에이전트

```bash
curl -X POST http://127.0.0.1:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","input":"팀 내 규칙을 알려줘"}'
```

```bash
curl -X POST http://127.0.0.1:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","input":"from b import x\nfrom a import y\nprint(1)\n"}'
```

### 2) 코드 점검(REST)

```bash
curl -X POST http://127.0.0.1:8000/check \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"demo",
    "language":"python",
    "auto_fix": true,
    "include_diff": true,
    "code":"from b import x\nfrom a import y\nprint(1)\n"
  }'
```

## 운영 관점에서 남은 고민

- DB 선택: rules/history를 SQLite/PostgreSQL로 이관
- IDE 연동: pre-commit hook / GitHub Action / PR comment bot / VSCode extension
- 규칙 확장: AST 기반 checker(예: unused import, naming convention) 도입

## 브라우저 UI

서버 실행 후 아래 주소로 접속하면 챗봇 형태의 프론트엔드를 사용할 수 있다.

- http://127.0.0.1:8000/

대화 탭: `/agent` 사용
코드 검사 탭: `/check` 사용
