# NFL Betting Predictor — App Manifest

**Generated:** 2026-10-16 14:06  
**Repository:** https://github.com/NulllResult/NFL-Betting-Predictor  
**Local Path:** `C:\\Users\\User\\NFL-Betting-Predictor`  
**WSL Path:** `/mnt/c/Users/User/NFL-Betting-Predictor`  
**Theme:** Pittsburgh Steelers (gold #FFB612 on black #0B0F19)

---

## 1. Overview

An Android app + Flask backend that predicts NFL game outcomes using a
blended machine learning model and live sportsbook odds. Includes live
scores with real team logos, team/player stats, weather, injuries, news,
betting odds with implied probabilities, player props, historical
head-to-head, and a self-learning prediction log.

---

## 2. Architecture

```
┌─────────────────────────┐        ┌──────────────────────────┐
│  Android App (Kotlin)   │◄──────►│  Flask Backend (Python)  │
│  - Retrofit + coroutines│  HTTP  │  - betting_api.py        │
│  - jmDNS discovery      │        │  - feature_updater.py    │
│  - WorkManager notifs   │        │  - ML models (sklearn)   │
│  - ViewModel state      │        │  - mDNS broadcast        │
└─────────────────────────┘        └──────────────────────────┘
```

### Backend Data Sources
- ESPN Site API (live scores, schedules, rosters)
- Sportsipy (team stats, win/loss records)
- Tomorrow.io (weather — env var TOMORROW_API_KEY)
- The Odds API (spread/total/moneyline — env var ODDS_API_KEY)
- NFL PBP data (advanced features for ML)

### Android Networking
- Retrofit 2.9.0 + Gson converter
- Custom `Call<T>.await()` extension for coroutines
- OkHttp 4.12 with 5s connect / 15s read timeouts
- Background polling via WorkManager (15 min interval)

---

## 3. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Android Language | Kotlin | 1.9.x |
| Min SDK | Android 7.0 | API 24 |
| Target SDK | Android 14 | API 34 |
| Build System | Gradle Kotlin DSL | 8.x |
| HTTP Client | Retrofit | 2.9.0 |
| OkHttp | OkHttp | 4.12.0 |
| JSON | Gson | via converter-gson 2.9.0 |
| Async | Kotlin Coroutines | 1.7.3 |
| Lifecycle | androidx.lifecycle-runtime-ktx | 2.7.0 |
| UI | XML layouts + Material Components | 1.11.0 |
| Swipe Refresh | androidx.swiperefreshlayout | 1.1.0 |
| Background | androidx.work-runtime-ktx | 2.9.0 |
| mDNS | jmDNS | 3.5.9 |
| Backend | Flask | 3.x |
| CORS | flask-cors | latest |
| ML | scikit-learn (RandomForest + GradientBoosting) | latest |
| Data | pandas, polars, pyarrow, joblib | latest |
| NFL data | sportsipy, nflreadpy | latest |
| mDNS (server) | zeroconf | latest |
| Tests | JUnit 4 | 4.13.2 |

---

## 4. Features

### STATS Mode
- Dropdown to select any of 32 NFL teams
- Displays record, win %, PF/PA, streak
- Weather at stadium (temp, conditions, impact)
- Top 5 injuries (player, position, status)
- Top 3 recent news headlines
- Manual override support for offline teams

### PLAYER Mode
- Team dropdown → Roster loaded dynamically
- Player dropdown shows position + injury flag
- Season stats: passing, rushing, receiving
- Preseason stats (via HELP cycle)

### PREDICT Mode
- Displays current week's games grouped by day
- Real team logos from ESPN CDN in game cards
- Live game cards (Steelers gold stroke) / completed (dimmed)
- Tap a card → ML prediction with:
  - Real team logos in header
  - Predicted winner (with Unicode football icon)
  - Projected score
  - Model spread vs Market spread (side-by-side)
  - Total (model vs market)
  - Blended win probability with ASCII bars (█▓░)
  - ML model probability vs Market probability
  - Edge (colored, with contextual readout)
  - Confidence level badge (HIGH/MEDIUM/LOW)
  - Key factors with detail strings
  - Similar historical matchups (auto-loaded after prediction)

### HELP Button (14-state cycle)
1. HELP — instructions
2. ACCURACY — total/correct/%
3. PRED LOG — filterable (ALL/CORRECT/WRONG/PENDING/STARRED), star via long-press
4. LIVE PICKS — probability bars, momentum, projected finals
5. ODDS — implied %, vig, value badges
6. PROPS — player prop lines + recommendations
7. PRESEASON — preseason stats for current player
8. H2H — head-to-head comparison (record, points, streaks)
9. WK CHART — accuracy-by-week ASCII bar chart
10. BACKTEST — accuracy by confidence/side/edge/divisional
11. FIND SERVER — mDNS auto-discovery
12. NOTIFS — toggle live-game notifications
13. THEME — light/dark toggle
14. SERVER IP — change backend IP manually

Button label updates to show NEXT action (e.g., \ACCURACY →\)

### Score Banner
- Steelers logo on left
- Rotates 2 games at a time every 6 seconds
- Pauses when app is backgrounded

### Background Features
- ScoreCheckWorker: polls /live_scores every 15 min, fires notifications
  when games go from scheduled to LIVE (tracked in prefs)
- mDNS discovery: finds server on local network automatically

---

## 5. Project Structure

```
NFL-Betting-Predictor/
├── betting_api.py                # Flask server (24 endpoints)
├── feature_updater.py            # ML feature pipeline
├── build_features_v2.py          # PBP data builder v2
├── build_features_v3.py          # PBP data builder v3
├── generate_manifest.sh          # This script
├── APP_MANIFEST.md               # This file
├── NFL-Betting-Predictor.apk     # Installable APK
├── prediction_history.json       # Self-learning log (140+ entries)
├── nfl_advanced_games_v3.csv     # Current game data (2021-2026)
├── nfl_advanced_games_v2.csv     # Earlier version
├── nfl_advanced_games.csv        # Earliest version
├── training_data.csv             # ML training set
├── archive/legacy_data/          # Archived unused data files
│   ├── README.md
│   ├── enhanced_nfl_games.csv
│   ├── real_nfl_games.csv
│   ├── scoreboard.json
│   └── stats.json
├── ml_models/
│   ├── random_forest.pkl
│   ├── gradient_boosting.pkl
│   ├── feature_cols.pkl
│   └── team_strengths.pkl
└── app/
    ├── build.gradle.kts
    └── src/
        ├── main/
        │   ├── AndroidManifest.xml
        │   ├── java/com/bestg/betting/
        │   │   ├── MainActivity.kt              # All UI + state
        │   │   ├── MainViewModel.kt             # Cross-rotation state
        │   │   ├── ApiService.kt                # Retrofit interface
        │   │   ├── RetrofitExtensions.kt        # Call<T>.await()
        │   │   ├── AppLog.kt                    # Structured logging
        │   │   ├── ServerDiscovery.kt           # mDNS resolver
        │   │   ├── ScoreCheckWorker.kt          # Background notifier
        │   │   └── models/
        │   │       └── ApiModels.kt             # All response data classes
        │   └── res/
        │       ├── drawable/
        │       │   └── logo_*.png               # 32 team logos
        │       ├── layout/
        │       │   ├── activity_main.xml
        │       │   ├── spinner_item.xml
        │       │   └── spinner_dropdown_item.xml
        │       ├── mipmap-*/                    # Steelers launcher icons
        │       ├── values/
        │       │   ├── colors.xml
        │       │   ├── strings.xml
        │       │   └── themes.xml
        │       └── xml/
        │           ├── network_security_config.xml
        │           ├── backup_rules.xml
        │           └── data_extraction_rules.xml
        └── test/java/com/bestg/betting/
            ├── SpreadCalculationTest.kt         # 7 tests
            ├── EdgeLogicTest.kt                 # 7 tests
            ├── FilterLogicTest.kt               # 5 tests
            └── WeatherAdjustmentTest.kt         # 5 tests (24 total)
```

---

## 6. Backend API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/teams` | GET | — |
| `/health` | GET | — |
| `/test` | GET | — |
| `/team_stats` | GET | — |
| `/roster` | GET | — |
| `/player_stats` | GET | — |
| `/weather` | GET | — |
| `/injuries` | GET | — |
| `/news` | GET | — |
| `/win_loss` | GET | — |
| `/predict` | GET | — |
| `/preseason_stats` | GET | — |
| `/live_scores` | GET | — |
| `/accuracy_by_week` | GET | — |
| `/prediction_accuracy` | GET | — |
| `/record_prediction` | POST | — |
| `/live_prediction` | GET | — |
| `/odds` | GET | — |
| `/player_props` | GET | — |
| `/upcoming_games` | GET | — |
| `/consensus_odds` | GET | — |
| `/log_prediction` | POST | — |
| `/check_results` | GET | — |
| `/predict_with_market` | GET | — |
| `/prediction_log` | GET | — |
| `/model_report` | GET | — |
| `/misses_analysis` | GET | — |
| `/learning_report` | GET | — |
| `/similar_matchups` | GET | — |
| `/backtest` | GET | — |
| `/auto_tune` | GET | — |
| `/debug_prediction` | GET | — |
| `/ml_predict` | GET | — |

---

## 7. ML Model

- **Algorithms:** RandomForest + GradientBoosting (ensemble)
- **Features:** Rolling EPA, turnovers, weighted injuries, rest days,
  market-implied probability, team strength, home/away splits,
  divisional flag, weather point adjustments
- **Training data:** 2021-2026 advanced game data (`nfl_advanced_games_v3.csv`)
- **Blending:** Final probability = weighted avg of model + market
  - With market: 50/50 model + market (production)
  - Without market: model-only probability
- **Edge:** model_prob − market_prob (positive = value bet)
- **Total derivation:**
  - With market: uses market total directly
  - Without market: 45 − 0.5 × |spread|, clamped [34, 56]
- **Self-learning:** Every prediction logged to `prediction_history.json`,
  resolved automatically when the game completes

---

## 8. Colors (Steelers Theme)

| Name | Hex | Purpose |
|---|---|---|
| steelers_gold | #FFB612 | Primary accent |
| steelers_black | #0B0F19 | Main background |
| app_background | #0B0F19 | Base |
| app_surface | #1A1A1A | Panels |
| card_live_bg | #1A1A1A | Live game card |
| card_live_stroke | #FFB612 | Live game border (gold) |
| card_completed_bg | #0B0F19 | Finished game card |
| card_default_bg | #1A1A1A | Scheduled game card |
| text_primary | #FFFFFFFF | Body text |
| text_secondary | #8B949E | Labels |
| text_score_gold | #FFB612 | Score banner |
| edge_positive | #FF00FF88 | Positive edge |
| edge_negative | #FFFF6B6B | Negative edge |
| confidence_high | #FF00FF88 | HIGH confidence |
| confidence_medium | #FFFFB612 | MEDIUM confidence |
| confidence_low | #FFFF6B6B | LOW confidence |

---

## 9. Configuration

### Server IP (default)
```
10.0.0.60:5000
```
Changeable 3 ways:
1. HELP 14x → SERVER IP (manual entry)
2. HELP 11x → FIND SERVER (mDNS auto-discovery)
3. Persisted in SharedPreferences under key `server_ip`

### SharedPreferences keys
| Key | Type | Purpose |
|---|---|---|
| server_ip | String | Backend IP |
| favorite_teams | StringSet | Starred teams |
| manual_overrides_json | String | Manual overrides (JSON format) |
| manual_overrides | StringSet | Legacy pipe-delimited format (still readable) |
| watched_predictions | StringSet | Starred predictions |
| theme_mode | String | 'dark' or 'light' |
| notif_enabled | Boolean | Notifications toggle |
| notif_seen_live_games | StringSet | Track games already notified |

### API Keys
Both read from environment with fallback to embedded keys:
```bash
set TOMORROW_API_KEY=your_key_here   # Windows CMD
set ODDS_API_KEY=your_key_here
```

---

## 10. Build & Deploy

### Build APK
```bash
cmd.exe /c "cd /d C:\\Users\\User\\NFL-Betting-Predictor && gradlew clean assembleDebug"
```

### Run tests
```bash
cmd.exe /c "cd /d C:\\Users\\User\\NFL-Betting-Predictor && gradlew testDebugUnitTest"
```
Result: 24 tests in 4 suites (SpreadCalculation, EdgeLogic, FilterLogic, WeatherAdjustment)

### Copy APK to repo root
```bash
cp app/build/outputs/apk/debug/app-debug.apk NFL-Betting-Predictor.apk
```

### Commit and push
```bash
git add -A
git commit -m "message"
git push
```

### Restart the Flask server (Windows Task Scheduler)
```cmd
schtasks /end /tn NFLServer
schtasks /run /tn NFLServer
```

### Install on phone
Download `NFL-Betting-Predictor.apk` from GitHub → sideload → grant permissions

---

## 11. Testing

24 unit tests covering:
- Spread calculation from predicted score (7 tests)
- Edge logic and readout thresholds (7 tests)
- Prediction log filter behavior + data preservation (5 tests)
- Weather severity ordering (5 tests)

Run with: `gradlew testDebugUnitTest`

---

## 12. Recent Changes (last 5 commits)

```
a687557 Add .gitignore; untrack gradle cache, pycache, local.properties, temp scripts
08b0d9e Final phase: mDNS, notifications, ViewModel, tests, cleanup
c84258c Fix: Predicted spread calculates from predicted score
0e3fd94 Rename market section to SPORTSBOOK LINE
3e622c7 ML v3 with 2026 data, feature updater, latest APK
```

---

## 13. Known Limitations

- API keys embedded as fallback (rotate regularly; env vars override)
- Server IP defaults to 10.0.0.60 (configurable via prefs)
- Some UI state mirrors in MainActivity + ViewModel (full MVVM not extracted)
- WifiManager.connectionInfo is deprecated but still functional

---

*End of manifest. Regenerate with: `bash generate_manifest.sh`*
