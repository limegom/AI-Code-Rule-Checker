from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

from rule_store import RuleStore
from agent import build_agent


def main():
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 설정되어야 한다. .env 또는 환경변수를 확인한다.")

    store = RuleStore(Path("rules/rules.json"))
    agent = build_agent(store)

    session_id = "local-demo"

    print("AI Code Rule Checker Agent Demo. 종료: /q")
    while True:
        user = input("You> ")
        if user.strip() in {"/q", "/quit", "quit", "exit"}:
            break
        out = agent.invoke(
            {"input": user},
            config={"configurable": {"session_id": session_id}},
        )
        print("AI> ", out["output"])


if __name__ == "__main__":
    main()
