import hashlib
import os
from typing import Dict, Any, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer


class VectorMemoryService:
    """
    Persistent semantic memory using ChromaDB.

    Stores documents (chat turns / preferences / viewed places) and retrieves
    similar context by semantic similarity for personalization.
    """

    def __init__(
        self,
        persist_path: Optional[str] = None,
        collection_name: str = "geo_guide_memory",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        persist_path = persist_path or os.getenv("CHROMA_PATH", "./chroma_db")
        self._embedder = SentenceTransformer(embedding_model)
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _doc_id(self, user_id: int, session_id: Optional[int], role: str, text: str) -> str:
        seed = f"{user_id}:{session_id}:{role}:{text}".encode("utf-8", errors="ignore")
        return hashlib.sha1(seed).hexdigest()

    def add_text(
        self,
        user_id: int,
        session_id: Optional[int],
        role: str,
        text: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not text or not text.strip():
            return

        embedding = self._embedder.encode(text).tolist()
        doc_id = self._doc_id(user_id, session_id=session_id, role=role, text=text)

        metadata = {
            "user_id": str(user_id),
            "session_id": str(session_id) if session_id is not None else "",
            "role": role,
        }
        if extra_metadata:
            metadata.update({str(k): str(v) for k, v in extra_metadata.items()})

        # `add` requires unique ids. If the same document is re-ingested,
        # Chroma may error; that's acceptable for now (we avoid crashes by try/except).
        try:
            self._collection.add(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata],
            )
        except Exception:
            # Best-effort ingestion: do not break chat if vector store already has the document.
            return

    def query_similar(
        self, user_id: int, query_text: str, k: int = 6
    ) -> List[Dict[str, Any]]:
        if not query_text or not query_text.strip():
            return []

        embedding = self._embedder.encode(query_text).tolist()
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where={"user_id": str(user_id)},
            include=["documents", "metadatas"],
        )

        docs = []
        for doc_list, meta_list in zip(results.get("documents", [[]]), results.get("metadatas", [[]])):
            for doc, meta in zip(doc_list, meta_list):
                docs.append({"document": doc, "metadata": meta or {}})
        return docs

