from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import re


@dataclass(frozen=True)
class SimpleViolation:
    rule_id: str
    title: str
    message: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    suggestion: Optional[str] = None


def _is_import_line(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("import ") or s.startswith("from ")


def _collect_top_import_block(lines: List[str]) -> Tuple[int, int]:
    """
    파이썬 파일 상단(import 구간)만 대상으로 한다.
    - 첫 번째 non-empty/non-comment 이후부터 연속된 import/from 라인(+빈줄/주석)을 포함한다.
    - def/class/기타 코드가 나오면 종료한다.
    반환: (start_idx, end_idx) 0-indexed, end는 exclusive
    """
    i = 0
    n = len(lines)

    # shebang/encoding/빈줄/주석은 스킵
    while i < n and (lines[i].strip() == "" or lines[i].lstrip().startswith("#") or lines[i].startswith("#!/")):
        i += 1

    start = i
    saw_import = False

    while i < n:
        s = lines[i].strip()
        if s == "" or lines[i].lstrip().startswith("#"):
            i += 1
            continue
        if _is_import_line(lines[i]):
            saw_import = True
            i += 1
            continue
        break

    if not saw_import:
        return (0, 0)

    end = i
    return (start, end)


def _import_sort_key(line: str) -> str:
    s = line.strip()
    if s.startswith("from "):
        parts = s.split()
        return parts[1] if len(parts) > 1 else s
    if s.startswith("import "):
        parts = s.split()
        return parts[1] if len(parts) > 1 else s
    return s


def check_import_alphabetical(code: str) -> Tuple[List[SimpleViolation], Optional[str]]:
    lines = code.splitlines(keepends=True)
    start, end = _collect_top_import_block(lines)
    if start == end:
        return ([], None)

    block = lines[start:end]
    import_lines_with_idx = [(idx, ln) for idx, ln in enumerate(block) if _is_import_line(ln)]
    import_lines = [ln for _, ln in import_lines_with_idx]
    sorted_lines = sorted(import_lines, key=_import_sort_key)

    if import_lines == sorted_lines:
        return ([], None)

    vio = SimpleViolation(
        rule_id="PY-IMPORT-ALPHA",
        title="import 순서는 알파벳 순서이다",
        message="상단 import 블록이 알파벳 오름차순이 아니다.",
        start_line=start + 1,
        end_line=end,
        suggestion="상단 import/from 라인을 모듈 경로 기준 알파벳 오름차순으로 정렬한다.",
    )

    fixed_block = block[:]
    it = iter(sorted_lines)
    for rel_idx, _ln in import_lines_with_idx:
        fixed_block[rel_idx] = next(it)

    fixed_lines = lines[:start] + fixed_block + lines[end:]
    fixed_code = "".join(fixed_lines)
    return ([vio], fixed_code)


def check_no_wildcard_import(code: str) -> List[SimpleViolation]:
    vios: List[SimpleViolation] = []
    for i, line in enumerate(code.splitlines(), start=1):
        if re.match(r"^\s*from\s+.+\s+import\s+\*\s*$", line):
            vios.append(
                SimpleViolation(
                    rule_id="PY-NO-WILDCARD-IMPORT",
                    title="from X import * 를 금지한다",
                    message="wildcard import(`from ... import *`)가 발견되었다.",
                    start_line=i,
                    end_line=i,
                    suggestion="명시적으로 필요한 심볼만 import한다.",
                )
            )
    return vios


def fix_trailing_whitespace(code: str) -> Tuple[List[SimpleViolation], Optional[str]]:
    lines = code.splitlines(keepends=True)
    vios: List[SimpleViolation] = []
    fixed_any = False
    fixed_lines: List[str] = []
    for idx, ln in enumerate(lines, start=1):
        if ln.endswith("\n"):
            body = ln[:-1]
            nl = "\n"
        else:
            body = ln
            nl = ""
        if body.rstrip(" \t") != body:
            fixed_any = True
            vios.append(
                SimpleViolation(
                    rule_id="PY-NO-TRAILING-WS",
                    title="라인 끝 공백을 금지한다",
                    message="라인 끝 공백이 발견되었다.",
                    start_line=idx,
                    end_line=idx,
                    suggestion="라인 끝 공백을 제거한다.",
                )
            )
            body = body.rstrip(" \t")
        fixed_lines.append(body + nl)

    if not fixed_any:
        return ([], None)
    return (vios, "".join(fixed_lines))


def check_line_length(code: str, limit: int = 88) -> List[SimpleViolation]:
    vios: List[SimpleViolation] = []
    for i, line in enumerate(code.splitlines(), start=1):
        if len(line) > limit:
            vios.append(
                SimpleViolation(
                    rule_id="PY-LINE-LENGTH-88",
                    title="라인 길이는 88자를 넘기지 않는다",
                    message=f"라인 길이 {len(line)}자가 {limit}자를 초과한다.",
                    start_line=i,
                    end_line=i,
                    suggestion="라인을 분리하거나 문자열/표현식을 정리한다.",
                )
            )
    return vios
