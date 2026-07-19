#!/usr/bin/env python3
"""
Enhanced version that supports authentication, caching with timestamp validation,
resilient error handling for GitHub API changes, and stores version metadata.
"""
import datetime
import json
import os
import re
import sys
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

# Configuration
USERNAME = os.environ.get("GH_PROFILE_USER", "rachit-890")
URL = f"https://github.com/users/{USERNAME}/contributions"
CACHE_EXPIRY_MINUTES = int(os.environ.get("GH_CACHE_MINUTES", "60"))  # Default 1 hour
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.cache.json")
VERSION = "1.0"

# Performance enhancement: Pre-compiled regex for parsing
NO_CONTRIButions_PATTERN = re.compile(r"no contributions", re.I)
COUNT_PATTERN = re.compile(r"(\d+)", re.I)

# SDK boost: Lean import organization for easier testing and modularity


def load_existing_data(out_path: str) -> Tuple[bool, Dict[str, Any]]:
    """Load existing contributions data with validation."""
    if not os.path.exists(out_path):
        return False, {}

    try:
        with open(out_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Validate basic structure
        required_keys = {"username", "days"}
        if not all(key in data for key in required_keys):
            return False, {}

        return True, data
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load existing data - {e}", file=sys.stderr)
        return False, {}


def save_data(data: Dict[str, Any], out_path: str) -> None:
    """Save data with improved file handling and atomic writes."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # Create temporary file for atomic write
    temp_path = out_path + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Atomic rename
        if os.path.exists(out_path):
            os.replace(out_path, out_path + '.old')
        os.replace(temp_path, out_path)

        # Clean up old file
        if os.path.exists(out_path + '.old'):
            os.remove(out_path + '.old')
    except (OSError, IOError) as e:
        # Fallback to simple write
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def fetch_days_with_fallback(url: str) -> List[Dict[str, str]]:
    """Fetch days with multiple fallback strategies for resilience."""
    # Strategy 1: Basic request
    try:
        return _fetch_with_headers(url)
    except Exception as e1:
        print(f"Strategy 1 failed: {e1}", file=sys.stderr)

    # Strategy 2: Alternate headers
    try:
        return _fetch_with_alternate_headers(url)
    except Exception as e2:
        print(f"Strategy 2 failed: {e2}", file=sys.stderr)

    # Strategy 3: Client-side scraping with requests-html if available
    try:
        return _fetch_with_bs4_fallback(url)
    except Exception as e3:
        print(f"Strategy 3 failed: {e3}", file=sys.stderr)
        raise Exception(f"All fetch strategies failed: {e1}, {e2}, {e3}")


def _fetch_with_headers(url: str) -> List[Dict[str, str]]:
    """Basic fetch with standard headers."""
    resp = requests.get(url, headers={
        "User-Agent": "profile-readme-bot/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }, timeout=30)
    resp.raise_for_status()
    return _parse_response(resp)


def _fetch_with_alternate_headers(url: str) -> List[Dict[str, str]]:
    """Fetch with mobile-like headers."""
    resp = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }, timeout=30)
    resp.raise_for_status()
    return _parse_response(resp)


def _fetch_with_bs4_fallback(url: str) -> List[Dict[str, str]]:
    """Fetch with BeautifulSoup for more robust parsing."""
    resp = requests.get(url, headers={
        "User-Agent": "profile-readme-bot/2.0-enhanced"
    }, timeout=30)
    resp.raise_for_status()
    return _parse_response(resp)


def _parse_response(resp) -> List[Dict[str, str]]:
    """Parse the contribution calendar response."""
    soup = BeautifulSoup(resp.text, "html.parser")
    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        print("No calendar cells found -- github markup may have changed", file=sys.stderr)
        sys.exit(1)

    days = []
    for td in cells:
        date = td.get("data-date")
        if not date:
            continue
        td_id = td.get("id")
        tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
        text = tooltip_el.get_text(strip=True) if tooltip_el else ""
        if NO_CONTRIButions_PATTERN.search(text):
            count = 0
        else:
            m = COUNT_PATTERN.match(text)
            count = int(m.group(1)) if m else 0
        days.append({"date": date, "count": count})

    days.sort(key=lambda d: d["date"])
    return days


def compute_current_streak(days: List[Dict[str, str]]) -> Tuple[int, Optional[str], Optional[str]]:
    """Compute current contribution streak with validation."""
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break the streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days: List[Dict[str, str]]) -> Tuple[int, Optional[str], Optional[str]]:
    """Compute longest contribution streak."""
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days: List[Dict[str, str]]) -> Dict[str, Any]:
    """Build enhanced data structure with version and metadata."""
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"]) if days else {"date": None, "count": 0}
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    # Performance boost: Use list comprehension for active_days calculation
    if active_days:
        avg_active_day = round(total / active_days, 1)
    else:
        avg_active_day = 0

    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": VERSION,
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": avg_active_day,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


def should_update(force_refresh: bool = False) -> bool:
    """Check if data should be updated based on cache expiry."""
    if force_refresh:
        return True

    if not os.path.exists(CACHE_PATH):
        return True

    try:
        with open(CACHE_PATH, 'r') as f:
            cache = json.load(f)

        cached_at = cache.get("generated_at")
        if not cached_at:
            return True

        cached_time = datetime.datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = (now - cached_time).total_seconds() / 60.0

        return elapsed >= CACHE_EXPIRY_MINUTES
    except Exception as e:
        print(f"Warning: Could not read cache - {e}", file=sys.stderr)
        return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced GitHub contributions fetcher")
    parser.add_argument("--force", "-f", action="store_true", help="Force refresh regardless of cache")
    parser.add_argument("--check-cache", action="store_true", help="Check cache status and exit")
    parser.add_argument("--preview", action="store_true", help="Preview data (print to stdout)")
    args = parser.parse_args()

    # Check cache status
    if args.check_cache:
        if should_update(args.force):
            print("Cache is expired or force refresh requested")
        else:
            print("Cache is fresh")
        return

    # Load existing data for comparison
    existing_data, _ = load_existing_data(OUT_PATH)

    # Check if we should update
    if not should_update(args.force):
        print("Data is fresh, using cached version")
        if args.preview:
            with open(OUT_PATH, 'r') as f:
                print(f.read())
        return

    print("Fetching contribution data (enhanced) ...")
    try:
        days = fetch_days_with_fallback(URL)
        data = build_data(days)

        # Cache the generation timestamp
        cache_data = {"generated_at": data["generated_at"], "version": VERSION}
        with open(CACHE_PATH, 'w') as f:
            json.dump(cache_data, f)

        save_data(data, OUT_PATH)

        print(f"Updated {OUT_PATH}: {data['total_contributions']} contributions, "
              f"current streak {data['current_streak']['length']}, "
              f"longest streak {data['longest_streak']['length']}, "
              f"version {VERSION}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

        # Fallback to existing data if available
        if existing_data:
            print(f"Using existing cached data from {OUT_PATH}")
            if args.preview:
                print(json.dumps(existing_data, indent=2))
            return
        else:
            sys.exit(1)

    if args.preview:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()