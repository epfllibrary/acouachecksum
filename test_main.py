"""
Unit tests for acouachecksum/main.py.

Covers every function that can be tested without a display:
  - md5Checksum2
  - is_cp850
  - arch_filename, arch_object_filename, arch_content, isdir
  - open_archive  (file-based: success and corrupt-file paths)
  - log_message
  - handleArchive (zip and tar paths)

The GUI entry-point (runchecksum, tk_progress_update, add/remove_archiver)
requires a running Tk event loop and is not covered here.

Run with:
    pytest test_main.py -v
or:
    python -m pytest test_main.py -v
"""

import hashlib
import io
import os
import sys
import tarfile
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import py7zr
import rarfile


# ---------------------------------------------------------------------------
# Headless import of main.py
# Tkinter is imported at module level in main.py; we stub it out before import
# so that the tests run without a display on CI / headless servers.
# ---------------------------------------------------------------------------
def _stub_tkinter():
    """Replace tkinter and its sub-modules with empty stubs."""
    tk_stub = types.ModuleType("tkinter")
    tk_stub.END = "end"
    tk_stub.MULTIPLE = "multiple"
    tk_stub.Label = MagicMock()
    tk_stub.Listbox = MagicMock()
    tk_stub.Frame = MagicMock()
    tk_stub.Button = MagicMock()
    tk_stub.Checkbutton = MagicMock()
    tk_stub.IntVar = MagicMock()
    tk_stub.Tk = MagicMock()

    font_stub = types.ModuleType("tkinter.font")
    font_stub.nametofont = MagicMock()

    filedialog_stub = types.ModuleType("tkinter.filedialog")
    ttk_stub = types.ModuleType("tkinter.ttk")
    ttk_stub.Scrollbar = MagicMock()

    sys.modules.setdefault("tkinter", tk_stub)
    sys.modules.setdefault("tkinter.font", font_stub)
    sys.modules.setdefault("tkinter.filedialog", filedialog_stub)
    sys.modules.setdefault("tkinter.ttk", ttk_stub)


_stub_tkinter()

# Add the directory containing main.py to sys.path.
# Adjust this if running from a different working directory.
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

import main  # noqa: E402  (must come after the stub)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md5(data: bytes) -> str:
    """Reference MD5 using the standard library directly."""
    return hashlib.md5(data).hexdigest()


