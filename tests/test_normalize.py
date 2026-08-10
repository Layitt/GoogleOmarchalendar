import unittest
from zoneinfo import ZoneInfo

from omarchy_calendar_sync import normalize

BOGOTA = ZoneInfo("America/Bogota")
CAL = {"id": "cal@example.com", "name": "Personal", "color": "#f83a22"}


def timed(start, end, **extra):
    event = {
        "id": "evt1",
        "status": "confirmed",
        "summary": "Standup",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
    }
    event.update(extra)
    return event


def all_day(start, end, **extra):
    event = {
        "id": "evt2",
        "status": "confirmed",
        "summary": "Holiday",
        "start": {"date": start},
        "end": {"date": end},
    }
    event.update(extra)
    return event


class TestTimedEvents(unittest.TestCase):
    def test_single_day_produces_one_row(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T19:15:00-05:00", "2026-08-10T20:15:00-05:00"), CAL, BOGOTA
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dateKey"], "2026-08-10")
        self.assertFalse(rows[0]["allDay"])
        self.assertEqual(rows[0]["title"], "Standup")
        self.assertEqual(rows[0]["color"], "#f83a22")
        self.assertEqual(rows[0]["calendarName"], "Personal")

    def test_utc_input_is_converted_to_local_day(self):
        # 02:30 UTC on the 11th is 21:30 on the 10th in Bogota.
        rows = normalize.normalize_event(
            timed("2026-08-11T02:30:00Z", "2026-08-11T03:30:00Z"), CAL, BOGOTA
        )
        self.assertEqual([r["dateKey"] for r in rows], ["2026-08-10"])

    def test_event_crossing_midnight_produces_two_rows(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T23:00:00-05:00", "2026-08-11T01:00:00-05:00"), CAL, BOGOTA
        )
        self.assertEqual([r["dateKey"] for r in rows], ["2026-08-10", "2026-08-11"])

    def test_event_ending_exactly_at_midnight_stays_on_one_day(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T22:00:00-05:00", "2026-08-11T00:00:00-05:00"), CAL, BOGOTA
        )
        self.assertEqual([r["dateKey"] for r in rows], ["2026-08-10"])

    def test_rows_of_one_event_share_the_google_id(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T23:00:00-05:00", "2026-08-11T01:00:00-05:00"), CAL, BOGOTA
        )
        self.assertEqual({r["id"] for r in rows}, {"evt1"})


class TestAllDayEvents(unittest.TestCase):
    def test_single_all_day_uses_exclusive_end(self):
        rows = normalize.normalize_event(all_day("2026-08-17", "2026-08-18"), CAL, BOGOTA)
        self.assertEqual([r["dateKey"] for r in rows], ["2026-08-17"])
        self.assertTrue(rows[0]["allDay"])

    def test_three_day_all_day_produces_three_rows(self):
        rows = normalize.normalize_event(all_day("2026-08-17", "2026-08-20"), CAL, BOGOTA)
        self.assertEqual(
            [r["dateKey"] for r in rows], ["2026-08-17", "2026-08-18", "2026-08-19"]
        )


class TestFiltering(unittest.TestCase):
    def test_cancelled_events_are_dropped(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T19:15:00-05:00", "2026-08-10T20:15:00-05:00", status="cancelled"),
            CAL,
            BOGOTA,
        )
        self.assertEqual(rows, [])

    def test_event_without_start_is_dropped(self):
        rows = normalize.normalize_event({"id": "x", "status": "confirmed"}, CAL, BOGOTA)
        self.assertEqual(rows, [])

    def test_missing_summary_falls_back(self):
        event = timed("2026-08-10T19:15:00-05:00", "2026-08-10T20:15:00-05:00")
        del event["summary"]
        rows = normalize.normalize_event(event, CAL, BOGOTA)
        self.assertEqual(rows[0]["title"], normalize.NO_TITLE)

    def test_blank_summary_falls_back(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T19:15:00-05:00", "2026-08-10T20:15:00-05:00", summary="   "),
            CAL,
            BOGOTA,
        )
        self.assertEqual(rows[0]["title"], normalize.NO_TITLE)

    def test_location_defaults_to_empty_string(self):
        rows = normalize.normalize_event(
            timed("2026-08-10T19:15:00-05:00", "2026-08-10T20:15:00-05:00"), CAL, BOGOTA
        )
        self.assertEqual(rows[0]["location"], "")


class TestNormalizeAll(unittest.TestCase):
    def test_flattens_every_event(self):
        events = [
            timed("2026-08-10T19:15:00-05:00", "2026-08-10T20:15:00-05:00"),
            all_day("2026-08-17", "2026-08-19"),
        ]
        rows = normalize.normalize_all(events, CAL, BOGOTA)
        self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
