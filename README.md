# ESPN BPI Prediction Accuracy

An empirical evaluation of ESPN's Basketball Power Index (BPI) predictions for NCAA Men's College Basketball, covering 15 seasons from 2010-11 through 2024-25.

**[View the full report (HTML)](report.html)** — download and open in any browser, no dependencies required.

## Questions Investigated

1. **Win probability calibration** — Are BPI's predicted win probabilities well-calibrated?
2. **Spread accuracy** — How accurate are BPI's predicted point spreads?
3. **Improvement over time** — Does BPI get better within a season and year-over-year?
4. **Home court advantage** — Does BPI correctly price home court?
5. **Conference vs non-conference play** — Is BPI more accurate during conference play?
6. **March Madness** — Is BPI more or less accurate during the NCAA tournament?
7. **BPI vs Vegas** — How does BPI compare to betting market spreads?

## Key Findings

- BPI is systematically **overconfident in the 60-85% win probability range** (2-4pp deviation)
- Spread predictions show a mild **compression toward the mean** (slope = 0.947)
- **No year-over-year improvement** across 15 seasons — the model reached maturity early
- BPI slightly **overprices home court advantage** (< 0.5 points, but significant)
- **March Madness accuracy drops** substantially (Brier skill score nearly halves)
- **Vegas outperforms BPI** on spread accuracy (MAE 8.74 vs 8.97, closer 53.8% of the time)

## Project Structure

- `report.html` — Complete analysis report (open in any browser)
- `report.ipynb` — Jupyter notebook source with all code and analysis
- `bpi.py` — Data collection (ESPN JSON APIs) and statistical analysis functions
- `fetch_odds.py` — Utility to fetch Vegas spread data from ESPN's odds API
- `refetch_missing.py` — Utility to re-fetch seasons with incomplete prediction data
- `data/` — Cached season CSVs (`season_YYYY_YY.csv`)

## Reproducing the Results

### Prerequisites

```bash
git clone https://github.com/willdabeast3/ESPN-BPI.git
cd ESPN-BPI
pip install numpy pandas scipy matplotlib jupyter nbconvert
```

### Option 1: View the report (no code execution needed)

Open `report.html` in any web browser. All results, tables, and graphs are included.

### Option 2: Run the notebook with cached data

Pre-fetched season CSVs (including Vegas spreads) are included in `data/`. To re-run the analysis:

```bash
jupyter notebook report.ipynb
```

Run all cells to regenerate calibration tables, regression plots, and trend analysis. To export a fresh HTML report:

```bash
jupyter nbconvert --to html --execute report.ipynb --no-input
```

### Option 3: Fetch fresh data from ESPN

Each season takes ~3 minutes to fetch. Use `throttle=True` to avoid ESPN's rate limit.

```python
from bpi import fetch_season, save_data

df = fetch_season(2025, throttle=True)
save_data(df, 'data/season_2024_25.csv')
```

To fetch all seasons:

```python
import os
from bpi import fetch_season, save_data

os.makedirs('data', exist_ok=True)
for year in range(2011, 2026):
    label = f'{year-1}_{str(year)[2:]}'
    path = f'data/season_{label}.csv'
    if not os.path.exists(path):
        df = fetch_season(year, throttle=True)
        save_data(df, path)
```

**Note:** ESPN's predictor API rate-limits after ~3-4 consecutive seasons of throttled fetching. If seasons end up with missing predictions (WIN_PROB=0), wait 15-60 minutes and run:

```bash
python refetch_missing.py
```

To add Vegas spread data to the CSVs:

```bash
python fetch_odds.py
```

This fetches closing lines from ESPN's odds API. Odds data is available from 2012-13 onward (66-93% coverage depending on season).

## Data Sources

- **Scoreboard API**: `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`
- **Predictor API**: `sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{id}/competitions/{id}/predictor`
- **Odds API**: `sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{id}/competitions/{id}/odds`

## Requirements

```
numpy
pandas
scipy
matplotlib
jupyter
nbconvert
```

## Author

William Arana
