"""
Unit tests for acouachecksum/main.py.

Covers every function that can be tested without a display:
  - md5Checksum2
  - is_cp850
  - arch_filename, arch_object_filename, arch_content, isdir
  - open_archive  (file-based: success and corrupt-file paths)
  - log_message
  - handleArchive (zip, tar, and plain-file paths)

The GUI entry-point (runchecksum, tk_progress_update, add/remove_archiver)
requires a running Tk event loop and is not covered here.

Run with:
    pytest test_main.py -v
"""

import hashlib
import io
import sys
import tarfile
import types
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import py7zr
import pytest
import rarfile

# ---------------------------------------------------------------------------
# Headless import of main.py
# Tkinter is imported at module level in main.py; stub it before import so
# the tests run without a display on CI / headless servers.
# ---------------------------------------------------------------------------

def _stub_tkinter() -> None:
    tk_stub = types.ModuleType("tkinter")
    tk_stub.END = "end"
    tk_stub.MULTIPLE = "multiple"
    for name in ("Label", "Listbox", "Frame", "Button", "Checkbutton", "IntVar", "Tk"):
        setattr(tk_stub, name, MagicMock())

    font_stub = types.ModuleType("tkinter.font")
    font_stub.nametofont = MagicMock()

    ttk_stub = types.ModuleType("tkinter.ttk")
    ttk_stub.Scrollbar = MagicMock()

    sys.modules.setdefault("tkinter", tk_stub)
    sys.modules.setdefault("tkinter.font", font_stub)
    sys.modules.setdefault("tkinter.filedialog", types.ModuleType("tkinter.filedialog"))
    sys.modules.setdefault("tkinter.ttk", ttk_stub)


_stub_tkinter()

