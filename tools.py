from __future__ import annotations

import json
import re
import difflib
from pathlib import Path
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field
from langchain.tools import tool

from rule_store import RuleStore
from rule_engine import (
    check_import_alphabetical,
    check_no_wildcard_import,
    fix_trailing_whitespace,
    check_line_length,
)
from schemas import RuleCheckResult, Violation
from vectorstore import rebuild_rules_index, search_rules


def _slug_id(prefix: str, title: str) -> str:
    # PY-RULE-XXXX 형태로, title 기반 slug + 짧은 해시
    s = re.sub(r"[^A-Za-z0-9]+", "-", title.strip().upper()).strip("-")
    if not s:
        s = "RULE"
    short = f"{abs(hash(title)) % 10000:04d}"
    return f"{prefix}-{s[:20]}-{short}"


class ListRulesInput(BaseModel):
    """입력 없음(더미)."""
    dummy: Optional[str] = None


class AddRuleInput(BaseModel):
    language: str = Field("python", description="언어(MVP는 python)")
    title: str = Field(..., description="규칙 제목")
    description: str = Field(..., description="규칙 설명")
    auto_fix: bool = Field(False, description="자동 수정 가능 여부(메타 정보)")


class RebuildIndexInput(BaseModel):
    """입력 없음(더미)."""
    dummy: Optional[str] = None


class SearchRulesInput(BaseModel):
    query: str = Field(..., description="검색 질의")
    k: int = Field(5, ge=1, le=10, description="검색 결과 개수")


class CheckCodeInput(BaseModel):
    language: str = Field("python", description="언어(MVP는 python)")
    code: str = Field(..., description="검사할 코드")
    auto_fix: bool = Field(True, description="가능하면 자동 수정도 수행")
    include_diff: bool = Field(True, description="수정이 발생하면 unified diff 포함")


def build_tools(rule_store: RuleStore):
    """
    RuleStore 인스턴스를 클로저로 캡처하여 도구들을 생성한다.
    """

    @tool("list_rules", args_schema=ListRulesInput)
    def list_rules_tool(dummy: Optional[str] = None) -> str:
        """팀 규칙 목록을 반환한다."""
        rules = rule_store.list_rules()
        if not rules:
            return "등록된 규칙이 없다."
        lines = []
        for r in rules:
            lines.append(f"- [{r.get('id')}] ({r.get('language')}) {r.get('title')}: {r.get('description')}")
        return "\n".join(lines)

    @tool("add_rule", args_schema=AddRuleInput)
    def add_rule_tool(language: str, title: str, description: str, auto_fix: bool = False) -> str:
        """새 규칙을 rules.json에 추가한다. id는 자동 생성한다."""
        rid = _slug_id("PY" if language.lower() == "python" else "RULE", title)
        rule = {
            "id": rid,
            "language": language.lower(),
            "title": title,
            "description": description,
            "auto_fix": bool(auto_fix),
        }
        rule_store.add_rule(rule)
        return json.dumps({"added": True, "rule": rule}, ensure_ascii=False)

    @tool("rebuild_rules_index", args_schema=RebuildIndexInput)
    def rebuild_rules_index_tool(dummy: Optional[str] = None) -> str:
        """rules.json 기반으로 벡터 인덱스를 재구축한다(Agentic RAG용)."""
        n = rebuild_rules_index(rule_store.list_rules())
        return json.dumps({"indexed_rules": n}, ensure_ascii=False)

    @tool("search_rules", args_schema=SearchRulesInput)
    def search_rules_tool(query: str, k: int = 5) -> str:
        """규칙을 벡터 검색으로 찾아 요약을 반환한다."""
        hits = search_rules(query, k=k)
        # 너무 길지 않게 상위 결과만 반환
        return json.dumps({"hits": hits}, ensure_ascii=False)

    @tool("check_code", args_schema=CheckCodeInput)
    def check_code_tool(language: str, code: str, auto_fix: bool = True, include_diff: bool = True) -> str:
        """코드가 팀 규칙을 위반하는지 검사하고, 가능한 경우 자동 수정 결과를 포함한다."""
        if language.lower() != "python":
            res = RuleCheckResult(ok=True, summary="MVP는 python만 지원한다.", notes="다른 언어는 확인되지 않음")
            return res.model_dump_json(ensure_ascii=False)

        original = code
        violations: List[Violation] = []
        fixed_code: Optional[str] = None

        # 1) import 알파벳 정렬(수정 가능)
        vios1, fixed1 = check_import_alphabetical(code)
        for v in vios1:
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
        if auto_fix and fixed1:
            code = fixed1
            fixed_code = code

        # 2) trailing whitespace (수정 가능)
        vios2, fixed2 = fix_trailing_whitespace(code)
        for v in vios2:
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
        if auto_fix and fixed2:
            code = fixed2
            fixed_code = code

        # 3) wildcard import (검사만)
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

        # 4) line length (검사만)
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
        if include_diff and fixed_code and fixed_code != original:
            diff = difflib.unified_diff(
                original.splitlines(True),
                fixed_code.splitlines(True),
                fromfile="before.py",
                tofile="after.py",
            )
            unified_diff = "".join(diff)

        res = RuleCheckResult(
            ok=ok,
            summary=summary,
            violations=violations,
            fixed_code=fixed_code if (auto_fix and fixed_code) else None,
            unified_diff=unified_diff,
            notes="deterministic checker 중심이며, 복잡한 규칙은 확인되지 않음",
        )
        return res.model_dump_json(ensure_ascii=False)

    return [list_rules_tool, add_rule_tool, rebuild_rules_index_tool, search_rules_tool, check_code_tool]
