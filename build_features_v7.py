import nflreadpy as nfl
import pandas as pd
import numpy as np

print("Loading PBP 2021-2026...")
pbp = nfl.load_pbp([2021, 2022, 2023, 2024, 2025, 2026]).to_pandas()
pbp = pbp[pbp['season_type'] == 'REG']
print(f"{len(pbp)} plays")

# Determine neutral-game-script plays: within 2 scores, first 3 quarters
# score_differential is from the offense's perspective
pbp['neutral'] = (
    (pbp['score_differential'].abs() <= 16) &
    (pbp['qtr'] <= 3)
)

print("Computing per-game team stats...")
game_stats = []
for (game_id, team), g in pbp.groupby(['game_id', 'posteam']):
    if pd.isna(team):
        continue
    plays = g[g['play_type'].isin(['pass', 'run'])]
    if len(plays) == 0:
        continue
    neutral_plays = plays[plays['neutral']]
    dropbacks = g[g['qb_dropback'] == 1]
    pass_plays = g[g['play_type'] == 'pass']
    neutral_pass = neutral_plays[neutral_plays['play_type'] == 'pass']

    # Drives
    drives = g[g['drive'].notna()].groupby('drive').agg(
        pts=('posteam_score_post', 'max'),
        start=('yardline_100', 'max'),
        plays=('play_id', 'count'),
    )
    rz_drives = drives[drives['start'] <= 20]
    gt_drives = drives[drives['start'] <= 5]
    scoring_drives = drives[drives['pts'] >= 3]

    # 3rd down EPA
    third = g[g['down'] == 3]
    third_epa = third['epa'].mean() if len(third) > 0 else 0.0

    # Red zone pass rate
    rz_plays = g[(g['yardline_100'] <= 20) & (g['play_type'].isin(['pass', 'run']))]
    rz_pass_rate = (rz_plays['play_type'] == 'pass').mean() if len(rz_plays) > 0 else 0.0

    # 2-minute drill EPA (last 2 min of 2nd quarter, or last 2 min of 4th when close)
    two_min = g[((g['qtr'] == 2) & (g['quarter_seconds_remaining'] <= 120)) |
                ((g['qtr'] == 4) & (g['quarter_seconds_remaining'] <= 120) & (g['score_differential'].abs() <= 8))]
    two_min_epa = two_min['epa'].mean() if len(two_min) > 0 else 0.0

    # Goal-to-go success
    gtg = g[g['goal_to_go'] == 1]
    gtg_success = gtg['success'].mean() if len(gtg) > 0 else 0.0

    # Drive success rate
    drive_success = len(scoring_drives) / len(drives) if len(drives) > 0 else 0.0

    # Avg drive start
    avg_start = drives['start'].mean() if len(drives) > 0 else 0.0

    # Plays per drive
    plays_per_drive = drives['plays'].mean() if len(drives) > 0 else 0.0

    # Neutral EPA
    neutral_epa = neutral_plays['epa'].mean() if len(neutral_plays) > 0 else 0.0

    game_stats.append({
        'game_id': game_id,
        'team': team,
        'season': g['season'].iloc[0],
        'week': g['week'].iloc[0],
        'date': g['game_date'].iloc[0],
        # Base (keep v6 features)
        'off_epa': plays['epa'].mean(),
        'success_rate': plays['success'].mean(),
        'explosive_rate': (plays['yards_gained'] >= 20).mean(),
        'sack_rate': dropbacks['sack'].fillna(False).astype(bool).mean() if len(dropbacks) > 0 else 0.0,
        'turnovers': g['interception'].fillna(False).astype(bool).sum() + g['fumble_lost'].fillna(False).astype(bool).sum(),
        'pts': g['posteam_score_post'].max(),
        'cpoe': pass_plays['cpoe'].mean() if 'cpoe' in pass_plays.columns else 0.0,
        'air_epa': pass_plays['air_epa'].mean() if 'air_epa' in pass_plays.columns else 0.0,
        'yac_epa': pass_plays['yac_epa'].mean() if 'yac_epa' in pass_plays.columns else 0.0,
        'xpass_rate': g['xpass'].mean() if 'xpass' in g.columns else 0.0,
        'series_success': g['series_success'].mean() if 'series_success' in g.columns else 0.0,
        'rz_td_rate': (rz_drives['pts'] >= 6).mean() if len(rz_drives) > 0 else 0.0,
        'qb_epa': g[g['qb_dropback'] == 1]['qb_epa'].mean() if 'qb_epa' in g.columns else 0.0,
        'pts_per_drive': drives['pts'].mean() if len(drives) > 0 else 0.0,
        # NEW v7 features
        'third_down_epa': third_epa,
        'rz_pass_rate': rz_pass_rate,
        'two_min_epa': two_min_epa,
        'gtg_success': gtg_success,
        'drive_success': drive_success,
        'avg_drive_start': avg_start,
        'plays_per_drive': plays_per_drive,
        'neutral_epa': neutral_epa,
    })

stats_df = pd.DataFrame(game_stats)
stats_df['date'] = pd.to_datetime(stats_df['date'])
stats_df = stats_df.sort_values(['team', 'date']).reset_index(drop=True)

print("Computing rolling averages...")
roll_cols = ['off_epa', 'success_rate', 'explosive_rate', 'sack_rate', 'turnovers', 'pts',
             'cpoe', 'air_epa', 'yac_epa', 'xpass_rate', 'series_success', 'rz_td_rate', 'qb_epa', 'pts_per_drive',
             'third_down_epa', 'rz_pass_rate', 'two_min_epa', 'gtg_success', 'drive_success',
             'avg_drive_start', 'plays_per_drive', 'neutral_epa']
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
df.to_csv('nfl_advanced_games_v7.csv', index=False)
print(f"\n✅ Built {len(df)} games with {len(df.columns)} cols")
print(f"Feature cols count: {len([c for c in df.columns if '_r4' in c])}")
