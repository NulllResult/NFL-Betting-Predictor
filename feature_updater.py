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
MODEL_PATH = 'ml_models/random_forest_v5.pkl'
FEATURE_COLS_PATH = 'ml_models/feature_cols_v5.pkl'
GAMES_CSV = 'nfl_advanced_games_v5.csv'

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


def compute_rolling_features(team, games_df):
    """
    Compute rolling 4-game features for a team based on their most recent 4 games.
    Uses 'home' prefix if team is the home team in the current matchup,
    'away' prefix otherwise. Returns a dict keyed by home_*/away_* names.
    """
    prior = games_df[
        (games_df['home_team'] == team) | (games_df['away_team'] == team)
    ].tail(4)

    if len(prior) < 2:
        return None

    # Compute rolling averages of the last 4 games for this team
    off_epa, success, explosive, sack, to, pts = [], [], [], [], [], []
    for _, g in prior.iterrows():
        is_home = g['home_team'] == team
        # v5 CSV columns
        off_epa.append(g['home_off_epa_r4'] if is_home else g['away_off_epa_r4'])
        success.append(g['home_success_r4'] if is_home else g['away_success_r4'])
        explosive.append(g['home_explosive_r4'] if is_home else g['away_explosive_r4'])
        sack.append(g['home_sack_r4'] if is_home else g['away_sack_r4'])
        to.append(g['home_to_r4'] if is_home else g['away_to_r4'])
        pts.append(g['home_pts_r4'] if is_home else g['away_pts_r4'])

    return {
        'off_epa': float(np.mean(off_epa)),
        'success': float(np.mean(success)),
        'explosive': float(np.mean(explosive)),
        'sack': float(np.mean(sack)),
        'to': float(np.mean(to)),
        'pts': float(np.mean(pts)),
    }


def predict_ml_probability(home_team, away_team):
    """
    Return probability home_team wins using the v5 model, or None on error.
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

        # Build feature dict matching v5 training column names
        feats = {
            'home_off_epa_r4': h['off_epa'],
            'away_off_epa_r4': a['off_epa'],
            'home_success_r4': h['success'],
            'away_success_r4': a['success'],
            'home_explosive_r4': h['explosive'],
            'away_explosive_r4': a['explosive'],
            'home_sack_r4': h['sack'],
            'away_sack_r4': a['sack'],
            'home_to_r4': h['to'],
            'away_to_r4': a['to'],
            'home_pts_r4': h['pts'],
            'away_pts_r4': a['pts'],
        }
        # Add differential features (same as trainer)
        feats['off_epa_r4_diff'] = h['off_epa'] - a['off_epa']
        feats['success_r4_diff'] = h['success'] - a['success']
        feats['explosive_r4_diff'] = h['explosive'] - a['explosive']
        feats['sack_r4_diff'] = h['sack'] - a['sack']
        feats['to_r4_diff'] = h['to'] - a['to']
        feats['pts_r4_diff'] = h['pts'] - a['pts']

        # Build input vector in the exact order the model expects
        X = pd.DataFrame([feats])
        # Ensure all required columns exist; fill missing with 0
        for col in feature_cols:
            if col not in X.columns:
                X[col] = 0.0
        X = X[feature_cols].fillna(0).values

        proba = model.predict_proba(X)[0]
        # Class order: model.classes_ = [0, 1]; proba[1] = home wins
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
