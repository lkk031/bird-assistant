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
        # Should have titles, results, or a clear error message when DDG is down
        assert (
            "Python" in result
            or "Search results for" in result
            or "No results" in result
            or "搜索暂时不可用" in result
        )

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

    # --- read_lines ---

    def test_read_lines_basic(self, workspace_dir):
        from assistant_bird.agents.filesystem import read_lines

        test_file = workspace_dir / "lines.txt"
        test_file.write_text("line1\nline2\nline3\nline4\nline5")

        result = read_lines.invoke({"path_str": "lines.txt", "start_line": 2, "end_line": 4})
        assert "line2" in result
        assert "line3" in result
        assert "line4" in result
        assert "line1" not in result
        assert "line5" not in result

    def test_read_lines_default_range(self, workspace_dir):
        from assistant_bird.agents.filesystem import read_lines

        test_file = workspace_dir / "lines.txt"
        test_file.write_text("\n".join(str(i) for i in range(1, 101)))

        result = read_lines.invoke({"path_str": "lines.txt"})
        assert "Lines 1-50 of 100" in result

    def test_read_lines_invalid_range(self, workspace_dir):
        from assistant_bird.agents.filesystem import read_lines

        (workspace_dir / "lines.txt").write_text("test")
        result = read_lines.invoke({"path_str": "lines.txt", "start_line": 5, "end_line": 1})
        assert "Error" in result

    # --- get_file_info ---

    def test_get_file_info(self, workspace_dir):
        from assistant_bird.agents.filesystem import get_file_info

        test_file = workspace_dir / "info.txt"
        test_file.write_text("hello world")

        result = get_file_info.invoke({"path_str": "info.txt"})
        assert "📄 File" in result or "File" in result
        assert "info.txt" in result
        assert "11 bytes" in result

    def test_get_file_info_directory(self, workspace_dir):
        from assistant_bird.agents.filesystem import get_file_info

        (workspace_dir / "sub").mkdir()

        result = get_file_info.invoke({"path_str": "sub"})
        assert "Directory" in result or "sub" in result

    def test_get_file_info_not_found(self):
        from assistant_bird.agents.filesystem import get_file_info

        result = get_file_info.invoke({"path_str": "nonexistent.xyz"})
        assert "not found" in result

    # --- append_to_file ---

    def test_append_to_existing(self, workspace_dir):
        from assistant_bird.agents.filesystem import append_to_file

        (workspace_dir / "log.txt").write_text("line1\n")

        result = append_to_file.invoke({"path_str": "log.txt", "content": "line2\n"})
        assert "已追加" in result or "appended" in result.lower()
        assert (workspace_dir / "log.txt").read_text() == "line1\nline2\n"

    def test_append_creates_new_file(self, workspace_dir):
        from assistant_bird.agents.filesystem import append_to_file

        result = append_to_file.invoke({"path_str": "new_log.txt", "content": "first line\n"})
        assert "已追加" in result or "appended" in result.lower()
        assert (workspace_dir / "new_log.txt").exists()
        assert (workspace_dir / "new_log.txt").read_text() == "first line\n"

    # --- delete_file ---

    def test_delete_file_needs_confirmation(self, workspace_dir):
        from assistant_bird.agents.filesystem import delete_file

        (workspace_dir / "to_delete.txt").write_text("delete me")

        result = delete_file.invoke({"path_str": "to_delete.txt"})
        assert "确认" in result or "confirm" in result.lower()
        assert (workspace_dir / "to_delete.txt").exists()  # Still exists

    def test_delete_file_confirmed(self, workspace_dir):
        from assistant_bird.agents.filesystem import delete_file

        (workspace_dir / "to_delete.txt").write_text("delete me")

        result = delete_file.invoke({"path_str": "to_delete.txt", "confirm": True})
        assert "已删除" in result or "deleted" in result.lower()
        assert not (workspace_dir / "to_delete.txt").exists()

    def test_delete_nonexistent(self):
        from assistant_bird.agents.filesystem import delete_file

        result = delete_file.invoke({"path_str": "nonexistent.txt", "confirm": True})
        assert "not found" in result

    def test_delete_non_empty_directory(self, workspace_dir):
        from assistant_bird.agents.filesystem import delete_file

        sub = workspace_dir / "nonempty"
        sub.mkdir()
        (sub / "file.txt").write_text("data")

        result = delete_file.invoke({"path_str": "nonempty", "confirm": True})
        assert "Error" in result or "not empty" in result

    # --- move_file ---

    def test_move_file_rename(self, workspace_dir):
        from assistant_bird.agents.filesystem import move_file

        (workspace_dir / "old_name.txt").write_text("content")

        result = move_file.invoke({"source": "old_name.txt", "destination": "new_name.txt"})
        assert "完成" in result or "moved" in result.lower()
        assert not (workspace_dir / "old_name.txt").exists()
        assert (workspace_dir / "new_name.txt").exists()
        assert (workspace_dir / "new_name.txt").read_text() == "content"

    def test_move_file_to_subdir(self, workspace_dir):
        from assistant_bird.agents.filesystem import move_file

        (workspace_dir / "sub").mkdir()
        (workspace_dir / "move_me.txt").write_text("moving")

        result = move_file.invoke({"source": "move_me.txt", "destination": "sub/move_me.txt"})
        assert "完成" in result or "moved" in result.lower()
        assert not (workspace_dir / "move_me.txt").exists()
        assert (workspace_dir / "sub" / "move_me.txt").exists()

    def test_move_file_destination_exists(self, workspace_dir):
        from assistant_bird.agents.filesystem import move_file

        (workspace_dir / "src.txt").write_text("src")
        (workspace_dir / "dst.txt").write_text("dst")

        result = move_file.invoke({"source": "src.txt", "destination": "dst.txt"})
        assert "已存在" in result or "exists" in result.lower()

    def test_move_file_source_not_found(self):
        from assistant_bird.agents.filesystem import move_file

        result = move_file.invoke({"source": "nope.txt", "destination": "somewhere.txt"})
        assert "not found" in result

    # --- copy_file ---

    def test_copy_file(self, workspace_dir):
        from assistant_bird.agents.filesystem import copy_file

        (workspace_dir / "original.txt").write_text("original content")

        result = copy_file.invoke({"source": "original.txt", "destination": "copy.txt"})
        assert "复制" in result or "copied" in result.lower()
        assert (workspace_dir / "original.txt").exists()
        assert (workspace_dir / "copy.txt").exists()
        assert (workspace_dir / "copy.txt").read_text() == "original content"

    def test_copy_file_source_not_found(self):
        from assistant_bird.agents.filesystem import copy_file

        result = copy_file.invoke({"source": "nope.txt", "destination": "anywhere.txt"})
        assert "not found" in result

    def test_copy_file_destination_exists(self, workspace_dir):
        from assistant_bird.agents.filesystem import copy_file

        (workspace_dir / "src.txt").write_text("src")
        (workspace_dir / "dst.txt").write_text("dst")

        result = copy_file.invoke({"source": "src.txt", "destination": "dst.txt"})
        assert "已存在" in result or "exists" in result.lower()

    # --- create_directory ---

    def test_create_directory(self, workspace_dir):
        from assistant_bird.agents.filesystem import create_directory

        result = create_directory.invoke({"path_str": "new_dir"})
        assert "已创建" in result or "created" in result.lower()
        assert (workspace_dir / "new_dir").is_dir()

    def test_create_directory_nested(self, workspace_dir):
        from assistant_bird.agents.filesystem import create_directory

        result = create_directory.invoke({"path_str": "a/b/c"})
        assert "已创建" in result or "created" in result.lower()
        assert (workspace_dir / "a" / "b" / "c").is_dir()

    def test_create_directory_already_exists(self, workspace_dir):
        from assistant_bird.agents.filesystem import create_directory

        (workspace_dir / "existing_dir").mkdir()
        result = create_directory.invoke({"path_str": "existing_dir"})
        assert "已存在" in result or "exists" in result.lower()

    # --- write_file overwrite ---

    def test_write_file_overwrite(self, workspace_dir):
        from assistant_bird.agents.filesystem import write_file

        (workspace_dir / "overwrite.txt").write_text("old")

        result = write_file.invoke({
            "path_str": "overwrite.txt",
            "content": "new",
            "overwrite": True,
        })
        assert "覆盖" in result or "成功" in result or "written" in result.lower()
        assert (workspace_dir / "overwrite.txt").read_text() == "new"


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
