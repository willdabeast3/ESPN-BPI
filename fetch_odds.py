"""Fetch Vegas spread data and append to existing season CSVs.

For each season CSV, re-queries ESPN's scoreboard API to get event IDs,
then fetches the odds endpoint for each game. Adds a VEGAS_SPREAD column
matching the PRED_SPREAD convention (positive = team is favored).

Run: python fetch_odds.py
"""
import datetime
import glob
import json
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

SCOREBOARD_URL = (
    'https://site.api.espn.com/apis/site/v2/sports/basketball/'
    'mens-college-basketball/scoreboard?dates={date}&groups=50&limit=200'
)
ODDS_URL = (
    'https://sports.core.api.espn.com/v2/sports/basketball/leagues/'
    'mens-college-basketball/events/{eid}/competitions/{eid}/odds'
)


def _fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception:
        return None


def _get_odds_for_date(date_str):
    """Fetch scoreboard + odds for one query date.

    Returns list of dicts with keys: game_date (UTC from comp['date'][:10]),
    home_team, away_team, home_vegas_spread.
    """
    scoreboard = _fetch_json(SCOREBOARD_URL.format(date=date_str))
    if not scoreboard:
        return []

    event_info = []
    for event in scoreboard.get('events', []):
        eid = event.get('id')
        comp = event.get('competitions', [{}])[0]
        if comp.get('status', {}).get('type', {}).get('name') != 'STATUS_FINAL':
            continue

        # Use the same UTC date extraction as the original fetch (comp['date'][:10])
        game_date = comp['date'][:10]

        home_team = away_team = None
        for c in comp['competitors']:
            if c['homeAway'] == 'home':
                home_team = c['team']['displayName']
            else:
                away_team = c['team']['displayName']

        if home_team and away_team and eid:
            event_info.append((eid, game_date, home_team, away_team))

    if not event_info:
        return []

    def fetch_one(info):
        eid, game_date, home, away = info
        odds = _fetch_json(ODDS_URL.format(eid=eid))
        if not odds:
            return None
        items = odds.get('items', [])
        if not items:
            return None
        spread = items[0].get('spread')
        if spread is None:
            return None
        return {
            'game_date': game_date,
            'home_team': home,
            'away_team': away,
            'home_vegas_spread': float(spread),
        }

    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(fetch_one, info) for info in event_info]
        for future in as_completed(futures):
            r = future.result()
            if r is not None:
                results.append(r)

    return results


def fetch_odds_for_season(season_end_year, verbose=True):
    """Fetch Vegas spreads for all games in a season.

    Returns dict mapping (game_date_utc, team_name) -> vegas_spread.
    The game_date uses the same UTC extraction as the original data pipeline
    (comp['date'][:10]) so it matches the DATE column in the CSV.
    """
    start = datetime.date(season_end_year - 1, 11, 1)
    end = datetime.date(season_end_year, 4, 15)
    count = (end - start).days + 1
    dates = [(start + datetime.timedelta(days=i)).strftime('%Y%m%d') for i in range(count)]

    all_results = []
    completed = 0

    # Low concurrency to avoid rate limiting on the odds API
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(_get_odds_for_date, d): d for d in dates}
        for future in as_completed(futures):
            all_results.extend(future.result())
            completed += 1
            if verbose and completed % 20 == 0:
                print(f'  {completed}/{len(dates)} days...', flush=True)

    if verbose:
        print(f'  {len(dates)}/{len(dates)} done. {len(all_results)} games with odds.')

    # Build lookup: (game_date, team) -> vegas_spread from that team's perspective
    # API spread: negative = home favored
    # VEGAS_SPREAD convention: positive = team is favored (matches PRED_SPREAD)
    lookup = {}
    for r in all_results:
        date = r['game_date']
        home_spread = r['home_vegas_spread']
        lookup[(date, r['home_team'])] = -home_spread   # flip: home fav -> positive
        lookup[(date, r['away_team'])] = home_spread     # away gets opposite

    return lookup


def add_odds_to_csv(path, verbose=True):
    """Add VEGAS_SPREAD column to an existing season CSV."""
    df = pd.read_csv(path)
    df['DATE'] = pd.to_datetime(df['DATE'])

    label = path.split('season_')[1].replace('.csv', '').replace('_', '-')
    year = int(label.split('-')[0]) + 1

    # Check if already done (skip if >50% coverage)
    if 'VEGAS_SPREAD' in df.columns:
        existing = (df['VEGAS_SPREAD'] != 0).sum() // 2
        total = len(df) // 2
        if existing > total * 0.5:
            print(f'{label}: already has {existing}/{total} Vegas spreads -- skipping')
            return existing

    print(f'{label}: fetching odds...')
    lookup = fetch_odds_for_season(year, verbose=verbose)

    if not lookup:
        print(f'  No odds data available for this season')
        if 'VEGAS_SPREAD' not in df.columns:
            df['VEGAS_SPREAD'] = 0.0
            df.to_csv(path, index=False)
        return 0

    # Map onto existing DataFrame
    def get_vegas(row):
        date_str = row['DATE'].strftime('%Y-%m-%d')
        return lookup.get((date_str, row['TEAM']), 0.0)

    df['VEGAS_SPREAD'] = df.apply(get_vegas, axis=1)
    matched = (df['VEGAS_SPREAD'] != 0).sum() // 2
    total = len(df) // 2
    print(f'  Matched {matched}/{total} games with Vegas spreads')
    df.to_csv(path, index=False)
    print(f'  Saved to {path}')
    return matched


if __name__ == '__main__':
    csv_files = sorted(glob.glob('data/season_*.csv'))
    for path in csv_files:
        add_odds_to_csv(path)
        time.sleep(3)
    print('\nDone.')
