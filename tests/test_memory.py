"""Tests for memory system components."""


class TestVectorStore:
    """Tests for Chroma vector store."""

    def test_import(self):
        from assistant_bird.memory.vector_store import get_vector_store

        store = get_vector_store()
        assert store is not None

    def test_add_and_search(self):
        from assistant_bird.memory.vector_store import get_vector_store

        store = get_vector_store()
        doc_id = store.add_document(
            content="Python is a programming language.",
            user_id="test_user",
            metadata={"source": "test"},
        )
        assert doc_id is not None

        results = store.search("Python programming", "test_user", n_results=1)
        assert len(results) > 0
        assert "Python" in results[0]["content"]

        # Cleanup
        store.delete_documents([doc_id])

    def test_search_returns_empty_for_missing(self):
        from assistant_bird.memory.vector_store import get_vector_store

        store = get_vector_store()
        results = store.search("xyz-nonexistent-query-abc", "test_user", n_results=1)
        assert len(results) == 0

    def test_document_count(self):
        from assistant_bird.memory.vector_store import get_vector_store

        store = get_vector_store()
        initial = store.count("count_test_user")
        doc_id = store.add_document("Test content", "count_test_user")
        assert store.count("count_test_user") == initial + 1
        store.delete_documents([doc_id])


class TestConversationDB:
    """Tests for SQLite conversation database."""

    def test_save_and_retrieve(self):
        from assistant_bird.memory.conversation_db import get_conversation_db

        db = get_conversation_db()
        db.save_message("test_user", "user", "Hello!")
        db.save_message("test_user", "assistant", "Hi there!")

        recent = db.get_recent("test_user", limit=5)
        assert len(recent) >= 2

    def test_search_conversations(self):
        from assistant_bird.memory.conversation_db import get_conversation_db

        db = get_conversation_db()
        db.save_message("search_test", "user", "I love pizza")

        results = db.search("search_test", "pizza")
        assert len(results) > 0
        assert any("pizza" in r["content"] for r in results)

    def test_summary_for_context(self):
        from assistant_bird.memory.conversation_db import get_conversation_db

        db = get_conversation_db()
        db.save_message("summary_test", "user", "What is Python?")
        db.save_message("summary_test", "assistant", "Python is a language.")

        summary = db.get_summary_for_context("summary_test", num_turns=2)
        assert "Python" in summary


class TestMem0Client:
    """Tests for Mem0 client wrapper."""

    def test_disabled_when_no_key(self):
        from assistant_bird.memory.mem0_client import get_mem0_client

        client = get_mem0_client()
        # MEM0_API_KEY is set to "" in test env
        assert not client.enabled

    def test_search_returns_empty_when_disabled(self):
        from assistant_bird.memory.mem0_client import get_mem0_client

        client = get_mem0_client()
        results = client.search("test", "user")
        assert results == []

    def test_add_returns_empty_when_disabled(self):
        from assistant_bird.memory.mem0_client import get_mem0_client

        client = get_mem0_client()
        results = client.add(
            [{"role": "user", "content": "test"}],
            user_id="user",
        )
        assert results == []


class TestMemoryManager:
    """Tests for memory orchestrator."""

    def test_import(self):
        from assistant_bird.memory.memory_manager import get_memory_manager

        mgr = get_memory_manager()
        assert mgr is not None

    def test_get_context_returns_string(self):
        from assistant_bird.memory.memory_manager import get_memory_manager

        mgr = get_memory_manager()
        context = mgr.get_context("test query", "test_user")
        assert isinstance(context, str)

    def test_store_conversation(self):
        from assistant_bird.memory.memory_manager import get_memory_manager

        mgr = get_memory_manager()
        # Should not raise
        mgr.store_conversation("test_user", "Hello", "Hi there!")
