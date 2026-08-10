"""User configuration for the sync.

Absent config is a valid state: every key has a default, so a first run works
with no file at all.
"""

import json
from datetime import timedelta
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "omarchy" / "calendar-sync.json"

DEFAULTS = {
    "profile": str(Path.home() / ".config" / "gws-omarchy-calendar"),
    "calendars": {"include": [], "exclude": []},
    "window": {"pastDays": 7, "futureDays": 60},
}


class ConfigError(Exception):
    """Raised when the config file exists but cannot be used."""


def load(path=None):
    """Load config, filling in defaults for anything absent."""
    path = Path(path) if path is not None else CONFIG_PATH

    if not path.exists():
        return _merge(DEFAULTS, {})

    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must contain a JSON object")

    return _merge(DEFAULTS, raw)


def _merge(defaults, override):
    """One level of nesting is all this config has, so this stays simple."""
    merged = {}
    for key, fallback in defaults.items():
        value = override.get(key, fallback)
        if isinstance(fallback, dict) and isinstance(value, dict):
            merged[key] = {**fallback, **value}
        else:
            merged[key] = value
    return merged


def select_calendars(calendars, config):
    """Apply the include and exclude lists. Exclude always wins."""
    rules = config.get("calendars") or {}
    include = set(rules.get("include") or [])
    exclude = set(rules.get("exclude") or [])

    selected = []
    for calendar in calendars:
        keys = {calendar["id"], calendar["name"]}
        if keys & exclude:
            continue
        if include and not (keys & include):
            continue
        selected.append(calendar)
    return selected


def window_bounds(config, now):
    """Return RFC3339 timeMin and timeMax for the events query."""
    window = config.get("window") or {}
    past = int(window.get("pastDays", DEFAULTS["window"]["pastDays"]))
    future = int(window.get("futureDays", DEFAULTS["window"]["futureDays"]))
    return (
        (now - timedelta(days=past)).isoformat(),
        (now + timedelta(days=future)).isoformat(),
    )
