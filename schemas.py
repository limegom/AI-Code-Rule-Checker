from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any


class Violation(BaseModel):
    rule_id: str = Field(..., description="위반한 규칙 ID")
    title: str = Field(..., description="규칙 제목")
    severity: Literal["info", "warning", "error"] = Field("warning", description="위반 심각도")
    message: str = Field(..., description="위반 설명")
    start_line: Optional[int] = Field(None, description="위반 시작 라인(1-indexed)")
    end_line: Optional[int] = Field(None, description="위반 종료 라인(1-indexed)")
    suggestion: Optional[str] = Field(None, description="수정 제안")


class RuleCheckResult(BaseModel):
    ok: bool = Field(..., description="규칙 위반이 없으면 True")
    summary: str = Field(..., description="요약")
    violations: List[Violation] = Field(default_factory=list, description="위반 목록")
    fixed_code: Optional[str] = Field(None, description="auto_fix가 True일 때 수정된 코드(가능하면 제공)")
    unified_diff: Optional[str] = Field(None, description="원본과 수정본의 unified diff(가능하면 제공)")
    notes: Optional[str] = Field(None, description="추가 메모(한계, 판단 근거 등)")


class AgentResponse(BaseModel):
    """
    단일 엔드포인트(/agent)에서 반환되는 응답 스키마.
    """
    output: str = Field(..., description="에이전트 최종 응답")
    tool_summary: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="debug=True인 경우, 어떤 도구가 호출되었는지 요약",
    )
