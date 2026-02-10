from __future__ import annotations

import os
from typing import Any, Dict, List
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor

from rule_store import RuleStore
from tools import build_tools


def build_agent(rule_store: RuleStore) -> RunnableWithMessageHistory:
    """
    Tool Calling Agent + 세션별 히스토리(persisted file) 구성.
    - 교안의 구조: system + chat_history + human(input) + agent_scratchpad 구성.
    - AgentExecutor에서 max_iterations, max_execution_time, handle_parsing_errors를 적용한다.
    """
    tools = build_tools(rule_store)

    system_msg = (
        "당신은 [서강대학교 러너톤] AI Code Rule Checker 에이전트이다.\n"
        "목표: 팀의 코딩 규칙을 대신 기억하고, 규칙을 설명하며, 코드를 받으면 위반을 찾고 고치는 것이다.\n"
        "도구 사용 원칙:\n"
        "1) 사용자가 규칙 목록/설명을 요구하면 list_rules 또는 search_rules를 사용한다.\n"
        "2) 사용자가 코드를 주거나 '체크/검사/고쳐' 요청을 하면 check_code를 사용한다.\n"
        "3) 사용자가 새 규칙을 추가하라고 하면 add_rule을 사용하고, 이후 필요 시 rebuild_rules_index를 호출한다.\n"
        "출력은 사람이 읽기 쉽게 작성하되, 위반이 있으면 라인 범위/수정 제안/가능하면 diff를 포함한다.\n"
        "규칙/검사 결과를 임의로 만들어내지 말고, 도구 출력에 근거하여 답한다."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

    agent = create_tool_calling_agent(llm, tools, prompt)

    max_iter = int(os.getenv("AGENT_MAX_ITERATIONS", "8"))
    max_time = float(os.getenv("AGENT_MAX_EXECUTION_TIME", "25"))

    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=max_iter,
        max_execution_time=max_time,
        handle_parsing_errors=True,
    )

    def get_history(session_id: str):
        Path("chat_histories").mkdir(exist_ok=True)
        return FileChatMessageHistory(f"chat_histories/{session_id}.json")

    return RunnableWithMessageHistory(
        executor,
        get_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )
