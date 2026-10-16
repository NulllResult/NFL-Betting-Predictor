# NFL Betting Predictor — App Manifest

**Generated:** 2026-10-15 21:35  
**Repository:** https://github.com/NulllResult/NFL-Betting-Predictor  
**Local Path:** `C:\\Users\\User\\NFL-Betting-Predictor`  
**WSL Path:** `/mnt/c/Users/User/NFL-Betting-Predictor`

---

## 1. Overview

An Android app + Flask backend that predicts NFL game outcomes using a
blended machine learning model and live sportsbook odds. Includes live
scores, team/player stats, weather, injuries, news, betting odds, player
props, and a self-learning prediction log.

---

## 2. Architecture

```
┌─────────────────────────┐        ┌──────────────────────────┐
│  Android App (Kotlin)   │◄──────►│  Flask Backend (Python)  │
│  - Retrofit HTTP        │  HTTP  │  - betting_api.py        │
│  - Coroutines           │        │  - feature_updater.py    │
│  - XML layouts          │        │  - ML models (sklearn)   │
└─────────────────────────┘        └──────────────────────────┘
```

### Backend Data Sources
- ESPN Site API (live scores, schedules, rosters)
- Sportsipy (team stats, win/loss records)
- Tomorrow.io (weather, API key required)
- The Odds API (betting lines, API key required)
- NFL PBP data (advanced features for ML)

### Android Networking
- Retrofit 2.9.0 + Gson converter
- Custom `Call<T>.await()` extension for coroutines
- Polling live scores every 30s via Handler

---

## 3. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Android Language | Kotlin | 1.9.x |
| Min SDK | Android 7.0 | API 24 |
| Target SDK | Android 14 | API 34 |
| Build System | Gradle Kotlin DSL | 8.x |
| HTTP Client | Retrofit | 2.9.0 |
| JSON | Gson | via converter-gson 2.9.0 |
| Async | Kotlin Coroutines | 1.7.3 |
| Lifecycle | androidx.lifecycle-runtime-ktx | 2.7.0 |
| UI | XML layouts + Material Components | 1.11.0 |
| Swipe Refresh | androidx.swiperefreshlayout | 1.1.0 |
| Backend | Flask | 3.x |
| CORS | flask-cors | latest |
| ML | scikit-learn (RandomForest + GradientBoosting) | latest |
| Data | pandas, polars, pyarrow, joblib | latest |
| NFL data | sportsipy, nflreadpy | latest |

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
- Live game cards (red stroke) / completed (dimmed)
- Tap a card → ML prediction with:
  - Predicted winner + score
  - Model spread (calculated from predicted score)
  - Predicted total
  - Blended win probability
  - ML model probability vs Market probability
  - Edge (model - market)
  - Sportsbook line (spread + total)
  - Confidence % + level

### HELP Button (8-state cycle)
1. HELP — instructions
2. ACCURACY — total/correct/%
3. PRED LOG — full prediction history with ✓/✗/⏳
4. LIVE PICKS — in-game win probabilities
5. ODDS — spread, O/U, moneylines
6. PROPS — player prop lines + recommendations
7. PRESEASON — preseason stats for current player
8. SERVER IP — change backend IP

Button label updates to show NEXT action (e.g., "ACCURACY →")

---

## 5. Project Structure

```
NFL-Betting-Predictor/
├── betting_api.py                # Flask server (all endpoints)
├── feature_updater.py            # ML feature pipeline
├── build_features_v2.py          # PBP data builder v2
├── build_features_v3.py          # PBP data builder v3
├── generate_manifest.sh          # This script
├── APP_MANIFEST.md               # This file
├── NFL-Betting-Predictor.apk     # Installable APK
├── prediction_history.json       # Self-learning log
├── nfl_advanced_games_v3.csv     # Current game data (2021-2026)
├── training_data.csv             # ML training set
├── ml_models/
│   ├── random_forest.pkl
│   ├── gradient_boosting.pkl
│   ├── feature_cols.pkl
│   └── team_strengths.pkl
└── app/
    ├── build.gradle.kts
    └── src/main/
        ├── AndroidManifest.xml
        ├── java/com/bestg/betting/
        │   ├── MainActivity.kt              # All UI + state
        │   ├── ApiService.kt                # Retrofit interface
        │   ├── RetrofitExtensions.kt        # Call<T>.await()
        │   └── models/
        │       └── ApiModels.kt             # All data classes
        └── res/
            ├── layout/
            │   ├── activity_main.xml
            │   ├── spinner_item.xml
            │   └── spinner_dropdown_item.xml
            ├── values/
            │   ├── colors.xml
            │   ├── strings.xml
            │   └── themes.xml
            ├── values-night/
            │   └── themes.xml
            └── xml/
                ├── network_security_config.xml
                ├── backup_rules.xml
                └── data_extraction_rules.xml
```

---

## 6. Backend API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
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
| `/learning_report` | GET | — |
| `/auto_tune` | GET | — |
| `/ml_predict` | GET | — |

---

## 7. ML Model

- **Algorithms:** RandomForest + GradientBoosting (ensemble)
- **Features:** Rolling EPA, turnovers, weighted injuries, rest days,
  market-implied probability, team strength, home/away splits