def _make_zip(files: dict[str, bytes], dest: Path) -> Path:
    """Write a zip archive to *dest* containing {name: content} entries."""
    with zipfile.ZipFile(dest, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return dest


def _make_tar(files: dict[str, bytes], dest: Path) -> Path:
    """Write a tar archive to *dest* containing {name: content} entries."""
    with tarfile.open(dest, "w") as tf:
        for name, content in files.items():
            ti = tarfile.TarInfo(name=name)
            ti.size = len(content)
            tf.addfile(ti, io.BytesIO(content))
    return dest


def _make_7z(files: dict[str, bytes], dest: Path) -> Path:
    """Write a .7z archive to *dest* containing {name: content} entries."""
    with py7zr.SevenZipFile(dest, "w") as sz:
        for name, content in files.items():
            sz.writestr(content, name)
    return dest


def _null_tk():
    """Return stub progress_info and tkroot objects for handleArchive calls."""
    progress_info = MagicMock()
    tkroot = MagicMock()
    return progress_info, tkroot


# ---------------------------------------------------------------------------
# md5Checksum2
# ---------------------------------------------------------------------------

class TestMd5Checksum2(unittest.TestCase):

    def _run(self, data: bytes) -> str:
        return main.md5Checksum2(io.BytesIO(data))

    def test_empty_file(self):
        self.assertEqual(self._run(b""), _md5(b""))

    def test_short_content(self):
        data = b"hello world"
        self.assertEqual(self._run(data), _md5(data))

    def test_exactly_one_block(self):
        """Data that fills exactly one 1 MiB read."""
        data = b"X" * (2**20)
        self.assertEqual(self._run(data), _md5(data))

    def test_slightly_over_one_block(self):
        """Data that spans a block boundary."""
        data = b"Y" * (2**20 + 1)
        self.assertEqual(self._run(data), _md5(data))

    def test_multi_block(self):
        """Data that requires several reads."""
        data = b"Z" * (2**20 * 3 + 7)
        self.assertEqual(self._run(data), _md5(data))

    def test_binary_content(self):
        data = bytes(range(256)) * 100
        self.assertEqual(self._run(data), _md5(data))

    def test_accepts_real_file(self):
        """Works on an actual open file object, not just BytesIO."""
        data = b"real file content"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            fname = f.name
        try:
            with open(fname, "rb") as fh:
                result = main.md5Checksum2(fh)
            self.assertEqual(result, _md5(data))
        finally:
            os.unlink(fname)

    def test_returns_lowercase_hex(self):
        result = self._run(b"test")
        self.assertRegex(result, r"^[0-9a-f]{32}$")


# ---------------------------------------------------------------------------
# is_cp850
# ---------------------------------------------------------------------------

class TestIsCp850(unittest.TestCase):

    def setUp(self):
        # Redirect log_message writes to a temp file so they don't pollute cwd
        self._tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        self._tmp.close()
        self._orig = main.error_file
        main.error_file = self._tmp.name

    def tearDown(self):
        main.error_file = self._orig
        os.unlink(self._tmp.name)

    def test_pure_ascii_returns_true(self):
        # Pure ASCII encodes identically in both cp850 and utf-8
        self.assertTrue(main.is_cp850("hello.txt"))

    def test_pure_ascii_digits_and_symbols(self):
        self.assertTrue(main.is_cp850("dataset_2024-01-01/file (1).csv"))

    def test_accented_char_returns_false(self):
        # 'é' encodes to 0x82 in cp850, which is not a valid utf-8 byte
        self.assertFalse(main.is_cp850("café.txt"))

    def test_umlaut_returns_false(self):
        self.assertFalse(main.is_cp850("über.txt"))

    def test_empty_string_returns_true(self):
        self.assertTrue(main.is_cp850(""))

    def test_logs_on_failure(self):
        main.is_cp850("été.txt")
        with open(self._tmp.name) as f:
            content = f.read()
        # Some error text should have been written
        self.assertTrue(len(content) > 0)


# ---------------------------------------------------------------------------
# arch_filename
# ---------------------------------------------------------------------------

class TestArchFilename(unittest.TestCase):

    def test_zipfile(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"a.txt": b"a"}, Path(fname))
            with zipfile.ZipFile(fname) as zf:
                self.assertEqual(main.arch_filename(zf), fname)
        finally:
            os.unlink(fname)

    def test_zipinfo(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"sub/b.txt": b"b"}, Path(fname))
            with zipfile.ZipFile(fname) as zf:
                info = zf.infolist()[0]
                self.assertEqual(main.arch_filename(info), "sub/b.txt")
        finally:
            os.unlink(fname)

    def test_tarfile(self):
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            fname = f.name
        try:
            _make_tar({"c.txt": b"c"}, Path(fname))
            with tarfile.open(fname) as tf:
                self.assertEqual(main.arch_filename(tf), fname)
        finally:
            os.unlink(fname)

    def test_tarinfo(self):
        ti = tarfile.TarInfo(name="dir/d.txt")
        self.assertEqual(main.arch_filename(ti), "dir/d.txt")


# ---------------------------------------------------------------------------
# arch_object_filename
# ---------------------------------------------------------------------------

class TestArchObjectFilename(unittest.TestCase):

    def test_zipinfo(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"e.txt": b"e"}, Path(fname))
            with zipfile.ZipFile(fname) as zf:
                info = zf.infolist()[0]
                self.assertEqual(main.arch_object_filename(info), "e.txt")
        finally:
            os.unlink(fname)

    def test_tarinfo(self):
        ti = tarfile.TarInfo(name="f.txt")
        self.assertEqual(main.arch_object_filename(ti), "f.txt")


# ---------------------------------------------------------------------------
# isdir
# ---------------------------------------------------------------------------

class TestIsdir(unittest.TestCase):

    def test_zip_directory_entry(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            with zipfile.ZipFile(fname, "w") as zf:
                # zipfile represents directories with a trailing slash
                zf.mkdir("mydir")
                zf.writestr("mydir/file.txt", b"x")
            with zipfile.ZipFile(fname) as zf:
                entries = {i.filename: i for i in zf.infolist()}
                self.assertTrue(main.isdir(entries["mydir/"]))
                self.assertFalse(main.isdir(entries["mydir/file.txt"]))
        finally:
            os.unlink(fname)

    def test_tarinfo_directory(self):
        ti_dir = tarfile.TarInfo(name="mydir")
        ti_dir.type = tarfile.DIRTYPE
        ti_file = tarfile.TarInfo(name="mydir/file.txt")
        ti_file.type = tarfile.REGTYPE
        self.assertTrue(main.isdir(ti_dir))
        self.assertFalse(main.isdir(ti_file))


# ---------------------------------------------------------------------------
# arch_content
# ---------------------------------------------------------------------------

class TestArchContent(unittest.TestCase):

    def test_none_returns_empty_list(self):
        self.assertEqual(main.arch_content(None), [])

    def test_zip(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"g.txt": b"g", "h.txt": b"h"}, Path(fname))
            with zipfile.ZipFile(fname) as zf:
                result = main.arch_content(zf)
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], zipfile.ZipInfo)
        finally:
            os.unlink(fname)

    def test_tar(self):
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            fname = f.name
        try:
            _make_tar({"i.txt": b"i"}, Path(fname))
            with tarfile.open(fname) as tf:
                result = main.arch_content(tf)
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], tarfile.TarInfo)
        finally:
            os.unlink(fname)

    def test_7z(self):
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as f:
            fname = f.name
        try:
            _make_7z({"j.txt": b"j"}, Path(fname))
            with py7zr.SevenZipFile(fname) as sz:
                result = main.arch_content(sz)
            self.assertEqual(len(result), 1)
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# open_archive
# ---------------------------------------------------------------------------

