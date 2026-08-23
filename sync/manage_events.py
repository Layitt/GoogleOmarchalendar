#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# Locate config
SYNC_DIR = Path(__file__).resolve().parent
PLUGIN_DIR = SYNC_DIR.parent
CONFIG_PATH = Path.home() / ".config" / "omarchy" / "calendar-sync.json"
STATE_FILE = Path.home() / ".local" / "state" / "omarchy" / "calendar-events.json"

# Resource-bounding limits
MAX_SUBPROCESS_BYTES = 2 * 1024 * 1024  # 2 MB maximum output from gws CLI

def get_gws_info():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("gwsPath", "gws"), data.get("profile", os.path.expanduser("~/.config/gws-omarchy-calendar"))
        except Exception:
            pass
    return "gws", os.path.expanduser("~/.config/gws-omarchy-calendar")

def run_gws_cmd(args, max_bytes=MAX_SUBPROCESS_BYTES):
    gws_bin, profile = get_gws_info()
    env = dict(os.environ)
    env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"] = str(profile)
    
    try:
        proc = subprocess.Popen(
            [gws_bin] + args,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        try:
            raw_stdout, raw_stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return 1, "", "gws subprocess timed out"
            
        if len(raw_stdout) > max_bytes:
            return 1, "", f"gws stdout exceeded {max_bytes} bytes limit"
        if len(raw_stderr) > max_bytes:
            return 1, "", f"gws stderr exceeded {max_bytes} bytes limit"
            
        stdout_text = raw_stdout.decode("utf-8", errors="replace")
        stderr_text = raw_stderr.decode("utf-8", errors="replace")
        return proc.returncode, stdout_text, stderr_text
    except Exception as e:
        return 1, "", str(e)

def trigger_sync():
    sync_script = SYNC_DIR / "omarchy-calendar-sync"
    if sync_script.exists():
        try:
            subprocess.run([str(sync_script)], capture_output=True, timeout=30)
        except Exception:
            pass

def resolve_tz():
    tz_env = os.environ.get("TZ")
    if tz_env:
        try:
            return ZoneInfo(tz_env.lstrip(":"))
        except Exception:
            pass
    try:
        localtime_target = os.readlink("/etc/localtime")
        parts = Path(localtime_target).parts
        if "zoneinfo" in parts:
            name = "/".join(parts[parts.index("zoneinfo") + 1:])
            return ZoneInfo(name)
    except Exception:
        pass
    return datetime.now().astimezone().tzinfo

LOCAL_TZ = resolve_tz()

def add_event(calendar_id, title, date_str, start_time=None, end_time=None, location="", color_id=""):
    calendar_id = calendar_id or "primary"
    body = {
        "summary": str(title).strip()[:500],
        "location": str(location).strip()[:500]
    }
    if color_id:
        body["colorId"] = str(color_id).strip()[:10]
    
    if start_time and ":" in start_time:
        start_time = start_time.strip()
        end_time = (end_time or "").strip()
        
        # Calculate start datetime
        dt_start_naive = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        if isinstance(LOCAL_TZ, ZoneInfo):
            dt_start = dt_start_naive.replace(tzinfo=LOCAL_TZ)
        else:
            dt_start = dt_start_naive.astimezone(LOCAL_TZ)
            
        # Calculate end datetime
        if end_time and ":" in end_time:
            dt_end_naive = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
            if dt_end_naive <= dt_start_naive:
                dt_end_naive = dt_start_naive + timedelta(hours=1)
        else:
            dt_end_naive = dt_start_naive + timedelta(hours=1)
            
        if isinstance(LOCAL_TZ, ZoneInfo):
            dt_end = dt_end_naive.replace(tzinfo=LOCAL_TZ)
        else:
            dt_end = dt_end_naive.astimezone(LOCAL_TZ)
            
        body["start"] = {"dateTime": dt_start.isoformat()}
        body["end"] = {"dateTime": dt_end.isoformat()}
    else:
        # All day event
        d_start = datetime.strptime(date_str, "%Y-%m-%d").date()
        d_end = d_start + timedelta(days=1)
        body["start"] = {"date": d_start.isoformat()}
        body["end"] = {"date": d_end.isoformat()}

    params = {"calendarId": calendar_id}
    code, stdout, stderr = run_gws_cmd([
        "calendar", "events", "insert",
        "--params", json.dumps(params),
        "--json", json.dumps(body)
    ])
    
    if code != 0:
        print(f"Error adding event: {stderr}", file=sys.stderr)
        return False
        
    trigger_sync()
    return True

def delete_event(calendar_id, event_id):
    calendar_id = calendar_id or "primary"
    params = {"calendarId": calendar_id, "eventId": str(event_id).strip()}
    code, stdout, stderr = run_gws_cmd([
        "calendar", "events", "delete",
        "--params", json.dumps(params)
    ])
    
    if code != 0:
        print(f"Error deleting event: {stderr}", file=sys.stderr)
        return False
        
    trigger_sync()
    return True

def update_event(calendar_id, event_id, title, date_str, start_time=None, end_time=None, location="", color_id=""):
    calendar_id = calendar_id or "primary"
    body = {
        "summary": str(title).strip()[:500],
        "location": str(location).strip()[:500]
    }
    if color_id:
        body["colorId"] = str(color_id).strip()[:10]
    
    if start_time and ":" in start_time:
        start_time = start_time.strip()
        end_time = (end_time or "").strip()
        
        dt_start_naive = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        if isinstance(LOCAL_TZ, ZoneInfo):
            dt_start = dt_start_naive.replace(tzinfo=LOCAL_TZ)
        else:
            dt_start = dt_start_naive.astimezone(LOCAL_TZ)
            
        if end_time and ":" in end_time:
            dt_end_naive = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
            if dt_end_naive <= dt_start_naive:
                dt_end_naive = dt_start_naive + timedelta(hours=1)
        else:
            dt_end_naive = dt_start_naive + timedelta(hours=1)
            
        if isinstance(LOCAL_TZ, ZoneInfo):
            dt_end = dt_end_naive.replace(tzinfo=LOCAL_TZ)
        else:
            dt_end = dt_end_naive.astimezone(LOCAL_TZ)
            
        body["start"] = {"dateTime": dt_start.isoformat()}
        body["end"] = {"dateTime": dt_end.isoformat()}
    else:
        d_start = datetime.strptime(date_str, "%Y-%m-%d").date()
        d_end = d_start + timedelta(days=1)
        body["start"] = {"date": d_start.isoformat()}
        body["end"] = {"date": d_end.isoformat()}

    params = {"calendarId": calendar_id, "eventId": str(event_id).strip()}
    code, stdout, stderr = run_gws_cmd([
        "calendar", "events", "patch",
        "--params", json.dumps(params),
        "--json", json.dumps(body)
    ])
    
    if code != 0:
        print(f"Error updating event: {stderr}", file=sys.stderr)
        return False
        
    trigger_sync()
    return True

def list_calendars():
    code, stdout, stderr = run_gws_cmd(["calendar", "calendarList", "list"])
    if code != 0:
        print("[]")
        return
    try:
        data = json.loads(stdout)
        cals = []
        for item in data.get("items", [])[:100]:  # Cap at 100 calendars
            role = item.get("accessRole", "")
            if role in ("owner", "writer"):
                cals.append({
                    "id": item["id"],
                    "name": item.get("summary", item["id"])[:100],
                    "primary": item.get("primary", False),
                    "color": item.get("backgroundColor", "#7bd148")
                })
        print(json.dumps(cals, ensure_ascii=False, indent=2))
    except Exception:
        print("[]")

def main():
    parser = argparse.ArgumentParser(description="Manage Google Calendar events for Omarchy widget")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Add
    p_add = subparsers.add_parser("add")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_add.add_argument("--start-time", default=None, help="HH:MM")
    p_add.add_argument("--end-time", default=None, help="HH:MM")
    p_add.add_argument("--location", default="")
    p_add.add_argument("--calendar-id", default="primary")
    p_add.add_argument("--color-id", default="")
    
    # Delete
    p_del = subparsers.add_parser("delete")
    p_del.add_argument("--calendar-id", required=True)
    p_del.add_argument("--event-id", required=True)
    
    # Update
    p_up = subparsers.add_parser("update")
    p_up.add_argument("--calendar-id", required=True)
    p_up.add_argument("--event-id", required=True)
    p_up.add_argument("--title", required=True)
    p_up.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_up.add_argument("--start-time", default=None, help="HH:MM")
    p_up.add_argument("--end-time", default=None, help="HH:MM")
    p_up.add_argument("--location", default="")
    p_up.add_argument("--color-id", default="")
    
    # List calendars
    subparsers.add_parser("list-calendars")
    
    args = parser.parse_args()
    
    if args.command == "add":
        ok = add_event(args.calendar_id, args.title, args.date, args.start_time, args.end_time, args.location, args.color_id)
        sys.exit(0 if ok else 1)
    elif args.command == "delete":
        ok = delete_event(args.calendar_id, args.event_id)
        sys.exit(0 if ok else 1)
    elif args.command == "update":
        ok = update_event(args.calendar_id, args.event_id, args.title, args.date, args.start_time, args.end_time, args.location, args.color_id)
        sys.exit(0 if ok else 1)
    elif args.command == "list-calendars":
        list_calendars()

if __name__ == "__main__":
    main()
