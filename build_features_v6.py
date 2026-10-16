import nflreadpy as nfl
import pandas as pd
import numpy as np

print("Loading PBP 2021-2026...")
pbp = nfl.load_pbp([2021, 2022, 2023, 2024, 2025, 2026]).to_pandas()
pbp = pbp[pbp['season_type'] == 'REG']
print(f"{len(pbp)} plays")

print("Computing per-game team stats...")
game_stats = []
for (game_id, team), g in pbp.groupby(['game_id', 'posteam']):
    if pd.isna(team):
        continue
    plays = g[g['play_type'].isin(['pass', 'run'])]
    if len(plays) == 0:
        continue
    dropbacks = g[g['qb_dropback'] == 1]
    pass_plays = g[g['play_type'] == 'pass']
    rec = g[g['complete_pass'] == 1] if 'complete_pass' in g.columns else pd.DataFrame()

    drives = g[g['drive'].notna()].groupby('drive').agg(
        pts=('posteam_score_post', 'max'),
        start=('yardline_100', 'max'),
    )
    rz_drives = drives[drives['start'] <= 20]

    game_stats.append({
        'game_id': game_id,
        'team': team,
        'season': g['season'].iloc[0],
        'week': g['week'].iloc[0],
        'date': g['game_date'].iloc[0],
        # Base
        'off_epa': plays['epa'].mean(),
        'success_rate': plays['success'].mean(),
        'explosive_rate': (plays['yards_gained'] >= 20).mean(),
        'sack_rate': dropbacks['sack'].fillna(False).astype(bool).mean() if len(dropbacks) > 0 else 0.0,
        'turnovers': g['interception'].fillna(False).astype(bool).sum() + g['fumble_lost'].fillna(False).astype(bool).sum(),
        'pts': g['posteam_score_post'].max(),
        # NEW play-level features
        'cpoe': pass_plays['cpoe'].mean() if 'cpoe' in pass_plays.columns else 0.0,
        'air_epa': pass_plays['air_epa'].mean() if 'air_epa' in pass_plays.columns else 0.0,
        'yac_epa': pass_plays['yac_epa'].mean() if 'yac_epa' in pass_plays.columns else 0.0,
        'xpass_rate': g['xpass'].mean() if 'xpass' in g.columns else 0.0,
        'series_success': g['series_success'].mean() if 'series_success' in g.columns else 0.0,
        'rz_td_rate': (rz_drives['pts'] >= 6).mean() if len(rz_drives) > 0 else 0.0,
        'qb_epa': g[g['qb_dropback'] == 1]['qb_epa'].mean() if 'qb_epa' in g.columns else 0.0,
        'pts_per_drive': drives['pts'].mean() if len(drives) > 0 else 0.0,
    })

stats_df = pd.DataFrame(game_stats)
stats_df['date'] = pd.to_datetime(stats_df['date'])
stats_df = stats_df.sort_values(['team', 'date']).reset_index(drop=True)

print("Computing rolling averages (last 4 games, excluding current)...")
roll_cols = ['off_epa', 'success_rate', 'explosive_rate', 'sack_rate', 'turnovers', 'pts',
             'cpoe', 'air_epa', 'yac_epa', 'xpass_rate', 'series_success', 'rz_td_rate', 'qb_epa', 'pts_per_drive']
for col in roll_cols:
    stats_df[f'{col}_r4'] = stats_df.groupby('team')[col].transform(
        lambda s: s.shift(1).rolling(4, min_periods=1).mean()
    )

print("Building game-level features...")
games = []
for game_id, g in pbp.groupby('game_id'):
    home = g['home_team'].iloc[0]
    away = g['away_team'].iloc[0]
    season = g['season'].iloc[0]
    week = g['week'].iloc[0]
    date = g['game_date'].iloc[0]
    home_score = int(g['total_home_score'].max())
    away_score = int(g['total_away_score'].max())

    h_stat = stats_df[(stats_df['game_id'] == game_id) & (stats_df['team'] == home)]
    a_stat = stats_df[(stats_df['game_id'] == game_id) & (stats_df['team'] == away)]
    if h_stat.empty or a_stat.empty:
        continue
    hs = h_stat.iloc[0]
    as_ = a_stat.iloc[0]

    row = {
        'game_id': game_id, 'season': season, 'week': week, 'date': date,
        'home_team': home, 'away_team': away,
        'home_score': home_score, 'away_score': away_score,
        'home_win': 1 if home_score > away_score else 0,
    }
    for col in roll_cols:
        row[f'home_{col}_r4'] = hs[f'{col}_r4']
        row[f'away_{col}_r4'] = as_[f'{col}_r4']
    games.append(row)

df = pd.DataFrame(games)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
df = df.dropna(subset=['home_off_epa_r4', 'away_off_epa_r4'])
df.to_csv('nfl_advanced_games_v6.csv', index=False)
print(f"\n✅ Built {len(df)} games with {len(df.columns)} cols")
print(f"Feature cols: {[c for c in df.columns if '_r4' in c]}")
