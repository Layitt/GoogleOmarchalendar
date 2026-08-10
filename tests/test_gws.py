import json
import unittest
from pathlib import Path

from omarchy_calendar_sync import gws

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text()


class FakeRunner:
    """Records argv and replays canned responses keyed by a marker in argv."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, argv, env):
        self.calls.append((argv, env))
        for marker, response in self.responses.items():
            if marker in argv:
                return response
        raise AssertionError(f"unexpected argv: {argv}")


class TestVersion(unittest.TestCase):
    def test_parses_version_line(self):
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"--version": (0, "gws 0.13.2\nnote\n", "")}))
        self.assertEqual(client.version(), (0, 13, 2))

    def test_missing_binary_raises(self):
        def runner(argv, env):
            raise FileNotFoundError("gws")

        with self.assertRaises(gws.GwsMissing):
            gws.Gws("/tmp/profile", runner=runner).check()

    def test_old_version_raises(self):
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"--version": (0, "gws 0.12.0\n", "")}))
        with self.assertRaises(gws.GwsTooOld):
            client.check()

    def test_current_version_passes(self):
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"--version": (0, "gws 0.13.2\n", "")}))
        client.check()


class TestCalendars(unittest.TestCase):
    def test_maps_to_id_name_color(self):
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"calendarList": (0, fixture("google-calendars.json"), "keyring noise")}))
        calendars = client.calendars()
        self.assertEqual(
            calendars,
            [
                {"id": "a@example.com", "name": "Personal", "color": "#f83a22"},
                {"id": "b@example.com", "name": "Phases of the Moon", "color": "#fad165"},
            ],
        )

    def test_missing_color_falls_back(self):
        body = json.dumps({"items": [{"id": "x", "summary": "No Color"}]})
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"calendarList": (0, body, "")}))
        self.assertEqual(client.calendars()[0]["color"], gws.FALLBACK_COLOR)

    def test_missing_summary_falls_back_to_id(self):
        body = json.dumps({"items": [{"id": "x@example.com", "backgroundColor": "#ffffff"}]})
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"calendarList": (0, body, "")}))
        self.assertEqual(client.calendars()[0]["name"], "x@example.com")


class TestEvents(unittest.TestCase):
    def test_returns_raw_items(self):
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"events": (0, fixture("google-events.json"), "")}))
        items = client.events("a@example.com", "2026-08-01T00:00:00+00:00", "2026-09-01T00:00:00+00:00")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "evt1")

    def test_passes_single_events_and_window(self):
        runner = FakeRunner({"events": (0, fixture("google-events.json"), "")})
        gws.Gws("/tmp/profile", runner=runner).events("a@example.com", "MIN", "MAX")
        argv = runner.calls[0][0]
        params = json.loads(argv[argv.index("--params") + 1])
        self.assertTrue(params["singleEvents"])
        self.assertEqual(params["orderBy"], "startTime")
        self.assertEqual(params["timeMin"], "MIN")
        self.assertEqual(params["timeMax"], "MAX")
        self.assertEqual(params["calendarId"], "a@example.com")

    def test_sets_profile_env_var(self):
        runner = FakeRunner({"events": (0, fixture("google-events.json"), "")})
        gws.Gws("/my/profile", runner=runner).events("a", "MIN", "MAX")
        env = runner.calls[0][1]
        self.assertEqual(env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"], "/my/profile")


class TestErrors(unittest.TestCase):
    def test_401_raises_auth_error(self):
        body = json.dumps({"error": {"code": 401, "message": "invalid_grant"}})
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"events": (0, body, "")}))
        with self.assertRaises(gws.GwsAuthError):
            client.events("a", "MIN", "MAX")

    def test_403_raises_auth_error(self):
        body = json.dumps({"error": {"code": 403, "message": "insufficient scopes"}})
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"events": (0, body, "")}))
        with self.assertRaises(gws.GwsAuthError):
            client.events("a", "MIN", "MAX")

    def test_other_error_code_raises_api_error(self):
        body = json.dumps({"error": {"code": 500, "message": "boom"}})
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"events": (0, body, "")}))
        with self.assertRaises(gws.GwsApiError):
            client.events("a", "MIN", "MAX")

    def test_unparseable_stdout_raises_api_error(self):
        client = gws.Gws("/tmp/profile", runner=FakeRunner({"events": (0, "not json", "")}))
        with self.assertRaises(gws.GwsApiError):
            client.events("a", "MIN", "MAX")


if __name__ == "__main__":
    unittest.main()
