from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Literal, Any, Dict, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from rule_store import RuleStore
from schemas import RuleCheckResult, AgentResponse
from rule_engine import (
    check_import_alphabetical,
    check_no_wildcard_import,
    fix_trailing_whitespace,
    check_line_length,
)
from schemas import Violation
from agent import build_agent


load_dotenv()

app = FastAPI(title="[Sogang Runnerthon] AI Code Rule Checker (Agentic)")

# Frontend (static)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def ui_root():
    return FileResponse("static/index.html")


RULES_PATH = Path("rules/rules.json")
rule_store = RuleStore(RULES_PATH)
agent_with_history = build_agent(rule_store)


class AgentRequest(BaseModel):
    session_id: str = Field(..., description="세션 식별자")
    input: str = Field(..., description="사용자 입력(자연어/코드 포함)")
    debug: bool = Field(False, description="도구 호출 요약 포함 여부")


class CheckRequest(BaseModel):
    session_id: str = Field(..., description="세션 식별자")
    language: Literal["python"] = Field("python", description="언어(MVP는 python)")
    code: str = Field(..., description="검사할 코드")
    auto_fix: bool = Field(True, description="가능하면 자동 수정 코드도 제공")
    include_diff: bool = Field(True, description="가능하면 unified diff 제공")


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/rules")
def list_rules():
    return {"team_name": rule_store.team_name(), "members": rule_store.members(), "rules": rule_store.list_rules()}


class AddRuleRequest(BaseModel):
    language: str = Field("python")
    title: str
    description: str
    auto_fix: bool = False


@app.post("/rules")
def add_rule(req: AddRuleRequest):
    # 단순 API 추가(에이전트 도구(add_rule)와 동일 목적)
    rid = f"RULE-{abs(hash(req.title)) % 10000:04d}"
    rule = {
        "id": rid,
        "language": req.language.lower(),
        "title": req.title,
        "description": req.description,
        "auto_fix": bool(req.auto_fix),
    }
    rule_store.add_rule(rule)
    return {"added": True, "rule": rule}


@app.post("/check", response_model=RuleCheckResult)
def check(req: CheckRequest):
    # deterministic checker만으로도 동작하는 REST 엔드포인트 유지
    original = req.code
    code = req.code
    violations: List[Violation] = []
    fixed_code: Optional[str] = None

    v1, f1 = check_import_alphabetical(code)
    for v in v1:
        violations.append(
            Violation(
                rule_id=v.rule_id,
                title=v.title,
                severity="warning",
                message=v.message,
                start_line=v.start_line,
                end_line=v.end_line,
                suggestion=v.suggestion,
            )
        )
    if req.auto_fix and f1:
        code = f1
        fixed_code = code

    v2, f2 = fix_trailing_whitespace(code)
    for v in v2:
        violations.append(
            Violation(
                rule_id=v.rule_id,
                title=v.title,
                severity="warning",
                message=v.message,
                start_line=v.start_line,
                end_line=v.end_line,
                suggestion=v.suggestion,
            )
        )
    if req.auto_fix and f2:
        code = f2
        fixed_code = code

    for v in check_no_wildcard_import(code):
        violations.append(
            Violation(
                rule_id=v.rule_id,
                title=v.title,
                severity="error",
                message=v.message,
                start_line=v.start_line,
                end_line=v.end_line,
                suggestion=v.suggestion,
            )
        )

    for v in check_line_length(code, limit=88):
        violations.append(
            Violation(
                rule_id=v.rule_id,
                title=v.title,
                severity="info",
                message=v.message,
                start_line=v.start_line,
                end_line=v.end_line,
                suggestion=v.suggestion,
            )
        )

    ok = (len(violations) == 0)
    summary = "규칙 위반이 없다." if ok else f"규칙 위반 {len(violations)}건이 발견되었다."

    unified_diff = None
    if req.include_diff and fixed_code and fixed_code != original:
        import difflib
        diff = difflib.unified_diff(
            original.splitlines(True),
            fixed_code.splitlines(True),
            fromfile="before.py",
            tofile="after.py",
        )
        unified_diff = "".join(diff)

    return RuleCheckResult(
        ok=ok,
        summary=summary,
        violations=violations,
        fixed_code=fixed_code if (req.auto_fix and fixed_code) else None,
        unified_diff=unified_diff,
        notes="deterministic checker만 사용한다.",
    )


@app.post("/agent", response_model=AgentResponse)
def agent(req: AgentRequest):
    """
    단일 입력으로:
    - 규칙 설명/검색
    - 코드 검사/수정
    - 규칙 추가
    등을 에이전트가 판단하여 수행한다.
    """
    # AgentExecutor는 dict 반환: {"output": "...", ...}
    result = agent_with_history.invoke(
        {"input": req.input},
        config={"configurable": {"session_id": req.session_id}},
    )

    output = result.get("output", str(result))

    # debug: intermediate_steps를 노출하면 너무 길어질 수 있으므로 요약만 제공
    tool_summary = None
    if req.debug:
        steps = result.get("intermediate_steps", [])
        summarized = []
        for action, observation in steps:
            summarized.append(
                {
                    "tool": getattr(action, "tool", None),
                    "tool_input": getattr(action, "tool_input", None),
                    "observation_preview": str(observation)[:300],
                }
            )
        tool_summary = summarized

    return AgentResponse(output=output, tool_summary=tool_summary)