class TestOpenArchive(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        self._tmp.close()
        self._orig_err = main.error_file
        main.error_file = self._tmp.name

    def tearDown(self):
        main.error_file = self._orig_err
        os.unlink(self._tmp.name)

    def test_open_zip_by_path(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"k.txt": b"k"}, Path(fname))
            archname, archive = main.open_archive(Path(fname), ".zip")
            self.assertIsNotNone(archive)
            self.assertIsInstance(archive, zipfile.ZipFile)
            archive.close()
        finally:
            os.unlink(fname)

    def test_open_tar_by_path(self):
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            fname = f.name
        try:
            _make_tar({"l.txt": b"l"}, Path(fname))
            archname, archive = main.open_archive(Path(fname), ".tar")
            self.assertIsNotNone(archive)
            self.assertIsInstance(archive, tarfile.TarFile)
            archive.close()
        finally:
            os.unlink(fname)

    def test_open_7z_by_path(self):
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as f:
            fname = f.name
        try:
            _make_7z({"m.txt": b"m"}, Path(fname))
            archname, archive = main.open_archive(Path(fname), ".7z")
            self.assertIsNotNone(archive)
            self.assertIsInstance(archive, py7zr.SevenZipFile)
            archive.close()
        finally:
            os.unlink(fname)

    def test_open_zip_by_string_path(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"n.txt": b"n"}, Path(fname))
            archname, archive = main.open_archive(fname, ".zip")
            self.assertIsNotNone(archive)
            archive.close()
        finally:
            os.unlink(fname)

    def test_corrupt_zip_returns_none_archive(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            f.write(b"this is not a zip file")
            fname = f.name
        try:
            archname, archive = main.open_archive(Path(fname), ".zip")
            self.assertIsNone(archive)
            self.assertEqual(archname, fname)
        finally:
            os.unlink(fname)

    def test_corrupt_tar_returns_none_archive(self):
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            f.write(b"this is not a tar file")
            fname = f.name
        try:
            archname, archive = main.open_archive(Path(fname), ".tar")
            self.assertIsNone(archive)
        finally:
            os.unlink(fname)

    def test_corrupt_7z_returns_none_archive(self):
        with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as f:
            f.write(b"this is not a 7z file")
            fname = f.name
        try:
            archname, archive = main.open_archive(Path(fname), ".7z")
            self.assertIsNone(archive)
        finally:
            os.unlink(fname)

    # TODO implement proper tests for nested archives
    # def test_nested_7z_info_returns_none_tuple(self):
    #     """Nested .7z sub-archives are not supported; must return (None, None)."""
    #     dummy_ls = MagicMock(spec=py7zr.FileInfo)
    #     dummy_ls.filename = "inner.7z"
    #     parent = MagicMock()
    #     result = main.open_archive(dummy_ls, ".7z", parent=parent)
    #     self.assertEqual(result, (None, None))

    # def test_nested_rarinfo_returns_none_tuple(self):
    #     dummy_ls = MagicMock(spec=rarfile.RarInfo)
    #     dummy_ls.filename = "inner.rar"
    #     parent = MagicMock()
    #     result = main.open_archive(dummy_ls, ".rar", parent=parent)
    #     self.assertEqual(result, (None, None))

    # def test_nested_tarinfo_returns_none_tuple(self):
    #     dummy_ls = MagicMock(spec=tarfile.TarInfo)
    #     dummy_ls.name = "inner.tar"
    #     parent = MagicMock()
    #     result = main.open_archive(dummy_ls, ".tar", parent=parent)
    #     self.assertEqual(result, (None, None))


# ---------------------------------------------------------------------------
# log_message
# ---------------------------------------------------------------------------

class TestLogMessage(unittest.TestCase):

    def test_writes_message_with_newline(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            fname = f.name
        main_orig = main.error_file
        main.error_file = fname
        try:
            main.log_message("hello")
            main.log_message("world")
            with open(fname) as f:
                lines = f.readlines()
            self.assertEqual(lines, ["hello\n", "world\n"])
        finally:
            main.error_file = main_orig
            os.unlink(fname)

    def test_appends_to_existing_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            f.write("existing\n")
            fname = f.name
        main_orig = main.error_file
        main.error_file = fname
        try:
            main.log_message("appended")
            with open(fname) as f:
                content = f.read()
            self.assertEqual(content, "existing\nappended\n")
        finally:
            main.error_file = main_orig
            os.unlink(fname)


# ---------------------------------------------------------------------------
# handleArchive — zip path
# ---------------------------------------------------------------------------

class TestHandleArchiveZip(unittest.TestCase):

    def setUp(self):
        self._tmp_err = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        self._tmp_err.close()
        self._orig_err = main.error_file
        main.error_file = self._tmp_err.name

    def tearDown(self):
        main.error_file = self._orig_err
        os.unlink(self._tmp_err.name)

    def test_checksums_files_in_zip(self):
        content_a = b"content of file a"
        content_b = b"content of file b"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"a.txt": content_a, "b.txt": content_b}, Path(fname))
            pi, tk = _null_tk()
            with zipfile.ZipFile(fname) as zf:
                md5list, progress = main.handleArchive(
                    ["a.txt", "b.txt"], zf,
                    total_files=2, progress=0,
                    progress_update_frequency=1,
                    progress_info=pi, tkroot=tk,
                )
            result = dict(md5list)
            self.assertEqual(result["a.txt"], _md5(content_a))
            self.assertEqual(result["b.txt"], _md5(content_b))
            self.assertEqual(progress, 2)
        finally:
            os.unlink(fname)

    def test_progress_increments(self):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
            fname = f.name
        try:
            _make_zip({"x.txt": b"x", "y.txt": b"y", "z.txt": b"z"}, Path(fname))
            pi, tk = _null_tk()
            with zipfile.ZipFile(fname) as zf:
                _, progress = main.handleArchive(
                    ["x.txt", "y.txt", "z.txt"], zf,
                    total_files=3, progress=0,
                    progress_update_frequency=1,
                    progress_info=pi, tkroot=tk,
                )
            self.assertEqual(progress, 3)
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# handleArchive — tar path
# ---------------------------------------------------------------------------