- **Training data:** 2021-2026 advanced game data (`nfl_advanced_games_v3.csv`)
- **Blending:** Final probability = weighted avg of model + market
- **Edge:** model_prob − market_prob (positive = value bet)
- **Self-learning:** Every prediction logged to `prediction_history.json`,
  resolved automatically when the game completes

---

## 8. Colors (Theme)

| Name | Hex | Purpose |
|---|---|---|
| app_background | #FF1A1A2E | Main background |
| app_surface | #FF16213E | Panels |
| app_surface_dark | #FF0A0E1A | Games container |
| card_live_bg | #FF1A2F4A | Live game card |
| card_live_stroke | #FFFF4444 | Live game border |
| card_completed_bg | #FF141824 | Finished game card |
| card_default_bg | #FF1E2740 | Scheduled game card |
| text_primary | #FFDDE4F0 | Body text |
| text_secondary | #FF8899AA | Labels |
| text_white | #FFFFFFFF | Headers |
| text_score_gold | #FFFFD700 | Score banner |
| status_live | #FFFF4444 | LIVE indicator |
| status_final | #FF8899AA | FINAL indicator |
| status_upcoming | #FF4A9EFF | Scheduled indicator |
| text_winner | #FF00FF88 | Winning team |
| day_header | #FF4A9EFF | Day group header |
| text_error | #FFFF4444 | Error text |

---

## 9. Configuration

### Server IP (default)
```
10.0.0.60:5000
```
Changeable at runtime via HELP → SERVER IP. Persisted in SharedPreferences
under key `server_ip`.

### SharedPreferences keys
| Key | Type | Purpose |
|---|---|---|
| server_ip | String | Backend IP |
| favorite_teams | StringSet | Starred teams |
| manual_overrides | StringSet | Offline stat overrides |

### API Keys (in betting_api.py)
- TOMORROW_API_KEY (weather)
- ODDS_API_KEY (betting lines)

⚠️  **These are currently hardcoded. Move to env vars before public release.**

---

## 10. Build & Deploy

### Build APK
```bash
cmd.exe /c "cd /d C:\\Users\\User\\NFL-Betting-Predictor && gradlew clean assembleDebug"
```

### Copy APK to repo root
```bash
cp app/build/outputs/apk/debug/app-debug.apk NFL-Betting-Predictor.apk
```

### Commit and push
```bash
git add -f NFL-Betting-Predictor.apk app/src/main/java/com/bestg/betting/MainActivity.kt
git commit -m "message"
git push
```

### Restart the Flask server (Windows Task Scheduler)
```cmd
schtasks /end /tn NFLServer
schtasks /run /tn NFLServer
```

### Install on phone
Download `NFL-Betting-Predictor.apk` from GitHub → sideload → grant network permission

---

## 11. Known Issues / TODOs

- [ ] Score polling continues when app is backgrounded (battery drain)
- [ ] Retrofit has no explicit timeouts (slow servers hang the UI)
- [ ] API keys are hardcoded in `betting_api.py`
- [ ] Server IP is hardcoded (breaks for non-LAN installs)
- [ ] Prediction log shows all entries (no filter)
- [ ] `key_factors` field is unused in UI
- [ ] All UI logic still in MainActivity (~800 lines)
- [ ] No unit tests
- [ ] No ProGuard rules for release build
- [ ] Manual overrides serialize as pipe-delimited strings (fragile)

---

## 12. Git History (recent)

```
c84258c Fix: Predicted spread calculates from predicted score
0e3fd94 Rename market section to SPORTSBOOK LINE
3e622c7 ML v3 with 2026 data, feature updater, latest APK
42e4d41 Clean spread and whole-number totals
a07f374 Display spread and total in prediction
570d929 ML model 60% accuracy wired into app
0d24259 Market-derived scores, winner matches score
08b4761 Turnover diff, EPA, weighted injuries, market edge, calibrated confidence
ec7b291 HELP button cycles through actions with text visibility
e48e945 HELP button cycles through actions
21f67ae Add test network functions
dae963c Menu redesigned as number input
c067fc8 Dismiss dialog before running menu action
db4e7dc Reduce HELP menu to 4 items
cab0643 Wrap HELP menu in try/catch
070c7ec HELP button single-tap opens menu
f0442a4 Market cache, blend, auto-resolve on predict
6e5b38e Fix timezone: MNF shows Monday not Tuesday
b8a1488 REFRESH button becomes BACK when viewing prediction
a9f1d32 Pro dashboard with day-grouped cards
```

---

## 13. Recent Fixes

- **Predicted spread** now calculated from predicted score (not market line)
- **Market section** renamed to "SPORTSBOOK LINE" for clarity
- **parallel API calls** in getTeamStats via coroutines (6x faster)
- **onDestroy** cleanup for score polling Handler (memory leak fix)
- **Loading states** added to all API calls
- **Null-safety** on edge / blended / ml probabilities
- **Colors** moved from hardcoded hex to colors.xml
- **HELP button** label shows next action
- **TestActivity** removed from manifest (didn't exist)
- **preseason_stats** now wired into HELP cycle

---

*End of manifest. Regenerate with: `bash generate_manifest.sh`*
