# Kaseya Center Events Calendar

Auto-updating iOS/macOS/Google calendar subscription for [Kaseya Center](https://www.kaseyacenter.com) in Miami.

A GitHub Actions workflow regenerates `calendar.ics` every morning and commits any changes back to this repo. Subscribe once — your calendar app syncs automatically.

---

## Subscribe

**URL to copy:**

```
https://igoreflor1990.github.io/kaseya-center-calendar/calendar.ics
```

**Tap-to-subscribe link** (swap `https://` for `webcal://` — tapping this URL opens the subscribe dialog directly in iOS Calendar):

```
webcal://igoreflor1990.github.io/kaseya-center-calendar/calendar.ics
```

### iOS steps

1. **Settings → Calendar → Accounts → Add Account → Other → Add Subscribed Calendar**
2. Paste the `https://` URL above → Next → Save.

Or just tap the `webcal://` link above on your iPhone — it will prompt you to subscribe.

> **Content-Type note:** GitHub Pages serves this file with `Content-Type: text/calendar` (verified), which is exactly what calendar clients expect — no extra configuration needed. iOS Calendar, macOS Calendar, and Google Calendar all subscribe to it directly.

---

## What's included

- All concerts, shows, and special events at Kaseya Center
- **Excludes** the recurring "Kaseya Center All-Access Tour" arena-tour listings (toggle with `EXCLUDE_ALL_ACCESS_TOURS = False` in `scrape.py`)
- Covers today through ~13 months out
- Each event: name, tour subtitle, ticket link, detail page URL

---

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scrape.py
# → writes calendar.ics
```

Python 3.9+ required (`zoneinfo` is stdlib from 3.9).

---

## How it works

### Data source

The Carbonhouse platform that powers kaseyacenter.com exposes a JSON endpoint:

```
GET https://www.kaseyacenter.com/events/calendar/{year}/{month}?v=2
```

This is the same endpoint the on-site calendar widget uses. It returns a JSON object mapping `MM-DD-YYYY` keys to HTML snippets (one per event day). `scrape.py` parses the HTML with BeautifulSoup, extracts event name/subtitle/time/URLs, and writes a valid iCalendar file.

Multi-night shows appear as separate entries (one per night), which is correct — each night is its own concert.

### Automation

`.github/workflows/update.yml` runs daily at 08:00 UTC:

1. Installs Python dependencies
2. Runs `python3 scrape.py` → regenerates `calendar.ics`
3. Commits and pushes **only if the file changed**

The commit also counts as repository activity, which prevents GitHub from auto-disabling scheduled workflows after 60 days of inactivity. New events are announced frequently, so real changes occur most days. If the calendar ever stalls (unlikely), manually trigger the workflow from the Actions tab to reset the clock.

### UIDs

Each event's `UID` is a SHA-1 hash of `date + detail_url`, so re-runs update existing calendar entries rather than creating duplicates when subscribers re-sync.

---

## If the site changes

The key things that could break the scraper:

| What changed | Where to fix |
|---|---|
| Carbonhouse endpoint moved | Update `BASE_URL` in `scrape.py` |
| JSON response format changed | Update `fetch_month()` and `parse_month()` |
| HTML snippet structure changed | Update the BeautifulSoup selectors in `parse_month()` |

Run `python3 scrape.py` locally and watch for warnings. A zero-event scrape will exit non-zero and fail the CI run loudly.

---

## Re-enabling the workflow

If the Actions schedule ever gets disabled (GitHub does this after 60 days with no repo activity):

1. Go to your repo → **Actions** tab
2. Click the **"Update Calendar"** workflow on the left
3. Click **"Enable workflow"**

That's it. You can also click **"Run workflow"** to trigger an immediate refresh.