class TestHandleArchiveTar(unittest.TestCase):

    def setUp(self):
        self._tmp_err = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        self._tmp_err.close()
        self._orig_err = main.error_file
        main.error_file = self._tmp_err.name

    def tearDown(self):
        main.error_file = self._orig_err
        os.unlink(self._tmp_err.name)

    def test_checksums_files_in_tar(self):
        content = b"tar file content"
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            fname = f.name
        try:
            _make_tar({"doc.txt": content}, Path(fname))
            pi, tk = _null_tk()
            with tarfile.open(fname) as tf:
                md5list, progress = main.handleArchive(
                    ["doc.txt"], tf,
                    total_files=1, progress=0,
                    progress_update_frequency=1,
                    progress_info=pi, tkroot=tk,
                )
            result = dict(md5list)
            self.assertEqual(result["doc.txt"], _md5(content))
            self.assertEqual(progress, 1)
        finally:
            os.unlink(fname)

    def test_skips_files_not_in_filelist(self):
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as f:
            fname = f.name
        try:
            _make_tar({"wanted.txt": b"yes", "unwanted.txt": b"no"}, Path(fname))
            pi, tk = _null_tk()
            with tarfile.open(fname) as tf:
                md5list, _ = main.handleArchive(
                    ["wanted.txt"], tf,
                    total_files=1, progress=0,
                    progress_update_frequency=1,
                    progress_info=pi, tkroot=tk,
                )
            names = [name for name, _ in md5list]
            self.assertIn("wanted.txt", names)
            self.assertNotIn("unwanted.txt", names)
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# handleArchive — no archive (plain file) path
# ---------------------------------------------------------------------------

class TestHandleArchiveNoArchive(unittest.TestCase):

    def setUp(self):
        self._tmp_err = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        self._tmp_err.close()
        self._orig_err = main.error_file
        main.error_file = self._tmp_err.name

    def tearDown(self):
        main.error_file = self._orig_err
        os.unlink(self._tmp_err.name)

    def test_plain_file_checksum(self):
        content = b"plain file data"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            fname = f.name
        try:
            pi, tk = _null_tk()
            md5list, progress = main.handleArchive(
                fname, None,
                total_files=1, progress=0,
                progress_update_frequency=1,
                progress_info=pi, tkroot=tk,
            )
            self.assertEqual(len(md5list), 1)
            self.assertEqual(md5list[0][0], fname)
            self.assertEqual(md5list[0][1], _md5(content))
            self.assertEqual(progress, 1)
        finally:
            os.unlink(fname)


if __name__ == "__main__":
    unittest.main()
