from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class RuleStore:
    """
    MVP+에서는 JSON 파일 기반 RuleStore를 유지한다.
    - rules.json 포맷만 유지하면, 추후 SQLite/PostgreSQL 등으로 교체 가능하다.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"team_name": "unknown", "members": [], "rules": []}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: Dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def team_name(self) -> str:
        return str(self.load().get("team_name", "unknown"))

    def members(self) -> List[str]:
        return list(self.load().get("members", []))

    def list_rules(self) -> List[Dict[str, Any]]:
        return list(self.load().get("rules", []))

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        for r in self.list_rules():
            if r.get("id") == rule_id:
                return r
        return None

    def add_rule(self, rule: Dict[str, Any]) -> None:
        data = self.load()
        rules = data.get("rules", [])
        rule_ids = {r.get("id") for r in rules}
        if rule.get("id") in rule_ids:
            raise ValueError(f"Rule id already exists: {rule.get('id')}")
        rules.append(rule)
        data["rules"] = rules
        self.save(data)

    def update_rule(self, rule_id: str, patch: Dict[str, Any]) -> None:
        data = self.load()
        rules = data.get("rules", [])
        for i, r in enumerate(rules):
            if r.get("id") == rule_id:
                merged = dict(r)
                merged.update(patch)
                rules[i] = merged
                data["rules"] = rules
                self.save(data)
                return
        raise ValueError(f"Rule not found: {rule_id}")
