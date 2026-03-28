# ESPN BPI Prediction Accuracy

An empirical evaluation of ESPN's Basketball Power Index (BPI) predictions for NCAA Men's College Basketball, covering 15 seasons from 2010-11 through 2024-25.

## Questions Investigated

1. **Win probability calibration** — Are BPI's predicted win probabilities well-calibrated? (Binomial tests, Brier score, log loss)
2. **Spread accuracy** — How accurate are BPI's predicted point spreads? (Residual analysis, regression, MAE/RMSE)
3. **Improvement over time** — Does BPI get better within a season and year-over-year? (Spearman rank correlation)
4. **Home court advantage** — Does BPI correctly price home court?
5. **Conference vs non-conference play** — Is BPI more accurate during conference play?
6. **March Madness** — Is BPI more or less accurate during the NCAA tournament?
7. **BPI vs Vegas** — How does BPI compare to betting market spreads? (Future work)

## Project Structure

- `bpi.py` — Data collection (ESPN JSON APIs) and statistical analysis functions
- `report.ipynb` — Jupyter notebook with full analysis, visualizations, and discussion
- `refetch_missing.py` — Utility to re-fetch seasons with incomplete prediction data
- `data/` — Cached season CSVs (`season_YYYY_YY.csv`)

## Data Sources

- **Scoreboard API**: `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard`
- **Predictor API**: `sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{id}/competitions/{id}/predictor`

## Getting Started

```bash
git clone https://github.com/yourusername/ESPN-BPI.git
cd ESPN-BPI
pip install numpy pandas scipy matplotlib jupyter
```

### Run the report (using cached data)

Pre-fetched season CSVs are included in `data/`. To run the analysis:

```bash
jupyter notebook report.ipynb
```

Run all cells to generate calibration tables, regression plots, and trend analysis.

### Fetch fresh data

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

If some seasons end up with missing predictions (WIN_PROB=0) due to rate limiting, wait 15-60 minutes and run:

```bash
python refetch_missing.py
```

### Run analysis from the command line

```bash
python bpi.py
```

This fetches a small date range and prints calibration, spread accuracy, and trend results.

## Requirements

```
numpy
pandas
scipy
matplotlib
jupyter
```

## Author

William Arana
