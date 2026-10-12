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
    
    def safe_mean(col, df_):
        try: return float(df_[col].mean()) if col in df_.columns and len(df_) > 0 else 0
        except: return 0
    def safe_sum(col, df_):
        try: return float(df_[col].sum()) if col in df_.columns and len(df_) > 0 else 0
        except: return 0
    
    games.append({
        'game_id': game_id, 'season': season, 'week': week, 'date': date,
        'home_team': home, 'away_team': away,
        'home_score': g['total_home_score'].max(),
        'away_score': g['total_away_score'].max(),
        'home_win': 1 if g['total_home_score'].max() > g['total_away_score'].max() else 0,
        'home_off_epa': safe_mean('epa', h_off),
        'away_off_epa': safe_mean('epa', a_off),
        'home_def_epa': safe_mean('epa', h_def),
        'away_def_epa': safe_mean('epa', a_def),
        'home_success': safe_mean('success', h_off) if 'success' in h_off.columns else ((h_off['epa'] > 0).mean() if len(h_off) > 0 else 0),
        'away_success': safe_mean('success', a_off) if 'success' in a_off.columns else ((a_off['epa'] > 0).mean() if len(a_off) > 0 else 0),
        'home_turnovers': safe_sum('interception', h_off) + safe_sum('fumble_lost', h_off),
        'away_turnovers': safe_sum('interception', a_off) + safe_sum('fumble_lost', a_off),
    })

df = pd.DataFrame(games)
df.to_csv('nfl_advanced_games_v3.csv', index=False)
print(f"Built {len(df)} games")

# Show 2026 games
df['date'] = pd.to_datetime(df['date'])
recent = df[df['season'] == 2026].sort_values('date').tail(5)
print("\nLast 5 games of 2026:")
for _, r in recent.iterrows():
    print(f"  {r['date'].date()} - {r['away_team']} @ {r['home_team']} (score {r['away_score']}-{r['home_score']})")
print(f"\nTotal 2026 games: {len(df[df['season']==2026])}")
