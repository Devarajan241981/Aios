import os
import tempfile
import unittest

from aiosd.schedule import (
    Scheduler,
    ScheduleError,
    service_unit,
    timer_unit,
    to_oncalendar,
    wrapper_script,
)


class TestOnCalendar(unittest.TestCase):
    def test_shortcuts(self):
        self.assertEqual(to_oncalendar("hourly"), "hourly")
        self.assertEqual(to_oncalendar("Daily"), "daily")

    def test_daily_time(self):
        self.assertEqual(to_oncalendar("daily 08:00"), "*-*-* 08:00:00")

    def test_bare_time(self):
        self.assertEqual(to_oncalendar("7:5"), "*-*-* 07:05:00")

    def test_weekday_time(self):
        self.assertEqual(to_oncalendar("mon 09:30"), "Mon *-*-* 09:30:00")

    def test_passthrough(self):
        self.assertEqual(to_oncalendar("*-*-* 12:00:00"), "*-*-* 12:00:00")


class TestUnitGenerators(unittest.TestCase):
    def test_units_and_wrapper(self):
        self.assertIn("OnCalendar=daily", timer_unit("x", "daily"))
        self.assertIn("WantedBy=timers.target", timer_unit("x", "daily"))
        self.assertIn("ExecStart=/w.sh", service_unit("x", "/w.sh"))
        w = wrapper_script("/usr/bin/aios", "hello 'world'", "/tmp/x.log")
        self.assertIn("aios", w)
        self.assertIn("ask", w)
        self.assertIn("/tmp/x.log", w)


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sched = Scheduler(
            unit_dir=os.path.join(self.tmp.name, "units"),
            data_dir=os.path.join(self.tmp.name, "data"),
            aios_bin="/usr/bin/aios",
            run_systemctl=False,  # don't touch the real systemd
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_creates_files_and_index(self):
        rec = self.sched.add("digest", "daily 08:00", "summarize my unread email")
        self.assertEqual(rec["oncalendar"], "*-*-* 08:00:00")
        self.assertTrue(os.path.exists(os.path.join(self.sched.unit_dir, "aios-digest.timer")))
        self.assertTrue(os.path.exists(os.path.join(self.sched.unit_dir, "aios-digest.service")))
        self.assertTrue(os.path.exists(os.path.join(self.sched.auto_dir, "digest.sh")))
        self.assertEqual([r["name"] for r in self.sched.list()], ["digest"])

    def test_bad_name_rejected(self):
        with self.assertRaises(ScheduleError):
            self.sched.add("bad name!", "hourly", "hi")

    def test_remove(self):
        self.sched.add("t", "hourly", "tick")
        self.assertTrue(self.sched.remove("t"))
        self.assertEqual(self.sched.list(), [])
        self.assertFalse(os.path.exists(os.path.join(self.sched.unit_dir, "aios-t.timer")))
        self.assertFalse(self.sched.remove("t"))  # already gone


if __name__ == "__main__":
    unittest.main()
