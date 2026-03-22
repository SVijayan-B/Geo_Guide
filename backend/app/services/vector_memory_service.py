from __future__ import annotations

import hashlib
import os
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer


class VectorMemoryService:
    """Persistent semantic memory using ChromaDB for chats and personalization signals."""

    _embedder: SentenceTransformer | None = None

    def __init__(
        self,
        persist_path: str | None = None,
        collection_name: str = "geo_guide_memory",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        persist_path = persist_path or os.getenv("CHROMA_PATH", "./chroma_db")

        if VectorMemoryService._embedder is None:
            VectorMemoryService._embedder = SentenceTransformer(embedding_model)

        self._embedder = VectorMemoryService._embedder
        self._client = chromadb.PersistentClient(path=persist_path)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _doc_id(self, user_id: int, session_id: int | None, role: str, text: str, memory_type: str) -> str:
        seed = f"{user_id}:{session_id}:{role}:{memory_type}:{text}".encode("utf-8", errors="ignore")
        return hashlib.sha1(seed).hexdigest()

    def _upsert_document(
        self,
        *,
        user_id: int,
        session_id: int | None,
        role: str,
        text: str,
        memory_type: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        if not text or not text.strip():
            return

        embedding = self._embedder.encode(text).tolist()
        doc_id = self._doc_id(user_id, session_id=session_id, role=role, text=text, memory_type=memory_type)

        metadata = {
            "user_id": str(user_id),
            "session_id": str(session_id) if session_id is not None else "",
            "role": role,
            "memory_type": memory_type,
        }
        if extra_metadata:
            metadata.update({str(key): str(value) for key, value in extra_metadata.items()})

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[metadata],
            )
        except Exception:
            return

    def add_text(
        self,
        user_id: int,
        session_id: int | None,
        role: str,
        text: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._upsert_document(
            user_id=user_id,
            session_id=session_id,
            role=role,
            text=text,
            memory_type="chat",
            extra_metadata=extra_metadata,
        )

    def add_preference(self, *, user_id: int, preference_text: str, source: str = "chat") -> None:
        self._upsert_document(
            user_id=user_id,
            session_id=None,
            role="system",
            text=preference_text,
            memory_type="preference",
            extra_metadata={"source": source},
        )

    def add_trip_snapshot(self, *, user_id: int, trip_id: int, origin: str, destination: str, status: str) -> None:
        text = f"Trip {trip_id}: {origin} to {destination}, status={status}"
        self._upsert_document(
            user_id=user_id,
            session_id=None,
            role="system",
            text=text,
            memory_type="trip",
            extra_metadata={"trip_id": trip_id, "origin": origin, "destination": destination, "status": status},
        )

    def add_viewed_place(self, *, user_id: int, place_name: str, city: str | None = None, details: str | None = None) -> None:
        text = f"Viewed place: {place_name}" if not details else f"Viewed place: {place_name}. {details}"
        self._upsert_document(
            user_id=user_id,
            session_id=None,
            role="system",
            text=text,
            memory_type="viewed_place",
            extra_metadata={"place_name": place_name, "city": city or ""},
        )

    def query_similar(
        self,
        user_id: int,
        query_text: str,
        k: int = 6,
        memory_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        if not query_text or not query_text.strip():
            return []

        embedding = self._embedder.encode(query_text).tolist()
        where: dict[str, Any] = {"user_id": str(user_id)}

        if memory_types:
            normalized = [str(item) for item in memory_types if item]
            if len(normalized) == 1:
                where["memory_type"] = normalized[0]
            elif normalized:
                where = {
                    "$and": [
                        {"user_id": str(user_id)},
                        {"$or": [{"memory_type": value} for value in normalized]},
                    ]
                }

        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        docs: list[dict[str, Any]] = []
        documents = results.get("documents", [[]])
        metadatas = results.get("metadatas", [[]])
        distances = results.get("distances", [[]])

        for doc_list, meta_list, dist_list in zip(documents, metadatas, distances):
            for doc, meta, dist in zip(doc_list, meta_list, dist_list):
                score = 1.0 - float(dist) if dist is not None else None
                docs.append(
                    {
                        "document": doc,
                        "metadata": meta or {},
                        "score": score,
                    }
                )

        return docs
