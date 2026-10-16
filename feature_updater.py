import pandas as pd
import numpy as np
import joblib
import os

TEAM_ABBR_MAP = {
    "Buffalo Bills": "BUF", "Miami Dolphins": "MIA", "New England Patriots": "NE", "New York Jets": "NYJ",
    "Baltimore Ravens": "BAL", "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Pittsburgh Steelers": "PIT",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Tennessee Titans": "TEN",
    "Denver Broncos": "DEN", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Dallas Cowboys": "DAL", "New York Giants": "NYG", "Philadelphia Eagles": "PHI", "Washington Commanders": "WAS",
    "Chicago Bears": "CHI", "Detroit Lions": "DET", "Green Bay Packers": "GB", "Minnesota Vikings": "MIN",
    "Atlanta Falcons": "ATL", "Carolina Panthers": "CAR", "New Orleans Saints": "NO", "Tampa Bay Buccaneers": "TB",
    "Arizona Cardinals": "ARI", "Los Angeles Rams": "LA", "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA"
}

# Model files
MODEL_PATH = 'ml_models/random_forest_v6.pkl'
FEATURE_COLS_PATH = 'ml_models/feature_cols_v6.pkl'
GAMES_CSV = 'nfl_advanced_games_v6.csv'

_games_cache = None


def load_games():
    global _games_cache
    if _games_cache is not None:
        return _games_cache
    if not os.path.exists(GAMES_CSV):
        print(f"[ML] {GAMES_CSV} not found")
        return None
    df = pd.read_csv(GAMES_CSV)
    df['date'] = pd.to_datetime(df['date'])
    _games_cache = df.sort_values('date').reset_index(drop=True)
    return _games_cache


def compute_rolling_features(team_abbr, games_df):
    """
    Compute rolling 4-game features for a team based on their most recent 4 games.
    Accepts the abbreviation (KC, BUF, etc.) matching the v6 CSV.
    """
    prior = games_df[
        (games_df['home_team'] == team_abbr) | (games_df['away_team'] == team_abbr)
    ].tail(4)

    if len(prior) < 2:
        return None

    # v6 column names
    cols = {
        'off_epa': 'off_epa_r4',
        'success': 'success_rate_r4',
        'explosive': 'explosive_rate_r4',
        'sack': 'sack_rate_r4',
        'to': 'turnovers_r4',
        'pts': 'pts_r4',
        'cpoe': 'cpoe_r4',
        'air_epa': 'air_epa_r4',
        'yac_epa': 'yac_epa_r4',
        'xpass': 'xpass_rate_r4',
        'series_success': 'series_success_r4',
        'rz_td': 'rz_td_rate_r4',
        'qb_epa': 'qb_epa_r4',
        'pts_per_drive': 'pts_per_drive_r4',
    }
    result = {}
    for short, col in cols.items():
        vals = []
        for _, g in prior.iterrows():
            is_home = g['home_team'] == team_abbr
            home_col = f'home_{col}'
            away_col = f'away_{col}'
            if is_home and home_col in g.index:
                vals.append(g[home_col])
            elif not is_home and away_col in g.index:
                vals.append(g[away_col])
        result[short] = float(np.mean(vals)) if vals else 0.0
    return result


def predict_ml_probability(home_team, away_team):
    """
    Return probability home_team wins using the v6 model, or None on error.
    """
    try:
        games_df = load_games()
        if games_df is None:
            return None

        home_abbr = TEAM_ABBR_MAP.get(home_team, home_team)
        away_abbr = TEAM_ABBR_MAP.get(away_team, away_team)

        h = compute_rolling_features(home_abbr, games_df)
        a = compute_rolling_features(away_abbr, games_df)
        if not h or not a:
            return None

        model = joblib.load(MODEL_PATH)
        feature_cols = joblib.load(FEATURE_COLS_PATH)

        # Build features matching v6 training column names
        feats = {
            'home_off_epa_r4': h['off_epa'],
            'away_off_epa_r4': a['off_epa'],
            'home_success_rate_r4': h['success'],
            'away_success_rate_r4': a['success'],
            'home_explosive_rate_r4': h['explosive'],
            'away_explosive_rate_r4': a['explosive'],
            'home_sack_rate_r4': h['sack'],
            'away_sack_rate_r4': a['sack'],
            'home_turnovers_r4': h['to'],
            'away_turnovers_r4': a['to'],
            'home_pts_r4': h['pts'],
            'away_pts_r4': a['pts'],
            'home_cpoe_r4': h['cpoe'],
            'away_cpoe_r4': a['cpoe'],
            'home_air_epa_r4': h['air_epa'],
            'away_air_epa_r4': a['air_epa'],
            'home_yac_epa_r4': h['yac_epa'],
            'away_yac_epa_r4': a['yac_epa'],
            'home_xpass_rate_r4': h['xpass'],
            'away_xpass_rate_r4': a['xpass'],
            'home_series_success_r4': h['series_success'],
            'away_series_success_r4': a['series_success'],
            'home_rz_td_rate_r4': h['rz_td'],
            'away_rz_td_rate_r4': a['rz_td'],
            'home_qb_epa_r4': h['qb_epa'],
            'away_qb_epa_r4': a['qb_epa'],
            'home_pts_per_drive_r4': h['pts_per_drive'],
            'away_pts_per_drive_r4': a['pts_per_drive'],
        }
        # Differentials
        diffs = {
            'off_epa_r4_diff': 'off_epa',
            'success_rate_r4_diff': 'success',
            'explosive_rate_r4_diff': 'explosive',
            'sack_rate_r4_diff': 'sack',
            'turnovers_r4_diff': 'to',
            'pts_r4_diff': 'pts',
            'cpoe_r4_diff': 'cpoe',
            'air_epa_r4_diff': 'air_epa',
            'yac_epa_r4_diff': 'yac_epa',
            'xpass_rate_r4_diff': 'xpass',
            'series_success_r4_diff': 'series_success',
            'rz_td_rate_r4_diff': 'rz_td',
            'qb_epa_r4_diff': 'qb_epa',
            'pts_per_drive_r4_diff': 'pts_per_drive',
        }
        for diff_name, key in diffs.items():
            feats[diff_name] = h[key] - a[key]

        X = pd.DataFrame([feats])
        for col in feature_cols:
            if col not in X.columns:
                X[col] = 0.0
        X = X[feature_cols].fillna(0).values

        proba = model.predict_proba(X)[0]
        return float(proba[1])

    except Exception as e:
        print(f"[ML] Error: {e}")
        return None


if __name__ == '__main__':
    for home, away in [('Kansas City Chiefs', 'Buffalo Bills'), ('Detroit Lions', 'Arizona Cardinals')]:
        p = predict_ml_probability(home, away)
        if p is not None:
            print(f"{away} @ {home}: home wins {p:.1%}")
        else:
            print(f"{home} vs {away}: insufficient data")
