import pandas as pd
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

import numpy as np
import joblib
import json
import os
from datetime import datetime

def load_games():
    path = 'nfl_advanced_games_v3.csv'
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').reset_index(drop=True)

def compute_team_features(team, games_df):
    prior = games_df[
        (games_df['home_team'] == team) | (games_df['away_team'] == team)
    ].tail(8)
    if len(prior) < 4:
        return None
    
    hw = np.exp(-np.arange(len(prior))[::-1] / 4.0)
    hw = hw / hw.sum()
    
    def wavg(stat):
        vals = []
        for _, g in prior.iterrows():
            is_home = g['home_team'] == team
            if stat == 'pd':
                v = (g['home_score'] - g['away_score']) if is_home else (g['away_score'] - g['home_score'])
            elif stat == 'off_epa':
                v = g['home_off_epa'] if is_home else g['away_off_epa']
            elif stat == 'def_epa':
                v = g['home_def_epa'] if is_home else g['away_def_epa']
            elif stat == 'success':
                v = g['home_success'] if is_home else g['away_success']
            elif stat == 'to':
                v = g['home_turnovers'] if is_home else g['away_turnovers']
            else: v = 0
            vals.append(v)
        return np.average(vals, weights=hw) if len(vals) > 0 else 0
    
    pf = pa = 0
    for _, g in prior.iterrows():
        if g['home_team'] == team:
            pf += g['home_score']; pa += g['away_score']
        else:
            pf += g['away_score']; pa += g['home_score']
    pyth = (pf ** 2.37) / (pf ** 2.37 + pa ** 2.37) if pa > 0 else 0.5
    
    to_raw = wavg('to')
    to = to_raw * 0.7 + 1.5 * 0.3
    
    return {
        'pd': wavg('pd'),
        'pyth': pyth,
        'off_epa': wavg('off_epa'),
        'def_epa': wavg('def_epa'),
        'success': wavg('success'),
        'to': to
    }

def predict_ml_probability(home_team, away_team):
    """Return probability home_team wins using trained model, or None"""
    try:
        games_df = load_games()
        if games_df is None:
            return None
        home_abbr = TEAM_ABBR_MAP.get(home_team, home_team)
        away_abbr = TEAM_ABBR_MAP.get(away_team, away_team)
        h = compute_team_features(home_abbr, games_df)
        a = compute_team_features(away_abbr, games_df)
        if not h or not a:
            return None
        model = joblib.load('ml_models/random_forest.pkl')
        feature_cols = joblib.load('ml_models/feature_cols.pkl')
        feats = {
            'trail_pd_diff': h['pd'] - a['pd'],
            'pyth_diff': h['pyth'] - a['pyth'],
            'trail_off_epa_diff': h['off_epa'] - a['off_epa'],
            'trail_def_epa_diff': h['def_epa'] - a['def_epa'],
            'trail_success_diff': h['success'] - a['success'],
            'trail_turnover_diff': a['to'] - h['to'],
        }
        X = pd.DataFrame([feats])[feature_cols]
        prob = model.predict_proba(X)[0][1]
        return float(prob)
    except Exception as e:
        print(f"[ML] Error: {e}")
        return None

if __name__ == '__main__':
    for home, away in [('Buffalo Bills', 'Kansas City Chiefs'), ('Detroit Lions', 'Arizona Cardinals')]:
        p = predict_ml_probability(home, away)
        if p is not None:
            print(f"{away} @ {home}: {home} wins {p:.1%}")
        else:
            print(f"{home} vs {away}: insufficient data")
