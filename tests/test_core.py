from __future__ import annotations

import os
import unittest

from directory_size_counter.core import walk, DirectorySummary


class _TempTree:
    """Context manager that builds and tears down a temp directory layout."""

    def __init__(self):
        self.root = ""
        self._created = []

    def __enter__(self) -> "_TempTree":
        import tempfile

        self.root = tempfile.mkdtemp()
        return self

    def __exit__(self, *exc) -> None:
        import shutil

        shutil.rmtree(self.root, ignore_errors=True)

    def mkdir(self, rel: str) -> str:
        p = os.path.join(self.root, rel)
        os.makedirs(p, exist_ok=True)
        self._created.append(p)
        return p

    def writefile(self, rel: str, content: bytes) -> str:
        p = os.path.join(self.root, rel)
        d = os.path.dirname(p)
        os.makedirs(d, exist_ok=True)
        with open(p, "wb") as f:
            f.write(content)
        return p


class TestWalkHappyPath(unittest.TestCase):
    def test_flat_single_file(self):
        with _TempTree() as t:
            t.writefile("a.bin", b"hello")
            summary = walk(t.root)
            self.assertEqual(summary.size, 5)
            self.assertEqual(summary.file_count, 1)
            self.assertEqual(summary.subdir_summaries, [])

    def test_nested_directories(self):
        with _TempTree() as t:
            t.writefile("a/f1.txt", b"xx")
            t.writefile("a/b/f2.txt", b"yyyy")
            t.writefile("c/f3.txt", b"z")
            summary = walk(t.root)

            self.assertEqual(summary.file_count, 3)
            self.assertEqual(summary.size, 7)

            by_name = {os.path.basename(s.path): s for s in summary.subdir_summaries}
            self.assertEqual(set(by_name), {"a", "c"})

            self.assertEqual(by_name["a"].file_count, 2)
            self.assertEqual(by_name["a"].size, 6)
            self.assertEqual(by_name["c"].file_count, 1)
            self.assertEqual(by_name["c"].size, 1)

            a = by_name["a"]
            self.assertEqual(len(a.subdir_summaries), 1)
            b = a.subdir_summaries[0]
            self.assertEqual(os.path.basename(b.path), "b")
            self.assertEqual(b.size, 4)
            self.assertEqual(b.file_count, 1)

    def test_empty_directory(self):
        with _TempTree() as t:
            t.mkdir("empty")
            summary = walk(t.root)
            self.assertEqual(summary.size, 0)
            self.assertEqual(summary.file_count, 0)
            self.assertEqual(len(summary.subdir_summaries), 1)
            child = summary.subdir_summaries[0]
            self.assertEqual(child.size, 0)
            self.assertEqual(child.file_count, 0)


class TestWalkEdgeCases(unittest.TestCase):
    def test_hidden_files_are_counted(self):
        with _TempTree() as t:
            t.writefile(".hidden", b"secret")
            t.writefile("sub/.config", b"data")
            summary = walk(t.root)
            self.assertEqual(summary.file_count, 2)
            self.assertEqual(summary.size, 10)

    def test_empty_file_contributes_zero_size_one_count(self):
        with _TempTree() as t:
            t.writefile("empty.txt", b"")
            summary = walk(t.root)
            self.assertEqual(summary.size, 0)
            self.assertEqual(summary.file_count, 1)

    def test_file_at_top_level_and_in_subdir(self):
        with _TempTree() as t:
            t.writefile("top.bin", b"123")
            t.writefile("sub/bot.bin", b"45678")
            summary = walk(t.root)
            self.assertEqual(summary.file_count, 2)
            self.assertEqual(summary.size, 8)
            self.assertEqual(len(summary.subdir_summaries), 1)
            sub = summary.subdir_summaries[0]
            self.assertEqual(sub.size, 5)
            self.assertEqual(sub.file_count, 1)

    def test_path_is_absolute_in_summary(self):
        with _TempTree() as t:
            t.writefile("a.txt", b"hi")
            summary = walk(t.root)
            self.assertTrue(os.path.isabs(summary.path))
            self.assertEqual(summary.path, os.path.abspath(t.root))

    def test_symlink_to_file_not_followed_counts_as_file(self):
        with _TempTree() as t:
            real = t.writefile("real.bin", b"payload")
            link = os.path.join(t.root, "link.bin")
            os.symlink(real, link)
            summary = walk(t.root, follow_symlinks=False)
            # With follow_symlinks=False the symlink is treated neither as a
            # directory nor as a regular file, so it is skipped entirely and
            # contributes nothing to bytes or counts. Only `real.bin` is
            # counted as a file.
            self.assertEqual(summary.file_count, 1)

    def test_symlink_to_directory_not_followed_by_default(self):
        with _TempTree() as t:
            t.writefile("real/file.bin", b"contents")
            real = os.path.join(t.root, "real")
            link = os.path.join(t.root, "link")
            os.symlink(real, link)
            summary = walk(t.root, follow_symlinks=False)
            # The symlink itself is not a directory with follow_symlinks=False,
            # so it contributes neither bytes nor files, and no subdir summary
            # is created for it. Only `real` is listed as a subdir.
            self.assertEqual(summary.file_count, 1)
            names = [os.path.basename(s.path) for s in summary.subdir_summaries]
            self.assertIn("real", names)
            self.assertNotIn("link", names)


class TestWalkErrors(unittest.TestCase):
    def test_nonexistent_path_raises(self):
        with _TempTree() as t:
            missing = os.path.join(t.root, "nope")
            with self.assertRaises(FileNotFoundError):
                walk(missing)

    def test_file_path_raises_not_a_directory(self):
        with _TempTree() as t:
            f = t.writefile("file.txt", b"data")
            with self.assertRaises(NotADirectoryError):
                walk(f)


class TestDirectorySummaryShape(unittest.TestCase):
    def test_summary_is_dataclass_with_expected_fields(self):
        with _TempTree() as t:
            t.writefile("a.txt", b"x")
            summary = walk(t.root)
            self.assertIsInstance(summary, DirectorySummary)
            self.assertIsInstance(summary.size, int)
            self.assertIsInstance(summary.file_count, int)
            self.assertIsInstance(summary.subdir_summaries, list)
            self.assertIsInstance(summary.path, str)


if __name__ == "__main__":
    unittest.main()
