"""Chroma vector store manager — document/knowledge memory."""


import chromadb
from chromadb.config import Settings as ChromaSettings

from assistant_bird.config import get_settings
from assistant_bird.logging_config import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "user_knowledge"


class VectorStore:
    """Chroma-based local vector store for document and knowledge memory.

    Stores text chunks with embeddings, provides semantic search.
    Zero-config: embedded Chroma, no separate server needed.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def search(self, query: str, user_id: str, n_results: int = 5) -> list[dict]:
        """Semantic search for relevant document chunks.

        Args:
            query: Natural language search query.
            user_id: User identifier to filter documents.
            n_results: Max number of chunks to return.

        Returns:
            List of dicts with 'content', 'metadata', 'distance'.
        """
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"user_id": user_id},
            )

            if not results["ids"][0]:
                return []

            items = []
            for i in range(len(results["ids"][0])):
                items.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i]
                    if results["distances"]
                    else None,
                })

            logger.info("vector_store: search", query=query, count=len(items))
            return items
        except Exception as e:
            logger.error("vector_store: search failed", error=str(e))
            return []

    def add_document(
        self,
        content: str,
        user_id: str,
        metadata: dict | None = None,
        doc_id: str | None = None,
    ) -> str:
        """Ingest a document chunk into the vector store.

        Args:
            content: Text content to embed and store.
            user_id: User identifier.
            metadata: Optional metadata dict.
            doc_id: Optional document ID (auto-generated if not provided).

        Returns:
            The document ID.
        """
        import uuid

        doc_id = doc_id or str(uuid.uuid4())
        meta = metadata or {}
        meta["user_id"] = user_id

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[meta],
            )
            logger.info("vector_store: document added", doc_id=doc_id)
            return doc_id
        except Exception as e:
            logger.error("vector_store: add failed", error=str(e))
            raise

    def delete_documents(self, doc_ids: list[str]) -> None:
        """Delete documents by ID.

        Args:
            doc_ids: List of document IDs to remove.
        """
        try:
            self._collection.delete(ids=doc_ids)
            logger.info("vector_store: documents deleted", count=len(doc_ids))
        except Exception as e:
            logger.error("vector_store: delete failed", error=str(e))

    def count(self, user_id: str) -> int:
        """Return the number of documents for a user.

        Args:
            user_id: User identifier.

        Returns:
            Document count.
        """
        try:
            result = self._collection.get(where={"user_id": user_id})
            return len(result["ids"]) if result["ids"] else 0
        except Exception:
            return 0


# Module-level singleton
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the VectorStore singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
