# William Arana
# ESPN BPI Prediction Accuracy Analysis

import datetime
import json
import math
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import scipy.stats as stats

# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

SCOREBOARD_URL = (
    'https://site.api.espn.com/apis/site/v2/sports/basketball/'
    'mens-college-basketball/scoreboard?dates={date}&groups=50&limit=200'
)
PREDICTOR_URL = (
    'https://sports.core.api.espn.com/v2/sports/basketball/leagues/'
    'mens-college-basketball/events/{event_id}/competitions/{event_id}/predictor'
)


def _fetch_json(url):
    """Fetch a URL and return parsed JSON, or None on error."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception:
        return None


def _get_predictor_stats(team_data):
    """Extract win prob and predicted point diff from a predictor team entry."""
    result = {'WIN_PROB': 0.0, 'PRED_SPREAD': 0.0}
    for stat in team_data.get('statistics', []):
        if stat['name'] == 'teampredwinpct':
            result['WIN_PROB'] = stat['value'] / 100.0
        elif stat['name'] == 'teampredmov':
            result['PRED_SPREAD'] = stat['value']
    return result


def _parse_scoreboard(scoreboard):
    """Parse a scoreboard response into a list of (event_id, game_date, teams) tuples."""
    games = []
    for event in scoreboard.get('events', []):
        event_id = event.get('id')
        if not event_id or 'competitions' not in event or not event['competitions']:
            continue
        comp = event['competitions'][0]

        if comp.get('status', {}).get('type', {}).get('name') != 'STATUS_FINAL':
            continue

        game_date = comp['date'][:10]

        teams = {}
        for competitor in comp['competitors']:
            side = competitor['homeAway']
            teams[side] = {
                'DATE': game_date,
                'TEAM': competitor['team']['displayName'],
                'POINTS': float(competitor.get('score', 0)),
                'HOME_AWAY': side,
            }

        if 'home' not in teams or 'away' not in teams:
            continue

        games.append((event_id, game_date, teams))
    return games


def _enrich_game(event_id, game_date, teams):
    """Fetch predictor data for one game, return two row dicts (home, away)."""
    predictor = _fetch_json(PREDICTOR_URL.format(event_id=event_id))
    if predictor:
        teams['home'].update(_get_predictor_stats(predictor.get('homeTeam', {})))
        teams['away'].update(_get_predictor_stats(predictor.get('awayTeam', {})))
    else:
        teams['home'].update({'WIN_PROB': 0.0, 'PRED_SPREAD': 0.0})
        teams['away'].update({'WIN_PROB': 0.0, 'PRED_SPREAD': 0.0})

    home_pts = teams['home']['POINTS']
    away_pts = teams['away']['POINTS']

    teams['home']['WON'] = home_pts > away_pts
    teams['home']['ACTUAL_SPREAD'] = home_pts - away_pts
    teams['away']['WON'] = away_pts > home_pts
    teams['away']['ACTUAL_SPREAD'] = away_pts - home_pts

    return [teams['home'], teams['away']]


def fetch_games(date_str, max_workers=20):
    """Fetch all completed games and BPI predictions for a single date.

    Predictor API calls are parallelized across games within the day.
    """
    scoreboard = _fetch_json(SCOREBOARD_URL.format(date=date_str))
    if not scoreboard:
        return []

    games = _parse_scoreboard(scoreboard)
    if not games:
        return []

    rows = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_enrich_game, eid, gd, t): eid
                   for eid, gd, t in games}
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except Exception:
                pass  # skip individual game errors

    return rows


def date_range(start, count):
    """Generate a list of date strings in YYYYMMDD format."""
    start_date = datetime.datetime.strptime(start, "%Y-%m-%d")
    dates = pd.date_range(start_date, periods=count)
    return [d.strftime("%Y%m%d") for d in dates]


def fetch_date_range(start, count, verbose=False, max_workers=8, throttle=False):
    """Fetch game data for a range of dates. Returns a DataFrame.

    Args:
        max_workers: Number of concurrent day-level fetches.
        throttle: If True, fetch days sequentially with a delay to avoid rate limiting.
    """
    dates = date_range(start, count)
    all_rows = []

    if throttle:
        # Moderate parallelism — fast enough but avoids rate limits
        # ~30-40 concurrent connections total (4 days × 10 games)
        completed = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fetch_games, d, max_workers=10): d for d in dates}
            for future in as_completed(futures):
                all_rows.extend(future.result())
                completed += 1
                if verbose and completed % 20 == 0:
                    print(f'  {completed}/{len(dates)} days fetched...', flush=True)
    else:
        # Full parallel — fastest but can trigger rate limits on large fetches
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(fetch_games, d): d for d in dates}
            for future in as_completed(futures):
                all_rows.extend(future.result())
                completed += 1
                if verbose and completed % 20 == 0:
                    print(f'  {completed}/{len(dates)} days fetched...', flush=True)

    if verbose:
        print(f'  {len(dates)}/{len(dates)} done. {len(all_rows)//2} games total.')
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows)
    df['DATE'] = pd.to_datetime(df['DATE'])
    return df


def fetch_season(season_end_year, verbose=True, throttle=False):
    """Fetch a full NCAA basketball season (Nov 1 through April 15).

    Args:
        season_end_year: The year the season ends (e.g., 2022 for the 2021-22 season).
        verbose: Print progress updates.
        throttle: If True, fetch sequentially with delays to avoid rate limiting.
    """
    start = f'{season_end_year - 1}-11-01'
    # Nov 1 to Apr 15 = ~166 days
    count = (datetime.date(season_end_year, 4, 15) - datetime.date(season_end_year - 1, 11, 1)).days + 1
    if verbose:
        print(f'Fetching {season_end_year - 1}-{str(season_end_year)[2:]} season ({count} days)...')
    return fetch_date_range(start, count, verbose=verbose, throttle=throttle)


def save_data(df, path):
    """Save a game DataFrame to CSV."""
    df.to_csv(path, index=False)


def load_data(path):
    """Load a game DataFrame from CSV."""
    df = pd.read_csv(path)
    df['DATE'] = pd.to_datetime(df['DATE'])
    return df


# ---------------------------------------------------------------------------
# Q1: Win probability accuracy
# ---------------------------------------------------------------------------

def win_prob_calibration(df, n_bins=10):
    """Calibration analysis for win probability predictions.

    Bins predictions into equal-width brackets from 0.50 to 1.0 (favorites only),
    then for each bin compares the observed win rate to the average prediction
    using a two-tailed binomial test.

    Returns:
        DataFrame with columns: Bin_Low, Bin_High, Avg_Predicted, Observed_Win_Rate,
        N, Wins, Binomial_P_Value
    """
    # Use only the favorite side of each game (WIN_PROB >= 0.50)
    fav = df[df['WIN_PROB'] >= 0.50].copy()

    bin_edges = np.linspace(0.50, 1.0, n_bins + 1)
    rows = []
    for j in range(len(bin_edges) - 1):
        lo, hi = bin_edges[j], bin_edges[j + 1]
        if j == len(bin_edges) - 2:
            bracket = fav[(fav['WIN_PROB'] >= lo) & (fav['WIN_PROB'] <= hi)]
        else:
            bracket = fav[(fav['WIN_PROB'] >= lo) & (fav['WIN_PROB'] < hi)]

        n = len(bracket)
        if n == 0:
            rows.append({'Bin_Low': lo, 'Bin_High': hi, 'Avg_Predicted': np.nan,
                         'Observed_Win_Rate': np.nan, 'N': 0, 'Wins': 0,
                         'Binomial_P_Value': np.nan})
            continue

        avg_pred = bracket['WIN_PROB'].mean()
        wins = int(bracket['WON'].sum())
        observed = wins / n

        # Two-tailed binomial test: is the observed win count consistent
        # with the predicted probability?
        binom_p = stats.binomtest(wins, n, avg_pred, alternative='two-sided').pvalue

        rows.append({
            'Bin_Low': round(lo, 4),
            'Bin_High': round(hi, 4),
            'Avg_Predicted': round(avg_pred, 4),
            'Observed_Win_Rate': round(observed, 4),
            'N': n,
            'Wins': wins,
            'Binomial_P_Value': binom_p,
        })

    return pd.DataFrame(rows)


def win_prob_scores(df):
    """Compute Brier score and log loss for win probability predictions.

    Uses favorites only (WIN_PROB >= 0.50) so each game is counted once.

    Returns:
        dict with keys: brier_score, brier_baseline, brier_skill_score,
        log_loss, n_games
    """
    fav = df[df['WIN_PROB'] >= 0.50].copy()
    predicted = fav['WIN_PROB'].values
    actual = fav['WON'].astype(float).values
    n = len(fav)

    brier = np.mean((predicted - actual) ** 2)
    brier_baseline = 0.25  # always predicting 0.50

    # Brier Skill Score: 1 = perfect, 0 = no better than 50/50, negative = worse
    brier_skill = 1.0 - (brier / brier_baseline)

    # Log loss (clamp predictions away from 0/1 to avoid log(0))
    eps = 1e-10
    p_clamp = np.clip(predicted, eps, 1 - eps)
    log_loss = -np.mean(actual * np.log(p_clamp) + (1 - actual) * np.log(1 - p_clamp))

    return {
        'brier_score': round(brier, 6),
        'brier_baseline': brier_baseline,
        'brier_skill_score': round(brier_skill, 4),
        'log_loss': round(log_loss, 6),
        'n_games': n,
    }


# ---------------------------------------------------------------------------
# Q2: Spread prediction accuracy
# ---------------------------------------------------------------------------

def spread_accuracy(df):
    """Overall accuracy metrics for spread predictions.

    Uses favorites only (PRED_SPREAD > 0) so each game is counted once.

    Returns:
        dict with keys: mean_residual, residual_t_stat, residual_p_value,
        mae, rmse, n_games
    """
    fav = df[df['PRED_SPREAD'] > 0].copy()
    residuals = fav['PRED_SPREAD'] - fav['ACTUAL_SPREAD']
    n = len(fav)

    mae = np.mean(np.abs(residuals))
    rmse = np.sqrt(np.mean(residuals ** 2))

    # One-sample t-test on residuals: is the mean residual = 0? (tests for bias)
    t_stat, p_value = stats.ttest_1samp(residuals, 0)

    return {
        'mean_residual': round(residuals.mean(), 3),
        'residual_t_stat': round(t_stat, 4),
        'residual_p_value': round(p_value, 6),
        'mae': round(mae, 3),
        'rmse': round(rmse, 3),
        'n_games': n,
    }


def spread_regression(df):
    """Regress actual spread on predicted spread.

    Perfect model: slope=1, intercept=0.
    Slope < 1 means overconfident (big predictions shrink in reality).
    Slope > 1 means underconfident.

    Uses favorites only (PRED_SPREAD > 0).

    Returns:
        dict with keys: slope, intercept, r_squared, slope_se,
        slope_t_vs_1 (t-stat testing slope=1), slope_p_vs_1, n_games
    """
    fav = df[df['PRED_SPREAD'] > 0].copy()
    x = fav['PRED_SPREAD'].values
    y = fav['ACTUAL_SPREAD'].values
    n = len(fav)

    result = stats.linregress(x, y)

    # Test H0: slope = 1 (not slope = 0, which is the default)
    t_vs_1 = (result.slope - 1.0) / result.stderr
    p_vs_1 = stats.t.sf(abs(t_vs_1), df=n - 2) * 2

    return {
        'slope': round(result.slope, 4),
        'intercept': round(result.intercept, 3),
        'r_squared': round(result.rvalue ** 2, 4),
        'slope_se': round(result.stderr, 4),
        'slope_t_vs_1': round(t_vs_1, 4),
        'slope_p_vs_1': round(p_vs_1, 6),
        'n_games': n,
    }


def spread_by_bin(df, step=3):
    """Bin favorites by predicted spread and compare to actual.

    Within each bin, runs a one-sample t-test on the residuals
    (predicted - actual) to test for bias.

    Returns:
        DataFrame with columns: Bin_Low, Bin_High, Avg_Predicted,
        Avg_Actual, Mean_Residual, Residual_P_Value, N
    """
    fav = df[df['PRED_SPREAD'] > 0].copy()
    max_spread = math.ceil(fav['PRED_SPREAD'].max())
    bin_edges = np.arange(0, max_spread + step, step)

    rows = []
    for j in range(len(bin_edges) - 1):
        lo, hi = bin_edges[j], bin_edges[j + 1]
        bracket = fav[(fav['PRED_SPREAD'] >= lo) & (fav['PRED_SPREAD'] < hi)]
        n = len(bracket)

        if n < 2:
            rows.append({'Bin_Low': lo, 'Bin_High': hi, 'Avg_Predicted': np.nan,
                         'Avg_Actual': np.nan, 'Mean_Residual': np.nan,
                         'Residual_P_Value': np.nan, 'N': n})
            continue

        residuals = bracket['PRED_SPREAD'] - bracket['ACTUAL_SPREAD']
        t_stat, p_val = stats.ttest_1samp(residuals, 0)

        rows.append({
            'Bin_Low': lo,
            'Bin_High': hi,
            'Avg_Predicted': round(bracket['PRED_SPREAD'].mean(), 3),
            'Avg_Actual': round(bracket['ACTUAL_SPREAD'].mean(), 3),
            'Mean_Residual': round(residuals.mean(), 3),
            'Residual_P_Value': round(p_val, 6),
            'N': n,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Q3: Does the model improve over time?
# ---------------------------------------------------------------------------

def accuracy_over_time(df, period='M'):
    """Compute accuracy metrics per time period.

    Args:
        df: Full game DataFrame with DATE column.
        period: Pandas offset alias for grouping. 'M' = monthly, 'W' = weekly.

    Returns:
        DataFrame indexed by period with columns: Brier_Score, MAE, N_Games
    """
    fav = df[df['WIN_PROB'] >= 0.50].copy()
    fav['PERIOD'] = fav['DATE'].dt.to_period(period)

    rows = []
    for period_val, group in fav.groupby('PERIOD'):
        predicted = group['WIN_PROB'].values
        actual = group['WON'].astype(float).values
        brier = np.mean((predicted - actual) ** 2)

        spread_fav = group[group['PRED_SPREAD'] > 0]
        if len(spread_fav) > 0:
            mae = np.mean(np.abs(spread_fav['PRED_SPREAD'] - spread_fav['ACTUAL_SPREAD']))
        else:
            mae = np.nan

        rows.append({
            'Period': str(period_val),
            'Brier_Score': round(brier, 6),
            'Spread_MAE': round(mae, 3) if not np.isnan(mae) else np.nan,
            'N_Games': len(group),
        })

    return pd.DataFrame(rows)


def accuracy_trend_test(time_df, metric='Brier_Score'):
    """Test whether an accuracy metric trends over time.

    Uses Spearman rank correlation between the period index and the metric.

    Args:
        time_df: Output of accuracy_over_time().
        metric: Column name to test.

    Returns:
        dict with keys: spearman_r, p_value, direction, n_periods
    """
    valid = time_df.dropna(subset=[metric])
    x = np.arange(len(valid))
    y = valid[metric].values

    if len(valid) < 3:
        return {'spearman_r': np.nan, 'p_value': np.nan,
                'direction': 'insufficient data', 'n_periods': len(valid)}

    r, p = stats.spearmanr(x, y)

    if p < 0.05:
        direction = 'improving' if r < 0 else 'worsening'
    else:
        direction = 'no significant trend'

    return {
        'spearman_r': round(r, 4),
        'p_value': round(p, 6),
        'direction': direction,
        'n_periods': len(valid),
    }


def accuracy_by_season(df):
    """Compute accuracy metrics per NCAA season.

    NCAA seasons span Nov-March. A game in Nov-Dec belongs to the season
    ending the following spring (e.g., Nov 2021 → 2021-22 season).

    Returns:
        DataFrame with columns: Season, Brier_Score, Spread_MAE, N_Games
    """
    fav = df[df['WIN_PROB'] >= 0.50].copy()

    # Assign season: games in months >= 8 (Aug+) belong to the next calendar year's season
    year = fav['DATE'].dt.year
    month = fav['DATE'].dt.month
    season_end_year = np.where(month >= 8, year + 1, year)
    fav['SEASON'] = [f'{y-1}-{str(y)[2:]}' for y in season_end_year]

    rows = []
    for season, group in fav.groupby('SEASON'):
        predicted = group['WIN_PROB'].values
        actual = group['WON'].astype(float).values
        brier = np.mean((predicted - actual) ** 2)

        spread_fav = group[group['PRED_SPREAD'] > 0]
        if len(spread_fav) > 0:
            mae = np.mean(np.abs(spread_fav['PRED_SPREAD'] - spread_fav['ACTUAL_SPREAD']))
        else:
            mae = np.nan

        rows.append({
            'Season': season,
            'Brier_Score': round(brier, 6),
            'Spread_MAE': round(mae, 3) if not np.isnan(mae) else np.nan,
            'N_Games': len(group),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    df = fetch_date_range(start='2022-01-11', count=60)

    if not df.empty:
        print(f'Loaded {len(df)//2} games ({len(df)} team-rows).\n')

        print('=== Q1: Win Probability Calibration ===')
        print(win_prob_calibration(df).to_string(index=False))
        print()
        print('Scoring:', win_prob_scores(df))
        print()

        print('=== Q2: Spread Accuracy ===')
        print('Overall:', spread_accuracy(df))
        print()
        print('Regression:', spread_regression(df))
        print()
        print(spread_by_bin(df).to_string(index=False))
        print()

        print('=== Q3: Accuracy Over Time (Monthly) ===')
        time_df = accuracy_over_time(df, period='M')
        print(time_df.to_string(index=False))
        print()
        print('Brier trend:', accuracy_trend_test(time_df, 'Brier_Score'))
        print('MAE trend:', accuracy_trend_test(time_df, 'Spread_MAE'))