sys.path.insert(0, str(Path(__file__).parent))
import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def make_zip(files: dict[str, bytes], dest: Path) -> Path:
    with zipfile.ZipFile(dest, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return dest


def make_tar(files: dict[str, bytes], dest: Path) -> Path:
    with tarfile.open(dest, "w") as tf:
        for name, content in files.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(content)
            tf.addfile(ti, io.BytesIO(content))
    return dest


def make_7z(files: dict[str, bytes], dest: Path) -> Path:
    with py7zr.SevenZipFile(dest, "w") as sz:
        for name, content in files.items():
            sz.writestr(content, name)
    return dest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def error_log(tmp_path):
    """Redirect main.error_file to a temp file for the duration of a test."""
    log = tmp_path / "errors.txt"
    log.touch()
    orig = main.error_file
    main.error_file = str(log)
    yield log
    main.error_file = orig


@pytest.fixture()
def zip_archive(tmp_path):
    """A zip archive containing two files with known content."""
    content = {"a.txt": b"content of file a", "b.txt": b"content of file b"}
    path = make_zip(content, tmp_path / "test.zip")
    return path, content


@pytest.fixture()
def tar_archive(tmp_path):
    """A tar archive containing two files with known content."""
    content = {"a.txt": b"content of file a", "b.txt": b"content of file b"}
    path = make_tar(content, tmp_path / "test.tar")
    return path, content


@pytest.fixture()
def sevenz_archive(tmp_path):
    """A .7z archive containing one file with known content."""
    content = {"a.txt": b"content of file a"}
    path = make_7z(content, tmp_path / "test.7z")
    return path, content


@pytest.fixture()
def null_tk():
    """Stub progress_info and tkroot for handleArchive calls."""
    return MagicMock(), MagicMock()


# ---------------------------------------------------------------------------
# md5Checksum2
# ---------------------------------------------------------------------------

class TestMd5Checksum2:

    def run(self, data: bytes) -> str:
        return main.md5Checksum2(io.BytesIO(data))

    def test_empty_file(self):
        assert self.run(b"") == md5(b"")

    def test_short_content(self):
        data = b"hello world"
        assert self.run(data) == md5(data)

    def test_exactly_one_block(self):
        data = b"X" * (2**20)
        assert self.run(data) == md5(data)

    def test_slightly_over_one_block(self):
        data = b"Y" * (2**20 + 1)
        assert self.run(data) == md5(data)

    def test_multi_block(self):
        data = b"Z" * (2**20 * 3 + 7)
        assert self.run(data) == md5(data)

    def test_binary_content(self):
        data = bytes(range(256)) * 100
        assert self.run(data) == md5(data)

    def test_accepts_real_file(self, tmp_path):
        data = b"real file content"
        f = tmp_path / "data.bin"
        f.write_bytes(data)
        with f.open("rb") as fh:
            assert main.md5Checksum2(fh) == md5(data)

    def test_returns_lowercase_hex(self):
        import re
        assert re.fullmatch(r"[0-9a-f]{32}", self.run(b"test"))


# ---------------------------------------------------------------------------
# is_cp850
# ---------------------------------------------------------------------------

class TestIsCp850:

    def test_pure_ascii_returns_true(self, error_log):
        assert main.is_cp850("hello.txt") is True

    def test_ascii_with_digits_and_symbols_returns_true(self, error_log):
        assert main.is_cp850("dataset_2024-01-01/file (1).csv") is True

    def test_empty_string_returns_true(self, error_log):
        assert main.is_cp850("") is True

    def test_accented_char_returns_false(self, error_log):
        # 'é' encodes to 0x82 in cp850, which is not a valid utf-8 start byte
        assert main.is_cp850("café.txt") is False

    def test_umlaut_returns_false(self, error_log):
        assert main.is_cp850("über.txt") is False

    def test_logs_on_cp850_failure(self, error_log):
        main.is_cp850("été.txt")
        assert error_log.stat().st_size > 0


# ---------------------------------------------------------------------------
# arch_filename
# ---------------------------------------------------------------------------

class TestArchFilename:

    def test_zipfile(self, tmp_path):
        path = make_zip({"a.txt": b"a"}, tmp_path / "test.zip")
        with zipfile.ZipFile(path) as zf:
            assert main.arch_filename(zf) == str(path)

    def test_zipinfo(self, tmp_path):
        path = make_zip({"sub/b.txt": b"b"}, tmp_path / "test.zip")
        with zipfile.ZipFile(path) as zf:
            info = zf.infolist()[0]
            assert main.arch_filename(info) == "sub/b.txt"

    def test_tarfile(self, tmp_path):
        path = make_tar({"c.txt": b"c"}, tmp_path / "test.tar")
        with tarfile.open(path) as tf:
            assert main.arch_filename(tf) == str(path)

    def test_tarinfo(self):
        ti = tarfile.TarInfo(name="dir/d.txt")
        assert main.arch_filename(ti) == "dir/d.txt"


# ---------------------------------------------------------------------------
# arch_object_filename
# ---------------------------------------------------------------------------

class TestArchObjectFilename:

    def test_zipinfo(self, tmp_path):
        path = make_zip({"e.txt": b"e"}, tmp_path / "test.zip")
        with zipfile.ZipFile(path) as zf:
            info = zf.infolist()[0]
            assert main.arch_object_filename(info) == "e.txt"

    def test_tarinfo(self):
        ti = tarfile.TarInfo(name="f.txt")
        assert main.arch_object_filename(ti) == "f.txt"


# ---------------------------------------------------------------------------
# isdir
# ---------------------------------------------------------------------------

class TestIsdir:

    def test_zip_directory_entry_is_dir(self, tmp_path):
        path = tmp_path / "test.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.mkdir("mydir")
            zf.writestr("mydir/file.txt", b"x")
        with zipfile.ZipFile(path) as zf:
            entries = {i.filename: i for i in zf.infolist()}
        assert main.isdir(entries["mydir/"]) is True

    def test_zip_file_entry_is_not_dir(self, tmp_path):
        path = tmp_path / "test.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.mkdir("mydir")
            zf.writestr("mydir/file.txt", b"x")
        with zipfile.ZipFile(path) as zf:
            entries = {i.filename: i for i in zf.infolist()}
        assert main.isdir(entries["mydir/file.txt"]) is False

    def test_tarinfo_directory(self):
        ti = tarfile.TarInfo(name="mydir")
        ti.type = tarfile.DIRTYPE
        assert main.isdir(ti) is True

    def test_tarinfo_regular_file(self):
        ti = tarfile.TarInfo(name="mydir/file.txt")
        ti.type = tarfile.REGTYPE
        assert main.isdir(ti) is False


# ---------------------------------------------------------------------------
# arch_content
# ---------------------------------------------------------------------------

class TestArchContent:

    def test_none_returns_empty_list(self):
        assert main.arch_content(None) == []

    def test_zip(self, zip_archive):
        path, content = zip_archive
        with zipfile.ZipFile(path) as zf:
            result = main.arch_content(zf)
        assert len(result) == len(content)
        assert all(isinstance(e, zipfile.ZipInfo) for e in result)

    def test_tar(self, tar_archive):
        path, content = tar_archive
        with tarfile.open(path) as tf:
            result = main.arch_content(tf)
        assert len(result) == len(content)
        assert all(isinstance(e, tarfile.TarInfo) for e in result)

    def test_7z(self, sevenz_archive):
        path, content = sevenz_archive
        with py7zr.SevenZipFile(path) as sz:
            result = main.arch_content(sz)
        assert len(result) == len(content)


# ---------------------------------------------------------------------------
# open_archive
# ---------------------------------------------------------------------------

class TestOpenArchive:

    def test_open_zip_by_path(self, tmp_path, error_log):
        path = make_zip({"k.txt": b"k"}, tmp_path / "test.zip")
        archname, archive = main.open_archive(path, ".zip")
        assert isinstance(archive, zipfile.ZipFile)
        archive.close()

    def test_open_zip_by_string(self, tmp_path, error_log):
        path = make_zip({"k.txt": b"k"}, tmp_path / "test.zip")
        archname, archive = main.open_archive(str(path), ".zip")
        assert isinstance(archive, zipfile.ZipFile)
        archive.close()

    def test_open_tar_by_path(self, tmp_path, error_log):
        path = make_tar({"l.txt": b"l"}, tmp_path / "test.tar")
        archname, archive = main.open_archive(path, ".tar")
        assert isinstance(archive, tarfile.TarFile)
        archive.close()

    def test_open_7z_by_path(self, tmp_path, error_log):
        path = make_7z({"m.txt": b"m"}, tmp_path / "test.7z")
        archname, archive = main.open_archive(path, ".7z")
        assert isinstance(archive, py7zr.SevenZipFile)
        archive.close()

    def test_corrupt_zip_returns_none_archive(self, tmp_path, error_log):
        path = tmp_path / "bad.zip"
        path.write_bytes(b"not a zip")
        archname, archive = main.open_archive(path, ".zip")
        assert archive is None

    def test_corrupt_tar_returns_none_archive(self, tmp_path, error_log):
        path = tmp_path / "bad.tar"
        path.write_bytes(b"not a tar")
        archname, archive = main.open_archive(path, ".tar")
        assert archive is None

    def test_corrupt_7z_returns_none_archive(self, tmp_path, error_log):
        path = tmp_path / "bad.7z"
        path.write_bytes(b"not a 7z")
        archname, archive = main.open_archive(path, ".7z")
        assert archive is None

    # def test_nested_7z_returns_none_tuple(self, error_log):
    #     ls = MagicMock(spec=py7zr.FileInfo)
    #     ls.filename = "inner.7z"
    #     assert main.open_archive(ls, ".7z", parent=MagicMock()) == (None, None)

    # def test_nested_rar_returns_none_tuple(self, error_log):
    #     ls = MagicMock(spec=rarfile.RarInfo)
    #     ls.filename = "inner.rar"
    #     assert main.open_archive(ls, ".rar", parent=MagicMock()) == (None, None)

    # def test_nested_tar_returns_none_tuple(self, error_log):
    #     ls = MagicMock(spec=tarfile.TarInfo)
    #     ls.name = "inner.tar"
    #     assert main.open_archive(ls, ".tar", parent=MagicMock()) == (None, None)

    # def test_nested_logs_warning(self, error_log):
    #     ls = MagicMock(spec=py7zr.FileInfo)
    #     ls.filename = "inner.7z"
    #     main.open_archive(ls, ".7z", parent=MagicMock())
    #     assert "WARNING" in error_log.read_text()


# ---------------------------------------------------------------------------
# log_message
# ---------------------------------------------------------------------------

class TestLogMessage:

    def test_writes_message_with_newline(self, tmp_path):
        log = tmp_path / "log.txt"
        main.error_file = str(log)
        main.log_message("hello")
        assert log.read_text() == "hello\n"

    def test_writes_multiple_messages(self, tmp_path):
        log = tmp_path / "log.txt"
        main.error_file = str(log)
        main.log_message("hello")
        main.log_message("world")
        assert log.read_text() == "hello\nworld\n"

    def test_appends_to_existing_content(self, tmp_path):
        log = tmp_path / "log.txt"
        log.write_text("existing\n")
        main.error_file = str(log)
        main.log_message("appended")
        assert log.read_text() == "existing\nappended\n"


# ---------------------------------------------------------------------------
# handleArchive — zip
# ---------------------------------------------------------------------------

class TestHandleArchiveZip:

    def test_checksums_all_files(self, zip_archive, null_tk, error_log):
        path, content = zip_archive
        pi, tk = null_tk
        with zipfile.ZipFile(path) as zf:
            md5list, progress = main.handleArchive(
                list(content), zf,
                total_files=len(content), progress=0,
                progress_update_frequency=1,
                progress_info=pi, tkroot=tk,
            )
        result = dict(md5list)
        for name, data in content.items():
            assert result[name] == md5(data)

    def test_progress_increments_per_file(self, zip_archive, null_tk, error_log):
        path, content = zip_archive
        pi, tk = null_tk
        with zipfile.ZipFile(path) as zf:
            _, progress = main.handleArchive(
                list(content), zf,
                total_files=len(content), progress=0,
                progress_update_frequency=1,
                progress_info=pi, tkroot=tk,
            )
        assert progress == len(content)

    def test_progress_accumulates_from_nonzero_start(self, zip_archive, null_tk, error_log):
        path, content = zip_archive
        pi, tk = null_tk
        with zipfile.ZipFile(path) as zf:
            _, progress = main.handleArchive(
                list(content), zf,
                total_files=10, progress=5,
                progress_update_frequency=1,
                progress_info=pi, tkroot=tk,
            )
        assert progress == 5 + len(content)


# ---------------------------------------------------------------------------
# handleArchive — tar
# ---------------------------------------------------------------------------

class TestHandleArchiveTar:

    def test_checksums_all_files(self, tar_archive, null_tk, error_log):
        path, content = tar_archive
        pi, tk = null_tk
        with tarfile.open(path) as tf:
            md5list, _ = main.handleArchive(
                list(content), tf,
                total_files=len(content), progress=0,
                progress_update_frequency=1,
                progress_info=pi, tkroot=tk,
            )
        result = dict(md5list)
        for name, data in content.items():
            assert result[name] == md5(data)

    def test_skips_files_not_in_filelist(self, tmp_path, null_tk, error_log):
        path = make_tar(
            {"wanted.txt": b"yes", "unwanted.txt": b"no"}, tmp_path / "t.tar"
        )
        pi, tk = null_tk
        with tarfile.open(path) as tf:
            md5list, _ = main.handleArchive(
                ["wanted.txt"], tf,
                total_files=1, progress=0,
                progress_update_frequency=1,
                progress_info=pi, tkroot=tk,
            )
        names = [name for name, _ in md5list]
        assert "wanted.txt" in names
        assert "unwanted.txt" not in names


# ---------------------------------------------------------------------------
# handleArchive — plain file (no archive)
# ---------------------------------------------------------------------------

class TestHandleArchivePlainFile:

    def test_checksums_plain_file(self, tmp_path, null_tk, error_log):
        data = b"plain file data"
        f = tmp_path / "data.bin"
        f.write_bytes(data)
        pi, tk = null_tk
        md5list, progress = main.handleArchive(
            str(f), None,
            total_files=1, progress=0,
            progress_update_frequency=1,
            progress_info=pi, tkroot=tk,
        )
        assert len(md5list) == 1
        assert md5list[0][0] == str(f)
        assert md5list[0][1] == md5(data)
        assert progress == 1
