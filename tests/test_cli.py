import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from omarchy_calendar_sync import cli, config, contract, gws

BOGOTA = ZoneInfo("America/Bogota")
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


class FakeGws:
    def __init__(self, calendars=None, events=None, raises=None):
        self._calendars = calendars if calendars is not None else [
            {"id": "a@example.com", "name": "Personal", "color": "#f83a22"}
        ]
        self._events = events if events is not None else [
            {
                "id": "evt1",
                "status": "confirmed",
                "summary": "Standup",
                "start": {"dateTime": "2026-08-10T09:00:00-05:00"},
                "end": {"dateTime": "2026-08-10T09:15:00-05:00"},
            }
        ]
        self._raises = raises

    def check(self):
        return None

    def version(self):
        return (0, 13, 2)

    def calendars(self):
        if self._raises:
            raise self._raises
        return self._calendars

    def events(self, calendar_id, time_min, time_max):
        if self._raises:
            raise self._raises
        return self._events


class TestWriteAtomic(unittest.TestCase):
    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "deeper" / "out.json"
            cli.write_atomic(path, {"hello": "world"})
            self.assertEqual(json.loads(path.read_text()), {"hello": "world"})

    def test_leaves_no_temp_file_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            cli.write_atomic(path, {"hello": "world"})
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["out.json"])


class TestRun(unittest.TestCase):
    def test_writes_a_valid_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "calendar-events.json"
            code = cli.run(FakeGws(), config.DEFAULTS, NOW, out, BOGOTA)
            self.assertEqual(code, 0)
            doc = json.loads(out.read_text())
            self.assertEqual(contract.validate(doc), [])
            self.assertEqual(len(doc["events"]), 1)
            self.assertEqual(doc["events"][0]["title"], "Standup")
            self.assertEqual(doc["events"][0]["dateKey"], "2026-08-10")

    def test_records_source_and_synced_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            cli.run(FakeGws(), config.DEFAULTS, NOW, out, BOGOTA)
            doc = json.loads(out.read_text())
            self.assertEqual(doc["source"], "gws/0.13.2")
            self.assertEqual(doc["syncedAt"], NOW.isoformat())

    def test_excluded_calendar_contributes_nothing(self):
        cfg = dict(config.DEFAULTS)
        cfg["calendars"] = {"include": [], "exclude": ["Personal"]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            cli.run(FakeGws(), cfg, NOW, out, BOGOTA)
            self.assertEqual(json.loads(out.read_text())["events"], [])

    def test_events_are_sorted_by_date_then_start(self):
        events = [
            {
                "id": "later",
                "status": "confirmed",
                "summary": "Later",
                "start": {"dateTime": "2026-08-10T18:00:00-05:00"},
                "end": {"dateTime": "2026-08-10T19:00:00-05:00"},
            },
            {
                "id": "earlier",
                "status": "confirmed",
                "summary": "Earlier",
                "start": {"dateTime": "2026-08-10T08:00:00-05:00"},
                "end": {"dateTime": "2026-08-10T09:00:00-05:00"},
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            cli.run(FakeGws(events=events), config.DEFAULTS, NOW, out, BOGOTA)
            titles = [e["title"] for e in json.loads(out.read_text())["events"]]
            self.assertEqual(titles, ["Earlier", "Later"])

    def test_auth_failure_leaves_previous_file_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            out.write_text('{"version": 1, "events": ["previous"]}')
            code = cli.run(
                FakeGws(raises=gws.GwsAuthError("401: invalid_grant")),
                config.DEFAULTS,
                NOW,
                out,
                BOGOTA,
            )
            self.assertEqual(code, 1)
            self.assertIn("previous", out.read_text())

    def test_api_failure_does_not_create_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            code = cli.run(
                FakeGws(raises=gws.GwsApiError("500: boom")),
                config.DEFAULTS,
                NOW,
                out,
                BOGOTA,
            )
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
