import os
import tempfile
import unittest

from aiosd.platform.services import (
    NullServiceManager,
    ScheduledJob,
    ServiceManager,
    SystemdServiceManager,
    current_service_manager,
    service_unit,
    timer_unit,
    to_oncalendar,
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
    def test_service_and_timer(self):
        svc = service_unit("x", "/w.sh", "desc")
        self.assertIn("ExecStart=/w.sh", svc)
        self.assertIn("Description=desc", svc)
        tmr = timer_unit("x", "daily")
        self.assertIn("OnCalendar=daily", tmr)
        self.assertIn("WantedBy=timers.target", tmr)


class TestSystemdServiceManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # systemctl="" => do not touch the real system, but still write unit files
        self.mgr = SystemdServiceManager(unit_dir=self.tmp.name, systemctl="")

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_a_service_manager(self):
        self.assertIsInstance(self.mgr, ServiceManager)
        self.assertFalse(self.mgr.available)

    def test_schedule_writes_units(self):
        result = self.mgr.schedule(ScheduledJob("digest", "daily 08:00", "/x/digest.sh"))
        self.assertEqual(result["calendar"], "*-*-* 08:00:00")
        self.assertEqual(result["backend"], "systemd")
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "aios-digest.timer")))
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "aios-digest.service")))

    def test_unschedule(self):
        self.mgr.schedule(ScheduledJob("t", "hourly", "/x/t.sh"))
        self.assertTrue(self.mgr.unschedule("t"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "aios-t.timer")))
        self.assertFalse(self.mgr.unschedule("t"))  # already gone

    def test_lifecycle_noop_without_systemctl(self):
        self.assertFalse(self.mgr.start("aiosd.service"))
        self.assertEqual(self.mgr.is_active("aiosd.service"), "unknown")
        self.mgr.reload()  # must not raise


class TestNullServiceManager(unittest.TestCase):
    def test_all_noop(self):
        m = NullServiceManager()
        self.assertFalse(m.available)
        self.assertFalse(m.start("x"))
        self.assertEqual(m.is_active("x"), "unknown")
        self.assertFalse(m.unschedule("x"))
        self.assertEqual(m.schedule(ScheduledJob("x", "hourly", "/c"))["backend"], "none")


class TestFactory(unittest.TestCase):
    def test_returns_service_manager(self):
        self.assertIsInstance(current_service_manager(unit_dir="/tmp/x"), ServiceManager)


if __name__ == "__main__":
    unittest.main()
