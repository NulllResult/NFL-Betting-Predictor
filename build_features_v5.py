import nflreadpy as nfl
import pandas as pd
import numpy as np

print("Loading PBP 2021-2026...")
pbp = nfl.load_pbp([2021, 2022, 2023, 2024, 2025, 2026]).to_pandas()
pbp = pbp[pbp['season_type'] == 'REG']
print(f"{len(pbp)} plays")

# ────── STEP 1: Compute per-game aggregates ──────
print("Computing per-game team stats...")
game_stats = []
for (game_id, team), g in pbp.groupby(['game_id', 'posteam']):
    if pd.isna(team):
        continue
    plays = g[g['play_type'].isin(['pass', 'run'])]
    if len(plays) == 0:
        continue
    dropbacks = g[g['qb_dropback'] == 1]
    game_stats.append({
        'game_id': game_id,
        'team': team,
        'season': g['season'].iloc[0],
        'week': g['week'].iloc[0],
        'date': g['game_date'].iloc[0],
        'off_epa': plays['epa'].mean(),
        'success_rate': plays['success'].mean(),
        'explosive_rate': (plays['yards_gained'] >= 20).mean(),
        'sack_rate': dropbacks['sack'].fillna(False).astype(bool).mean() if len(dropbacks) > 0 else 0.0,
        'turnovers': g['interception'].fillna(False).astype(bool).sum() + g['fumble_lost'].fillna(False).astype(bool).sum(),
        'pts': g['posteam_score_post'].max(),
    })

stats_df = pd.DataFrame(game_stats)
stats_df['date'] = pd.to_datetime(stats_df['date'])
stats_df = stats_df.sort_values(['team', 'date']).reset_index(drop=True)

# ────── STEP 2: Rolling averages (last 4 games, EXCLUDING current) ──────
print("Computing rolling averages...")
stats_df['off_epa_roll4'] = stats_df.groupby('team')['off_epa'].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
stats_df['success_roll4'] = stats_df.groupby('team')['success_rate'].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
stats_df['explosive_roll4'] = stats_df.groupby('team')['explosive_rate'].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
stats_df['sack_roll4'] = stats_df.groupby('team')['sack_rate'].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
stats_df['to_roll4'] = stats_df.groupby('team')['turnovers'].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
stats_df['pts_roll4'] = stats_df.groupby('team')['pts'].transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())

# Defensive: same rolling on opponent side (need to know opponent)
# Create a lookup of opponent per game
opp_lookup = {}
for (game_id, team), g in pbp.groupby(['game_id', 'posteam']):
    if pd.isna(team):
        continue
    opp = g['defteam'].iloc[0]
    opp_lookup[(game_id, team)] = opp

stats_df['opp'] = stats_df.apply(lambda r: opp_lookup.get((r['game_id'], r['team']), None), axis=1)

# ────── STEP 3: Build game-level feature rows ──────
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

    # Get home team's rolling stats (as of before this game)
    h_stat = stats_df[(stats_df['game_id'] == game_id) & (stats_df['team'] == home)]
    a_stat = stats_df[(stats_df['game_id'] == game_id) & (stats_df['team'] == away)]

    if h_stat.empty or a_stat.empty:
        continue

    hs = h_stat.iloc[0]
    as_ = a_stat.iloc[0]

    games.append({
        'game_id': game_id, 'season': season, 'week': week, 'date': date,
        'home_team': home, 'away_team': away,
        'home_score': home_score, 'away_score': away_score,
        'home_win': 1 if home_score > away_score else 0,
        'home_off_epa_r4': hs['off_epa_roll4'],
        'away_off_epa_r4': as_['off_epa_roll4'],
        'home_success_r4': hs['success_roll4'],
        'away_success_r4': as_['success_roll4'],
        'home_explosive_r4': hs['explosive_roll4'],
        'away_explosive_r4': as_['explosive_roll4'],
        'home_sack_r4': hs['sack_roll4'],
        'away_sack_r4': as_['sack_roll4'],
        'home_to_r4': hs['to_roll4'],
        'away_to_r4': as_['to_roll4'],
        'home_pts_r4': hs['pts_roll4'],
        'away_pts_r4': as_['pts_roll4'],
    })

df = pd.DataFrame(games)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
df = df.dropna(subset=['home_off_epa_r4', 'away_off_epa_r4'])

df.to_csv('nfl_advanced_games_v5.csv', index=False)
print(f"\n✅ Built {len(df)} games with {len(df.columns)} cols (leakage-free)")
print(f"Columns: {list(df.columns)}")
