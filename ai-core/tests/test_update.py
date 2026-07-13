import os
import subprocess
import tempfile
import unittest

from aiosd.update import GitUpdateManager, UpdateManager, make_update_manager


def _git(cwd, *args):
    subprocess.run(["git", "-C", cwd, "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True, text=True)


def _commit(cwd, name, content, msg):
    with open(os.path.join(cwd, name), "w") as fh:
        fh.write(content)
    _git(cwd, "add", ".")
    _git(cwd, "commit", "-m", msg)


class TestGitUpdateManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upstream = os.path.join(self.tmp.name, "upstream")
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(self.upstream)
        _git(self.upstream, "init", "-b", "main")
        _commit(self.upstream, "f.txt", "1\n", "init")
        subprocess.run(["git", "clone", self.upstream, self.work],
                       check=True, capture_output=True, text=True)
        self.mgr = GitUpdateManager(self.work, branch="main")

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_update_manager(self):
        self.assertIsInstance(self.mgr, UpdateManager)

    def test_up_to_date(self):
        st = self.mgr.status()
        self.assertTrue(st["ok"])
        self.assertFalse(st["update_available"])
        self.assertEqual(st["behind"], 0)
        self.assertTrue(st["clean"])

    def test_detects_update(self):
        _commit(self.upstream, "f.txt", "2\n", "upstream change")
        st = self.mgr.status()
        self.assertTrue(st["update_available"])
        self.assertEqual(st["behind"], 1)

    def test_apply_fast_forwards(self):
        _commit(self.upstream, "f.txt", "2\n", "upstream change")
        res = self.mgr.apply()
        self.assertTrue(res["ok"])
        self.assertTrue(res["applied"])
        self.assertFalse(self.mgr.status()["update_available"])  # now current

    def test_apply_up_to_date_is_noop(self):
        res = self.mgr.apply()
        self.assertTrue(res["ok"])
        self.assertFalse(res["applied"])

    def test_apply_refuses_dirty_tree(self):
        _commit(self.upstream, "f.txt", "2\n", "upstream change")
        with open(os.path.join(self.work, "f.txt"), "w") as fh:
            fh.write("local edit\n")  # make the work tree dirty
        res = self.mgr.apply()
        self.assertFalse(res["ok"])
        self.assertIn("uncommitted", res["error"])

    def test_non_repo(self):
        st = GitUpdateManager(self.tmp.name + "/nope").status()
        self.assertFalse(st["ok"])


class TestFactory(unittest.TestCase):
    def test_default_points_at_the_repo(self):
        mgr = make_update_manager()
        self.assertIsInstance(mgr, GitUpdateManager)
        # the AIOS repo itself is a git checkout — status should be readable
        self.assertTrue(os.path.isdir(mgr.repo_dir))


if __name__ == "__main__":
    unittest.main()
