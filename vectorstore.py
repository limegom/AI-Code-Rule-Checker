from __future__ import annotations

import os
from typing import List, Dict, Any

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


def get_rules_vectorstore() -> Chroma:
    persist_dir = os.getenv("RULES_CHROMA_DIR", "chroma_rules")
    collection = os.getenv("RULES_COLLECTION", "team_rules")
    embeddings = OpenAIEmbeddings()
    return Chroma(
        collection_name=collection,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )


def rules_to_documents(rules: List[Dict[str, Any]]) -> List[Document]:
    docs: List[Document] = []
    for r in rules:
        rid = r.get("id", "UNKNOWN")
        title = r.get("title", "")
        desc = r.get("description", "")
        lang = r.get("language", "any")
        content = f"[{rid}] ({lang}) {title}\n{desc}".strip()
        docs.append(Document(page_content=content, metadata={"rule_id": rid, "language": lang}))
    return docs


def rebuild_rules_index(rules: List[Dict[str, Any]]) -> int:
    """
    Chroma 컬렉션을 현재 rules.json 내용으로 재구축한다.
    - MVP+: 전체 삭제 후 재삽입 방식(규모가 커지면 upsert 전략으로 교체).
    """
    vs = get_rules_vectorstore()
    vs.delete_collection()
    vs = get_rules_vectorstore()
    docs = rules_to_documents(rules)
    vs.add_documents(docs)
    vs.persist()
    return len(docs)


def search_rules(query: str, k: int = 5) -> List[Dict[str, Any]]:
    vs = get_rules_vectorstore()
    docs = vs.similarity_search(query, k=k)
    out = []
    for d in docs:
        out.append(
            {
                "content": d.page_content,
                "metadata": d.metadata,
            }
        )
    return out
