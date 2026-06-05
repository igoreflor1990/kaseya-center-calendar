#!/usr/bin/env python3
"""
Kaseya Center calendar scraper + ICS generator.

Data source: https://www.kaseyacenter.com/events/calendar/{year}/{month}?v=2
Returns JSON mapping MM-DD-YYYY → HTML snippet per event day.
"""

import hashlib
import re
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event

# Toggle to include the recurring arena-tour entries
EXCLUDE_ALL_ACCESS_TOURS = True

MIAMI_TZ = ZoneInfo("America/New_York")
BASE_URL = "https://www.kaseyacenter.com/events/calendar/{year}/{month}?v=2"
LOCATION = "Kaseya Center, 601 Biscayne Blvd, Miami, FL 33132"
MONTHS_AHEAD = 13  # current month + 12 more = always ~1 year of events
OUTPUT_FILE = "calendar.ics"


def fetch_month(year: int, month: int) -> dict:
    """Return a {MM-DD-YYYY: html_snippet} dict, or {} when no events exist."""
    url = BASE_URL.format(year=year, month=month)
    resp = requests.get(url, timeout=15, headers={"User-Agent": "KaseyaCenterCalendarBot/1.0"})
    resp.raise_for_status()
    data = resp.json()
    # Empty months return {"events": []} rather than a date-keyed dict
    if isinstance(data, dict) and "events" in data:
        return {}
    return data


def parse_month(data: dict) -> list[dict]:
    events: list[dict] = []
    for date_key, html_frag in sorted(data.items()):
        soup = BeautifulSoup(html_frag, "html.parser")
        wrappers = soup.find_all(class_="event_item_wrapper")
        if not wrappers:
            wrappers = [soup]

        for wrapper in wrappers:
            name_tag = wrapper.find("h3")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)

            # Determine the detail URL (used for dedup UID and as the calendar URL)
            detail_link = wrapper.find("a", href=re.compile(r"/events/detail/"))
            detail_url = detail_link["href"] if detail_link else ""

            if EXCLUDE_ALL_ACCESS_TOURS and (
                "All-Access Tour" in name or "all-access-tour" in detail_url.lower()
            ):
                continue

            subtitle_tag = wrapper.find("h4")
            subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else ""

            time_tag = wrapper.find("span", class_="time")
            raw_time = time_tag.get_text(strip=True).lstrip("- ").strip() if time_tag else ""

            ticket_link = wrapper.find("a", class_=re.compile(r"\btickets\b"))
            ticket_url = ticket_link["href"] if ticket_link else detail_url

            # date_key format: MM-DD-YYYY
            month_n, day_n, year_n = date_key.split("-")
            event_date = date(int(year_n), int(month_n), int(day_n))

            all_day = False
            if raw_time:
                try:
                    t = datetime.strptime(raw_time, "%I:%M %p")
                    start_dt: datetime | date = datetime(
                        event_date.year, event_date.month, event_date.day,
                        t.hour, t.minute, tzinfo=MIAMI_TZ,
                    )
                    end_dt: datetime | date = start_dt + timedelta(hours=3)
                except ValueError:
                    all_day = True
            else:
                all_day = True

            if all_day:
                start_dt = event_date
                end_dt = event_date + timedelta(days=1)  # DTEND is exclusive for DATE events

            # Stable UID: hash of date + detail URL so re-runs update, not duplicate
            uid = hashlib.sha1(f"{date_key}:{detail_url}".encode()).hexdigest() + "@kaseyacenter.com"

            events.append({
                "uid": uid,
                "name": name,
                "subtitle": subtitle,
                "detail_url": detail_url,
                "ticket_url": ticket_url,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "all_day": all_day,
            })
    return events


def build_ics(events: list[dict]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Kaseya Center Events//kaseyacenter.com//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Kaseya Center Events")
    cal.add("x-wr-timezone", "America/New_York")
    # Hint to clients: refresh approximately once a day
    cal.add("x-published-ttl", "PT24H")
    cal.add("refresh-interval;value=duration", "PT24H")

    for ev in sorted(events, key=lambda e: e["start_dt"]):
        vevent = Event()
        vevent.add("uid", ev["uid"])
        vevent.add("summary", ev["name"])

        parts: list[str] = []
        if ev["subtitle"]:
            parts.append(ev["subtitle"])
        if ev["ticket_url"] and ev["ticket_url"] != ev["detail_url"]:
            parts.append(f"Tickets: {ev['ticket_url']}")
        if ev["detail_url"]:
            parts.append(f"More info: {ev['detail_url']}")
        vevent.add("description", "\n".join(parts))

        vevent.add("location", LOCATION)
        if ev["detail_url"]:
            vevent.add("url", ev["detail_url"])

        vevent.add("dtstart", ev["start_dt"])
        vevent.add("dtend", ev["end_dt"])

        cal.add_component(vevent)

    return cal.to_ical()


def main() -> None:
    today = date.today()
    all_events: list[dict] = []

    for offset in range(MONTHS_AHEAD):
        # Advance by offset months from today's month
        total_months = today.month - 1 + offset
        year = today.year + total_months // 12
        month = total_months % 12 + 1

        print(f"  Fetching {year}/{month:02d} ...", file=sys.stderr)
        try:
            data = fetch_month(year, month)
            events = parse_month(data)
            all_events.extend(events)
            time.sleep(0.5)  # Be a polite scraper
        except Exception as exc:
            print(f"  WARNING: failed {year}/{month}: {exc}", file=sys.stderr)

    if not all_events:
        print("ERROR: scraped 0 events — refusing to overwrite calendar.ics", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(all_events)} events collected", file=sys.stderr)

    ics_bytes = build_ics(all_events)

    with open(OUTPUT_FILE, "wb") as fh:
        fh.write(ics_bytes)

    print(f"  Written {OUTPUT_FILE} ({len(ics_bytes):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
