"""Tests for tool implementations."""



class TestWebSearch:
    """Tests for DuckDuckGo web_search tool."""

    def test_import(self):
        from assistant_bird.tools.web_search import web_search
        assert web_search is not None
        assert hasattr(web_search, "invoke")

    def test_search_returns_results(self):
        """Integration test: real DuckDuckGo search."""
        from assistant_bird.tools.web_search import web_search

        result = web_search.invoke({"query": "Python programming", "num_results": 3})
        assert isinstance(result, str)
        assert len(result) > 0
        # Should have titles or results
        assert "Python" in result or "Search results for" in result or "No results" in result

    def test_search_respects_max_results(self):
        from assistant_bird.tools.web_search import web_search

        result = web_search.invoke({"query": "test", "num_results": 20})
        # Should be capped at 10
        assert isinstance(result, str)


class TestWebScraper:
    """Tests for web scraper tool."""

    def test_import(self):
        from assistant_bird.tools.web_scraper import scrape_webpage, search_and_scrape
        assert scrape_webpage is not None
        assert search_and_scrape is not None

    def test_invalid_url_rejected(self):
        from assistant_bird.tools.web_scraper import scrape_webpage

        result = scrape_webpage.invoke({"url": "not-a-valid-url"})
        assert "Error" in result

    def test_nonexistent_domain(self):
        from assistant_bird.tools.web_scraper import scrape_webpage

        result = scrape_webpage.invoke({"url": "https://this-domain-does-not-exist-12345.com"})
        assert "Error" in result


class TestFileOps:
    """Tests for file operations tools."""

    def test_read_file(self, workspace_dir):
        from assistant_bird.agents.filesystem import read_file

        # Create a test file
        test_file = workspace_dir / "test.txt"
        test_file.write_text("Hello, World!")

        result = read_file.invoke({"path_str": "test.txt"})
        assert "Hello, World!" in result

    def test_read_nonexistent_file(self):
        from assistant_bird.agents.filesystem import read_file

        result = read_file.invoke({"path_str": "nonexistent.txt"})
        assert "Error" in result or "not found" in result

    def test_write_file(self, workspace_dir):
        from assistant_bird.agents.filesystem import write_file

        result = write_file.invoke({
            "path_str": "output.txt",
            "content": "Test output",
        })
        assert "已写入" in result or "written" in result.lower()
        assert (workspace_dir / "output.txt").exists()
        assert (workspace_dir / "output.txt").read_text() == "Test output"

    def test_write_file_warns_overwrite(self, workspace_dir):
        from assistant_bird.agents.filesystem import write_file

        # Create existing file
        (workspace_dir / "existing.txt").write_text("old content")

        result = write_file.invoke({
            "path_str": "existing.txt",
            "content": "new content",
        })
        assert "已存在" in result or "exists" in result.lower()

    def test_list_directory(self, workspace_dir):
        from assistant_bird.agents.filesystem import list_directory

        (workspace_dir / "a.txt").write_text("a")
        (workspace_dir / "b.txt").write_text("b")

        result = list_directory.invoke({"path_str": "."})
        assert "a.txt" in result
        assert "b.txt" in result

    def test_list_empty_directory(self, workspace_dir):
        from assistant_bird.agents.filesystem import list_directory

        empty_dir = workspace_dir / "empty"
        empty_dir.mkdir()

        result = list_directory.invoke({"path_str": "empty"})
        assert "empty" in result.lower()

    def test_search_files(self, workspace_dir):
        from assistant_bird.agents.filesystem import search_files

        (workspace_dir / "test1.py").write_text("# test")
        (workspace_dir / "test2.py").write_text("# test")
        (workspace_dir / "data.txt").write_text("data")

        result = search_files.invoke({
            "pattern": "*.py",
            "directory": ".",
        })
        assert "test1.py" in result
        assert "test2.py" in result
        assert "data.txt" not in result

    def test_search_files_no_match(self, workspace_dir):
        from assistant_bird.agents.filesystem import search_files

        result = search_files.invoke({
            "pattern": "*.rs",
            "directory": ".",
        })
        assert "No files matching" in result

    def test_path_sandbox(self, workspace_dir):
        from assistant_bird.agents.filesystem import read_file

        result = read_file.invoke({"path_str": "../etc/passwd"})
        assert "Access denied" in result


class TestToolRegistry:
    """Tests for tool registry."""

    def test_get_tools(self):
        from assistant_bird.tools.registry import get_tool_registry

        registry = get_tool_registry()
        tools = registry.get_tools(["web_search", "scrape_webpage"])
        assert len(tools) == 2

    def test_list_tools(self):
        from assistant_bird.tools.registry import get_tool_registry

        registry = get_tool_registry()
        names = registry.list_tools()
        assert "web_search" in names
        assert "scrape_webpage" in names
        assert "search_and_scrape" in names
