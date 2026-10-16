import nflreadpy as nfl
import polars as pl
import pandas as pd
import numpy as np

print("Loading play-by-play data...")
# Pull 2021-2025 play-by-play data
pbp = nfl.load_pbp([2021, 2022, 2023, 2024, 2025])

# Convert to pandas for easier manipulation if needed
pbp = pbp.to_pandas()

# Filter to regular season only
pbp = pbp[pbp['season_type'] == 'REG']

print(f"Loaded {len(pbp)} plays")

# ---- TEAM-LEVEL AGGREGATION PER GAME ----
games = []

for game_id, game_df in pbp.groupby('game_id'):
    home_team = game_df['home_team'].iloc[0]
    away_team = game_df['away_team'].iloc[0]
    season = game_df['season'].iloc[0]
    week = game_df['week'].iloc[0]
    game_date = game_df['game_date'].iloc[0]
    
    home_df = game_df[game_df['posteam'] == home_team]
    away_df = game_df[game_df['posteam'] == away_team]
    home_def_df = game_df[game_df['defteam'] == home_team]
    away_def_df = game_df[game_df['defteam'] == away_team]
    
    home_off_epa = home_df['epa'].mean() if len(home_df) > 0 else 0
    away_off_epa = away_df['epa'].mean() if len(away_df) > 0 else 0
    
    home_pass_epa = home_df[home_df['play_type'] == 'pass']['epa'].mean() if len(home_df[home_df['play_type'] == 'pass']) > 0 else 0
    home_rush_epa = home_df[home_df['play_type'] == 'run']['epa'].mean() if len(home_df[home_df['play_type'] == 'run']) > 0 else 0
    away_pass_epa = away_df[away_df['play_type'] == 'pass']['epa'].mean() if len(away_df[away_df['play_type'] == 'pass']) > 0 else 0
    away_rush_epa = away_df[away_df['play_type'] == 'run']['epa'].mean() if len(away_df[away_df['play_type'] == 'run']) > 0 else 0
    
    home_success = (home_df['epa'] > 0).mean() if len(home_df) > 0 else 0
    away_success = (away_df['epa'] > 0).mean() if len(away_df) > 0 else 0
    
    home_turnovers = len(home_df[home_df['interception'] == 1]) + len(home_df[home_df['fumble_lost'] == 1])
    away_turnovers = len(away_df[away_df['interception'] == 1]) + len(away_df[away_df['fumble_lost'] == 1])
    
    home_score = game_df['total_home_score'].max()
    away_score = game_df['total_away_score'].max()
    home_win = 1 if home_score > away_score else 0
    
    games.append({
        'game_id': game_id, 'season': season, 'week': week, 'date': game_date,
        'home_team': home_team, 'away_team': away_team,
        'home_score': home_score, 'away_score': away_score, 'home_win': home_win,
        'home_off_epa': home_off_epa, 'away_off_epa': away_off_epa,
        'home_pass_epa': home_pass_epa, 'home_rush_epa': home_rush_epa,
        'away_pass_epa': away_pass_epa, 'away_rush_epa': away_rush_epa,
        'home_success': home_success, 'away_success': away_success,
        'home_turnovers': home_turnovers, 'away_turnovers': away_turnovers,
        'home_def_epa': home_def_df['epa'].mean() if len(home_def_df) > 0 else 0,
        'away_def_epa': away_def_df['epa'].mean() if len(away_def_df) > 0 else 0,
    })

df = pd.DataFrame(games)
print(f"Built {len(df)} game records")
df.to_csv('nfl_advanced_games.csv', index=False)
print("Saved to nfl_advanced_games.csv")
