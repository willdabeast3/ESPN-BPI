"""Re-fetch seasons that are missing BPI prediction data.

Checks each CSV in data/ for games with WIN_PROB > 0. If a season has
fewer than 1000 predictions, it re-fetches with throttling enabled to
avoid triggering ESPN's rate limit.

Run: python refetch_missing.py
"""
import glob
import time
from bpi import load_data, fetch_season, save_data

THRESHOLD = 1000  # minimum games with predictions to consider "complete"

csv_files = sorted(glob.glob('data/season_*.csv'))

for path in csv_files:
    df = load_data(path)
    valid = df[df['WIN_PROB'] > 0]
    label = path.split('season_')[1].replace('.csv', '').replace('_', '-')
    year = int(label.split('-')[0]) + 1  # season_end_year

    if len(valid) // 2 >= THRESHOLD:
        print(f'{label}: {len(valid)//2} predictions -- OK, skipping')
        continue

    print(f'{label}: {len(valid)//2} predictions -- REFETCHING (throttled)...')
    df_new = fetch_season(year, verbose=True, throttle=True)
    new_valid = df_new[df_new['WIN_PROB'] > 0]
    print(f'  Got {len(new_valid)//2} predictions (was {len(valid)//2})')

    if len(new_valid) > len(valid):
        save_data(df_new, path)
        print(f'  Saved to {path}')
    else:
        print(f'  No improvement, keeping existing file')

    # Pause between seasons to be gentle on the API
    time.sleep(5)

print('\nDone.')
