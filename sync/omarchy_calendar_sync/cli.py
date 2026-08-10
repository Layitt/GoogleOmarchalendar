"""Entry point. Orchestrates config, gws, normalization, and the write."""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import config as config_module
from . import contract, normalize
from .gws import Gws, GwsError

EXIT_OK = 0
EXIT_SYNC_FAILED = 1
EXIT_BAD_CONFIG = 2


def write_atomic(path, doc):
    """Write JSON so a reader never observes a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as stream:
            json.dump(doc, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def run(client, cfg, now, out_path, local_tz):
    """Fetch, normalize, write. Returns a process exit code."""
    try:
        client.check()
        calendars = config_module.select_calendars(client.calendars(), cfg)
        time_min, time_max = config_module.window_bounds(cfg, now)

        rows = []
        for calendar in calendars:
            raw = client.events(calendar["id"], time_min, time_max)
            rows.extend(normalize.normalize_all(raw, calendar, local_tz))

        source = "gws/" + ".".join(str(part) for part in client.version())
    except GwsError as error:
        print(f"sync failed: {error}", file=sys.stderr)
        print(
            "if this is an auth error, run: "
            "GOOGLE_WORKSPACE_CLI_CONFIG_DIR=" + str(cfg["profile"]) + " "
            "gws auth login --scopes https://www.googleapis.com/auth/calendar.readonly",
            file=sys.stderr,
        )
        return EXIT_SYNC_FAILED

    rows.sort(key=lambda row: (row["dateKey"], row["start"], row["title"]))
    doc = contract.build_document(rows, now.isoformat(), source)

    problems = contract.validate(doc)
    if problems:
        for problem in problems:
            print(f"refusing to write invalid document: {problem}", file=sys.stderr)
        return EXIT_SYNC_FAILED

    write_atomic(out_path, doc)
    print(f"wrote {len(rows)} rows from {len(calendars)} calendars to {out_path}")
    return EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="omarchy-calendar-sync",
        description="Sync Google Calendar into the Omarchy calendar widget file.",
    )
    parser.add_argument("--config", default=None, help="path to calendar-sync.json")
    parser.add_argument("--out", default=None, help="path to the contract file")
    args = parser.parse_args(argv)

    try:
        cfg = config_module.load(args.config)
    except config_module.ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return EXIT_BAD_CONFIG

    out_path = Path(args.out) if args.out else contract.CONTRACT_PATH
    now = datetime.now(timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo

    return run(Gws(cfg["profile"]), cfg, now, out_path, local_tz)


if __name__ == "__main__":
    sys.exit(main())
