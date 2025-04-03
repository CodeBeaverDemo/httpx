import sys

import pytest

from scripts import unasync


# Helper function to reset global substitutions-used tracker before each test.
def reset_used_subs():
    unasync.USED_SUBS.clear()


def test_unasync_line_def():
    """Test that 'async def' is replaced with 'def'."""
    reset_used_subs()
    line = "async def myfunc():"
    expected = "def myfunc():"
    result = unasync.unasync_line(line)
    assert result == expected


def test_unasync_line_multiple():
    """Test multiple substitutions in one line, e.g. 'async for' and 'AsyncIterator'."""
    reset_used_subs()
    line = "async for item in AsyncIterator:"
    expected = "for item in Iterator:"
    result = unasync.unasync_line(line)
    assert result == expected


def test_unasync_async_pattern():
    """Test the substitution pattern for 'Async' followed by an identifier."""
    reset_used_subs()
    line = "AsyncFoo"
    expected = "Foo"
    result = unasync.unasync_line(line)
    assert result == expected


def test_unasync_file(tmp_path):
    """Test unasync_file converts file content correctly."""
    reset_used_subs()
    input_file = tmp_path / "input.py"
    output_file = tmp_path / "output.py"
    content = "async def foo():\n    await bar()\n"
    input_file.write_text(content)
    unasync.unasync_file(str(input_file), str(output_file))
    expected = "def foo():\n    bar()\n"
    assert output_file.read_text() == expected


def test_unasync_file_check_success(tmp_path):
    """Test unasync_file_check passes when file content matches expected conversion."""
    reset_used_subs()
    input_file = tmp_path / "input.py"
    output_file = tmp_path / "output.py"
    content = "async def foo():\n    await bar()\n"
    expected = "def foo():\n    bar()\n"
    input_file.write_text(content)
    output_file.write_text(expected)
    unasync.unasync_file_check(str(input_file), str(output_file))


def test_unasync_file_check_failure(tmp_path):
    """Test unasync_file_check fails when conversion does not match expected output."""
    reset_used_subs()
    input_file = tmp_path / "input.py"
    output_file = tmp_path / "output.py"
    content = "async def foo():\n    await bar()\n"
    wrong = "def foo():\n    bar()  # extra comment\n"
    input_file.write_text(content)
    output_file.write_text(wrong)
    with pytest.raises(SystemExit) as e:
        unasync.unasync_file_check(str(input_file), str(output_file))
    assert e.value.code == 1


def test_unasync_dir(tmp_path):
    """Test unasync_dir processes all .py files in a directory recursively."""
    reset_used_subs()
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    (out_dir / "sub").mkdir(parents=True, exist_ok=True)
    sub_dir = in_dir / "sub"
    sub_dir.mkdir()
    file1 = in_dir / "a.py"
    file1.write_text("async def a():\n    await b()\n")
    file2 = sub_dir / "b.py"
    file2.write_text("async for item in AsyncIterator:\n    await process(item)\n")
    unasync.unasync_dir(str(in_dir), str(out_dir))
    expected1 = "def a():\n    b()\n"
    expected2 = "for item in Iterator:\n    process(item)\n"
    out_file1 = out_dir / "a.py"
    out_file2 = out_dir / "sub" / "b.py"
    assert out_file1.read_text() == expected1
    assert out_file2.read_text() == expected2


def test_unasync_dir_check_failure(tmp_path):
    """Test unasync_dir in check mode fails when discrepancies are found."""
    reset_used_subs()
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    file1 = in_dir / "a.py"
    file1.write_text("async def a():\n    await b()\n")
    out_file1 = out_dir / "a.py"
    out_file1.parent.mkdir(parents=True, exist_ok=True)
    out_file1.write_text("def a():\n    b()  # wrong\n")
    with pytest.raises(SystemExit) as e:
        unasync.unasync_dir(str(in_dir), str(out_dir), check_only=True)
    assert e.value.code == 1


def test_main_unused_subs(monkeypatch):
    """Test that main fails when not all substitution patterns are used."""
    reset_used_subs()
    # Monkey patch unasync_dir to do nothing, thus no substitutions get used.
    monkeypatch.setattr(
        unasync, "unasync_dir", lambda in_dir, out_dir, check_only=False: None
    )
    original_argv = sys.argv
    sys.argv = ["dummy"]
    with pytest.raises(SystemExit) as e:
        unasync.main()
    assert e.value.code == 1
    sys.argv = original_argv
