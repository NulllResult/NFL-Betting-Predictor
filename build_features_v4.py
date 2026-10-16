import nflreadpy as nfl
import pandas as pd
import numpy as np

print("Loading PBP 2021-2026...")
pbp = nfl.load_pbp([2021, 2022, 2023, 2024, 2025, 2026])
pbp = pbp.to_pandas()
pbp = pbp[pbp['season_type'] == 'REG']
print(f"{len(pbp)} plays")

games = []
for game_id, g in pbp.groupby('game_id'):
    home = g['home_team'].iloc[0]
    away = g['away_team'].iloc[0]
    season = g['season'].iloc[0]
    week = g['week'].iloc[0]
    date = g['game_date'].iloc[0]

    h_off = g[g['posteam'] == home]
    a_off = g[g['posteam'] == away]
    h_def = g[g['defteam'] == home]
    a_def = g[g['defteam'] == away]

    def sm(col, df_):
        try:
            return float(df_[col].mean()) if col in df_.columns and len(df_) > 0 else 0.0
        except Exception:
            return 0.0

    def ss(col, df_):
        try:
            return float(df_[col].sum()) if col in df_.columns and len(df_) > 0 else 0.0
        except Exception:
            return 0.0

    def rz_eff(df_):
        try:
            drives = df_[df_['drive'].notna()].groupby('drive').agg(
                start=('yardline_100', 'max'),
                end=('yardline_100', 'min'),
                pts=('posteam_score_post', 'max')
            )
            rz = drives[drives['start'] <= 20]
            if len(rz) == 0:
                return 0.0
            return float(rz['pts'].mean())
        except Exception:
            return 0.0

    def third_down_rate(df_):
        try:
            td = df_[df_['down'] == 3]
            if len(td) == 0:
                return 0.0
            return float((td['first_down'].sum()) / len(td))
        except Exception:
            return 0.0

    def pressure_rate(df_):
        try:
            if 'sack' not in df_.columns:
                return 0.0
            dropbacks = df_[(df_['qb_dropback'] == 1)]
            if len(dropbacks) == 0:
                return 0.0
            return float(dropbacks['sack'].fillna(False).astype(bool).sum() / len(dropbacks))
        except Exception:
            return 0.0

    def explosive_rate(df_):
        try:
            plays = df_[df_['play_type'].isin(['pass', 'run'])]
            if len(plays) == 0:
                return 0.0
            explosive = plays[plays['yards_gained'] >= 20]
            return float(len(explosive) / len(plays))
        except Exception:
            return 0.0

    def points_per_drive(df_):
        try:
            drives = df_[df_['drive'].notna()].groupby('drive').agg(
                pts=('posteam_score_post', 'max')
            )
            if len(drives) == 0:
                return 0.0
            return float(drives['pts'].mean())
        except Exception:
            return 0.0

    games.append({
        'game_id': game_id, 'season': season, 'week': week, 'date': date,
        'home_team': home, 'away_team': away,
        'home_score': int(g['total_home_score'].max()),
        'away_score': int(g['total_away_score'].max()),
        'home_win': 1 if g['total_home_score'].max() > g['total_away_score'].max() else 0,

        # Offensive EPA
        'home_off_epa': sm('epa', h_off),
        'away_off_epa': sm('epa', a_off),

        # Defensive EPA allowed (real signal: opponent's epa on their plays)
        'home_def_epa_allowed': sm('epa', a_off),
        'away_def_epa_allowed': sm('epa', h_off),

        # Success rate
        'home_success': sm('success', h_off),
        'away_success': sm('success', a_off),
        'home_def_success_allowed': sm('success', a_off),
        'away_def_success_allowed': sm('success', h_off),

        # Turnovers (fumbles_lost + interceptions)
        'home_turnovers': ss('interception', h_off) + ss('fumble_lost', h_off),
        'away_turnovers': ss('interception', a_off) + ss('fumble_lost', a_off),
        'home_takeaways': ss('interception', h_def) + ss('fumble_lost', h_def),
        'away_takeaways': ss('interception', a_def) + ss('fumble_lost', a_def),

        # Situational
        'home_rz_eff': rz_eff(h_off),
        'away_rz_eff': rz_eff(a_off),
        'home_3d_rate': third_down_rate(h_off),
        'away_3d_rate': third_down_rate(a_off),
        'home_sack_rate': pressure_rate(h_off),
        'away_sack_rate': pressure_rate(a_off),
        'home_explosive_rate': explosive_rate(h_off),
        'away_explosive_rate': explosive_rate(a_off),
        'home_pts_per_drive': points_per_drive(h_off),
        'away_pts_per_drive': points_per_drive(a_off),

        # Home/away splits
        'home_is_home': 1,
        'away_is_home': 0,
    })

df = pd.DataFrame(games)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

df.to_csv('nfl_advanced_games_v4.csv', index=False)
print(f"\n✅ Built {len(df)} games with {len(df.columns)} columns")
print(f"\nColumns: {list(df.columns)}")

recent = df[df['season'] == 2026].tail(3)
print("\nLast 3 games of 2026:")
for _, r in recent.iterrows():
    print(f"  {r['date'].date()} - {r['away_team']} @ {r['home_team']} ({r['away_score']}-{r['home_score']})")
print(f"\nTotal 2026 games: {len(df[df['season']==2026])}")
