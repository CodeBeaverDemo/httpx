import os
import re
import sys
import tempfile
import pytest

from scripts import unasync

class TestUnasync:
    """Test suite for the unasync script functionality."""

    def test_unasync_line_multiple_patterns(self):
        """Test unasync_line with multiple async patterns in a single line."""
        # Example: "async def my_function:" should convert to "def my_function:"
        input_line = "async def my_function(AsyncIterator, await aclose):"
        # Expected conversion based on substitutions:
        expected = "def my_function(Iterator, close):"
        output_line = unasync.unasync_line(input_line)
        assert output_line == expected

    def test_unasync_file_and_file_check(self):
        """Test unasync_file and unasync_file_check with temporary files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.py")
            output_path = os.path.join(tmpdir, "output.py")
            content = "async def foo(AsyncIterator):\n    await bar()\n"
            with open(input_path, "w") as f:
                f.write(content)
            # Generate the sync version
            unasync.unasync_file(input_path, output_path)
            with open(output_path, "r") as f:
                result = f.read()
            expected = "def foo(Iterator):\n    bar()\n"
            assert result == expected
            # Verify that unasync_file_check does not raise an error for matching files.
            unasync.unasync_file_check(input_path, output_path)

    def test_unasync_file_check_mismatch(self):
        """Test unasync_file_check detects mismatches and exits."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "input.py")
            output_path = os.path.join(tmpdir, "output.py")
            content = "async def foo(AsyncIterator):\n    await bar()\n"
            with open(input_path, "w") as f:
                f.write(content)
            # Write an incorrect sync file manually.
            wrong_sync = "def foo(Iterator):\n    await bar()\n"
            with open(output_path, "w") as f:
                f.write(wrong_sync)
            with pytest.raises(SystemExit):
                unasync.unasync_file_check(input_path, output_path)

    def test_unasync_dir_check_only(self):
        """Test unasync_dir in check_only mode with temporary directory structure."""
        with tempfile.TemporaryDirectory() as in_dir, tempfile.TemporaryDirectory() as out_dir:
            sub_dir = os.path.join(in_dir, "sub")
            os.makedirs(sub_dir)
            file_path = os.path.join(sub_dir, "test.py")
            with open(file_path, "w") as f:
                f.write("async def foo(AsyncIterator):\n    await bar()\n")
            sub_out_dir = os.path.join(out_dir, "sub")
            os.makedirs(sub_out_dir)
            out_file_path = os.path.join(sub_out_dir, "test.py")
            with open(out_file_path, "w") as f:
                f.write("def foo(Iterator):\n    bar()\n")
            # In check_only mode, unasync_dir should not modify files and should not exit if files match.
            unasync.unasync_dir(in_dir, out_dir, check_only=True)

    def test_unasync_dir_conversion(self):
        """Test unasync_dir conversion mode by verifying file contents in output directory."""
        with tempfile.TemporaryDirectory() as in_dir, tempfile.TemporaryDirectory() as out_dir:
            file1 = os.path.join(in_dir, "a.py")
            file2 = os.path.join(in_dir, "b.py")
            with open(file1, "w") as f:
                f.write("async def a(AsyncIterator):\n    await bar()\n")
            with open(file2, "w") as f:
                f.write("async with something:\n    await process()\n")
            unasync.unasync_dir(in_dir, out_dir)
            with open(os.path.join(out_dir, "a.py"), "r") as f:
                content_a = f.read()
            with open(os.path.join(out_dir, "b.py"), "r") as f:
                content_b = f.read()
            expected_a = "def a(Iterator):\n    bar()\n"
            expected_b = "with something:\n    process()\n"
            assert content_a == expected_a
            assert content_b == expected_b

    def test_used_subs_reporting_after_all_tests(self):
        """Test that main reports unused substitutions and exits due to incomplete usage."""
        # Backup the original unasync_dir function to prevent actual directory walking.
        original_unasync_dir = unasync.unasync_dir
        unasync.unasync_dir = lambda in_dir, out_dir, check_only=False: None

        # Backup current USED_SUBS and clear it to simulate unused substitutions.
        old_used_subs = set(unasync.USED_SUBS)
        unasync.USED_SUBS.clear()

        # Simulate running main with no --check argument.
        old_argv = sys.argv
        sys.argv = ["dummy_script.py"]
        with pytest.raises(SystemExit) as e:
            unasync.main()
        sys.argv = old_argv
        # Restore global state.
        unasync.USED_SUBS.clear()
        unasync.USED_SUBS.update(old_used_subs)
        unasync.unasync_dir = original_unasync_dir
    def test_unasync_line_no_conversion(self):
        """Test that unasync_line returns the original string if no patterns match."""
        old_used = unasync.USED_SUBS.copy()
        input_line = "This is a line with no async keywords."
        result = unasync.unasync_line(input_line)
        assert result == input_line, "Line with no patterns should be unchanged."
        # Ensure that no additional substitutions were recorded.
        assert unasync.USED_SUBS == old_used

    def test_individual_substitutions(self):
        """Test each individual substitution pattern for correct conversion."""
        test_data = [
            ("AsyncByteStream", "SyncByteStream"),
            ("async_auth_flow", "sync_auth_flow"),
            ("handle_async_request", "handle_request"),
            ("AsyncIterator", "Iterator"),
            ("from anyio import Lock", "from threading import Lock"),
            ("AsyncFoo", "Foo"),  # using pattern Async([A-Z][A-Za-z0-9_]*) -> "\2"
            ("async def", "def"),
            ("async with", "with"),
            ("async for", "for"),
            ("await value", "value"),
            ("aclose", "close"),
            ("aread", "read"),
            ("__aenter__", "__enter__"),
            ("__aexit__", "__exit__"),
            ("__aiter__", "__iter__"),
            ("@pytest.mark.anyio", ""),
        ]
        # Save and clear USED_SUBS to isolate the test.
        old_used = unasync.USED_SUBS.copy()
        unasync.USED_SUBS.clear()
        for inp, expected in test_data:
            result = unasync.unasync_line(inp)
            assert result == expected, f"For input '{inp}', expected '{expected}' but got '{result}'"
        # Restore USED_SUBS global after test.
        unasync.USED_SUBS.update(old_used)

    def test_unasync_dir_skips_non_py_files(self):
        """Test that unasync_dir skips files that do not end with .py."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as in_dir, tempfile.TemporaryDirectory() as out_dir:
            # Create a non-Python file in the input directory.
            non_py_file = os.path.join(in_dir, "notes.txt")
            with open(non_py_file, "w") as f:
                f.write("async def not_a_python_function(): pass\n")
            # Call unasync_dir conversion (should process only .py files)
            unasync.unasync_dir(in_dir, out_dir)
            # Check that no equivalent output file was created for the .txt file.
            out_non_py = os.path.join(out_dir, "notes.txt")
            assert not os.path.exists(out_non_py), "Non-.py files should be skipped by unasync_dir."
    def test_empty_file_conversion(self):
        """Test conversion of an empty file results in an empty output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "empty.py")
            output_path = os.path.join(tmpdir, "empty_out.py")
            # Create an empty input file
            with open(input_path, "w") as f:
                f.write("")
            unasync.unasync_file(input_path, output_path)
            with open(output_path, "r") as f:
                result = f.read()
            assert result == ""

    def test_unasync_file_extra_lines_sync(self):
        """Test that unasync_file_check ignores extra trailing lines in the sync file.
        The extra trailing lines in the sync file are ignored because zip only iterates as long as the shortest file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "in_extra.py")
            output_path = os.path.join(tmpdir, "out_extra.py")
            content = "async def foo(AsyncIterator):\n    await bar()\n"
            with open(input_path, "w") as f:
                f.write(content)
            # Generate expected sync conversion
            expected_conversion = "def foo(Iterator):\n    bar()\n"
            # Write the sync file with an extra trailing line
            with open(output_path, "w") as f:
                f.write(expected_conversion + "extra trailing line\n")
            # unasync_file_check should succeed because it only compares lines up to the shorter file.
            unasync.unasync_file_check(input_path, output_path)

    def test_unasync_line_with_word_boundaries(self):
        """Test that unasync_line does not replace keywords when they are part of a larger word.
        For example, "myasync def foo(): pass" should not be transformed.
        """
        input_line = "myasync def foo(): pass"
        result = unasync.unasync_line(input_line)
        assert result == input_line, "Line with non-boundary async keyword should remain unchanged."

    def test_unasync_file_no_trailing_newline(self):
        """Test that unasync_file correctly converts a file that does not end with a newline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "no_newline.py")
            output_path = os.path.join(tmpdir, "no_newline_out.py")
            # Write a file without a trailing newline
            content = "async def foo(AsyncIterator):"
            with open(input_path, "w") as f:
                f.write(content)
            unasync.unasync_file(input_path, output_path)
            with open(output_path, "r") as f:
                result = f.read()
            expected = "def foo(Iterator):"
            assert result == expected
    def test_main_success(self):
        """Test that main completes successfully when all substitution patterns are used."""
        # Backup the original unasync_dir function and USED_SUBS
        original_unasync_dir = unasync.unasync_dir
        old_used_subs = set(unasync.USED_SUBS)
        # Simulate all substitutions used by setting USED_SUBS to all indices
        unasync.USED_SUBS.clear()
        unasync.USED_SUBS.update(range(len(unasync.SUBS)))
        # Override unasync_dir to prevent actual directory walking during the test
        unasync.unasync_dir = lambda in_dir, out_dir, check_only=False: None
        # Set sys.argv to simulate a normal invocation (without --check)
        old_argv = sys.argv
        sys.argv = ["dummy_script.py"]
        try:
            unasync.main()
        finally:
            sys.argv = old_argv
            unasync.USED_SUBS.clear()
            unasync.USED_SUBS.update(old_used_subs)
            unasync.unasync_dir = original_unasync_dir

    def test_unasync_file_crlf(self):
        """Test that unasync_file correctly converts a file with CRLF newlines."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "crlf_input.py")
            output_path = os.path.join(tmpdir, "crlf_output.py")
            # Write a file with CRLF endings
            content = "async def foo(AsyncIterator):\r\n    await bar()\r\n"
            with open(input_path, "w", newline="") as f:
                f.write(content)
            # Convert the file
            unasync.unasync_file(input_path, output_path)
            with open(output_path, "r") as f:
                result = f.read()
            # Even if the file was written with CRLF, since it was read in text-mode it gets normalized,
            # so we expect LF endings in the result.
            expected = "def foo(Iterator):\n    bar()\n"
            assert result == expected