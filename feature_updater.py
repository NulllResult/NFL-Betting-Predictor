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

# Meta-ensemble config
MODEL_V6 = 'ml_models/meta_v6.pkl'
MODEL_V7 = 'ml_models/meta_v7.pkl'
FEATS_V6 = 'ml_models/feature_cols_v6.pkl'
FEATS_V7 = 'ml_models/feature_cols_v7.pkl'
WEIGHTS = 'ml_models/meta_weights.pkl'
GAMES_V7 = 'nfl_advanced_games_v7.csv'

_games_cache = None
_models_cache = None


def _load_all():
    global _games_cache, _models_cache
    if _games_cache is None:
        df = pd.read_csv(GAMES_V7)
        df['date'] = pd.to_datetime(df['date'])
        _games_cache = df.sort_values('date').reset_index(drop=True)
    if _models_cache is None:
        _models_cache = {
            'm6': joblib.load(MODEL_V6),
            'm7': joblib.load(MODEL_V7),
            'f6': joblib.load(FEATS_V6),
            'f7': joblib.load(FEATS_V7),
            'w': joblib.load(WEIGHTS),
        }
    return _games_cache, _models_cache


# Base columns we need rolling stats for
BASE_COLS = {
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
    'third_down_epa': 'third_down_epa_r4',
    'rz_pass_rate': 'rz_pass_rate_r4',
    'two_min_epa': 'two_min_epa_r4',
    'gtg_success': 'gtg_success_r4',
    'drive_success': 'drive_success_r4',
    'avg_drive_start': 'avg_drive_start_r4',
    'plays_per_drive': 'plays_per_drive_r4',
    'neutral_epa': 'neutral_epa_r4',
}


def compute_rolling_features(team_abbr, games_df):
    prior = games_df[
        (games_df['home_team'] == team_abbr) | (games_df['away_team'] == team_abbr)
    ].tail(4)
    if len(prior) < 2:
        return None

    result = {}
    for short, col in BASE_COLS.items():
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


def _build_features(h, a):
    """Build v6/v7 feature dicts."""
    feats = {}
    for key in h:
        feats[f'home_{key}_r4'] = h[key]
        feats[f'away_{key}_r4'] = a[key]
    # Differentials
    for key in h:
        # Map short names to expected diff column names
        feats[f'{key}_r4_diff'] = h[key] - a[key]
    # Add a few explicit mappings the trainers used
    if 'success' in h:
        feats['success_rate_r4_diff'] = h['success'] - a['success']
    if 'explosive' in h:
        feats['explosive_rate_r4_diff'] = h['explosive'] - a['explosive']
    if 'sack' in h:
        feats['sack_rate_r4_diff'] = h['sack'] - a['sack']
    if 'turnovers' in h:
        feats['turnovers_r4_diff'] = h['to'] - a['to']
    if 'xpass_rate' in h:
        feats['xpass_rate_r4_diff'] = h['xpass'] - a['xpass']
    return feats


def predict_ml_probability(home_team, away_team):
    """
    Return probability home_team wins using the v6+v7 meta-ensemble.
    """
    try:
        games_df, models = _load_all()

        home_abbr = TEAM_ABBR_MAP.get(home_team, home_team)
        away_abbr = TEAM_ABBR_MAP.get(away_team, away_team)

        h = compute_rolling_features(home_abbr, games_df)
        a = compute_rolling_features(away_abbr, games_df)
        if not h or not a:
            return None

        feats = _build_features(h, a)

        def predict_one(model, feature_cols):
            X = pd.DataFrame([feats])
            for col in feature_cols:
                if col not in X.columns:
                    X[col] = 0.0
            X = X[feature_cols].fillna(0).values
            return float(model.predict_proba(X)[0][1])

        p6 = predict_one(models['m6'], models['f6'])
        p7 = predict_one(models['m7'], models['f7'])
        w = models['w'].get('w_v6', 0.6)
        p = w * p6 + (1 - w) * p7
        return p

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
