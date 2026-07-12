import os
import tempfile
import unittest

from aiosd.platform.services import NullServiceManager
from aiosd.schedule import Scheduler, ScheduleError, wrapper_script


class StubServiceManager(NullServiceManager):
    """Records scheduling calls so we can test the Scheduler policy in isolation."""

    def __init__(self):
        self.scheduled = []
        self.unscheduled = []

    def schedule(self, job):
        self.scheduled.append(job)
        return {"calendar": f"CAL({job.when})", "backend": "stub", "enabled": True}

    def unschedule(self, name):
        self.unscheduled.append(name)
        return True


class TestWrapper(unittest.TestCase):
    def test_wrapper_runs_plain_ask(self):
        w = wrapper_script("/usr/bin/aios", "hello 'world'", "/tmp/x.log")
        self.assertIn("aios", w)
        self.assertIn("ask", w)
        self.assertIn("/tmp/x.log", w)


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.svc = StubServiceManager()
        self.sched = Scheduler(self.svc, data_dir=self.tmp.name, aios_bin="/usr/bin/aios")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_delegates_and_writes_policy_artifacts(self):
        rec = self.sched.add("digest", "daily 08:00", "summarize my unread email")
        # delegated OS registration to the seam
        self.assertEqual(len(self.svc.scheduled), 1)
        self.assertEqual(self.svc.scheduled[0].name, "digest")
        self.assertEqual(self.svc.scheduled[0].command,
                         os.path.join(self.sched.auto_dir, "digest.sh"))
        # calendar comes back from the manager, not decided by the Scheduler
        self.assertEqual(rec["calendar"], "CAL(daily 08:00)")
        # AIOS-owned artifacts: wrapper + index
        self.assertTrue(os.path.exists(os.path.join(self.sched.auto_dir, "digest.sh")))
        self.assertEqual([r["name"] for r in self.sched.list()], ["digest"])

    def test_bad_name_rejected(self):
        with self.assertRaises(ScheduleError):
            self.sched.add("bad name!", "hourly", "hi")

    def test_remove_delegates_and_cleans_up(self):
        self.sched.add("t", "hourly", "tick")
        self.assertTrue(self.sched.remove("t"))
        self.assertEqual(self.svc.unscheduled, ["t"])
        self.assertEqual(self.sched.list(), [])
        self.assertFalse(os.path.exists(os.path.join(self.sched.auto_dir, "t.sh")))
        self.assertFalse(self.sched.remove("t"))  # already gone


if __name__ == "__main__":
    unittest.main()
