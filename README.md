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

## Usage

```python
from bpi import fetch_season, save_data, load_data

# Fetch a season (throttle=True to avoid rate limiting)
df = fetch_season(2025, throttle=True)
save_data(df, 'data/season_2024_25.csv')

# Load cached data
df = load_data('data/season_2024_25.csv')

# Run analysis
from bpi import win_prob_calibration, win_prob_scores, spread_accuracy
print(win_prob_calibration(df))
print(win_prob_scores(df))
print(spread_accuracy(df))
```

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
