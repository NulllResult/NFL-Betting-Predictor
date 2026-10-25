import requests
import sys
sys.path.insert(0, ".")
from feature_updater import predict_ml_probability
import joblib
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

# ─────────────────────────────────────────────────────────────
# OPTIONAL: Rate limiting + production serving
# Install with: pip install flask-limiter gunicorn
# Uncomment below and the @limiter.limit decorators on routes
# ─────────────────────────────────────────────────────────────
# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
# limiter = Limiter(app, key_func=get_remote_address,
#                   default_limits=["120 per minute"])
#
# To run in production instead of flask dev server:
#   gunicorn -w 4 -b 0.0.0.0:5000 betting_api:app
# ─────────────────────────────────────────────────────────────


from datetime import datetime
import time
import os

app = Flask(__name__)
CORS(app)

try:
    from sportsipy.nfl.roster import Roster
    SPORTSIPY_AVAILABLE = True
    print("Sportsipy loaded successfully")
except ImportError:
    SPORTSIPY_AVAILABLE = False
    print("Sportsipy not available")

# API keys — read from environment. Fallbacks are the original keys so
# nothing breaks if env vars aren't set.
import os as _os
TOMORROW_API_KEY = _os.environ.get("TOMORROW_API_KEY", "4jUTfSnJ2t7VJjG5zRKh5gR6K8m2JhyM")
ODDS_API_KEY = _os.environ.get("ODDS_API_KEY", "daebc38f7fa4559b6d3f77a82a1a16dc")


def cache_get(key, ttl=None):
    """Unified cache read with per-key TTL. Returns None if missing or expired."""
    import time as _t
    if ttl is None:
        ttl = cache_timeout
    entry = cache.get(key)
    if not entry:
        return None
    val, ts = entry
    if _t.time() - ts > ttl:
        cache.pop(key, None)
        return None
    return val


def cache_set(key, value):
    """Unified cache write. Timestamp is auto-recorded."""
    import time as _t
    cache[key] = (value, _t.time())



# Freeze predictions within 5 min of kickoff so users don't see flicker
FREEZE_WINDOW_SECONDS = 300
_frozen_predictions = {}   # key: "team1|team2" -> {prediction, locked_at}


def _should_freeze(kickoff_iso):
    """Return True if we're within the freeze window before kickoff."""
    if not kickoff_iso:
        return False
    try:
        from datetime import datetime as _dt
        ko = _dt.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
        now = _dt.now(ko.tzinfo)
        delta = (ko - now).total_seconds()
        return 0 <= delta <= FREEZE_WINDOW_SECONDS
    except Exception:
        return False


cache = {}
cache_timeout = 300
market_cache = {"data": None, "time": 0}
MARKET_CACHE_TTL = 300
ESPN_SITE_V2 = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# Manual overrides storage
manual_overrides = {}

# Prediction history tracking
import json as json_lib
PREDICTIONS_FILE = "prediction_history.json"

def load_prediction_history():
    try:
        if os.path.exists(PREDICTIONS_FILE):
            with open(PREDICTIONS_FILE, 'r') as f:
                return json_lib.load(f)
    except:
        pass
    return []

def save_prediction_history(history):
    try:
        with open(PREDICTIONS_FILE, 'w') as f:
            json_lib.dump(history[-500:], f)  # keep last 500
    except:
        pass



STADIUM_LOCATIONS = {
    "Buffalo Bills": {"city": "Buffalo", "lat": 42.7738, "lon": -78.7870, "stadium": "Highmark Stadium"},
    "Miami Dolphins": {"city": "Miami", "lat": 25.9580, "lon": -80.2389, "stadium": "Hard Rock Stadium"},
    "New England Patriots": {"city": "Foxborough", "lat": 42.0909, "lon": -71.2643, "stadium": "Gillette Stadium"},
    "New York Jets": {"city": "East Rutherford", "lat": 40.8136, "lon": -74.0744, "stadium": "MetLife Stadium"},
    "Baltimore Ravens": {"city": "Baltimore", "lat": 39.2780, "lon": -76.6227, "stadium": "M&T Bank Stadium"},
    "Cincinnati Bengals": {"city": "Cincinnati", "lat": 39.0954, "lon": -84.5161, "stadium": "Paycor Stadium"},
    "Cleveland Browns": {"city": "Cleveland", "lat": 41.5061, "lon": -81.6995, "stadium": "Huntington Bank Field"},
    "Pittsburgh Steelers": {"city": "Pittsburgh", "lat": 40.4468, "lon": -80.0158, "stadium": "Acrisure Stadium"},
    "Houston Texans": {"city": "Houston", "lat": 29.6847, "lon": -95.4107, "stadium": "NRG Stadium"},
    "Indianapolis Colts": {"city": "Indianapolis", "lat": 39.7601, "lon": -86.1639, "stadium": "Lucas Oil Stadium"},
    "Jacksonville Jaguars": {"city": "Jacksonville", "lat": 30.3240, "lon": -81.6375, "stadium": "EverBank Stadium"},
    "Tennessee Titans": {"city": "Nashville", "lat": 36.1664, "lon": -86.7714, "stadium": "Nissan Stadium"},
    "Denver Broncos": {"city": "Denver", "lat": 39.7439, "lon": -105.0201, "stadium": "Empower Field"},
    "Kansas City Chiefs": {"city": "Kansas City", "lat": 39.0489, "lon": -94.4839, "stadium": "Arrowhead Stadium"},
    "Las Vegas Raiders": {"city": "Las Vegas", "lat": 36.0909, "lon": -115.1836, "stadium": "Allegiant Stadium"},
    "Los Angeles Chargers": {"city": "Inglewood", "lat": 33.9535, "lon": -118.3394, "stadium": "SoFi Stadium"},
    "Dallas Cowboys": {"city": "Arlington", "lat": 32.7473, "lon": -97.0945, "stadium": "AT&T Stadium"},
    "New York Giants": {"city": "East Rutherford", "lat": 40.8136, "lon": -74.0744, "stadium": "MetLife Stadium"},
    "Philadelphia Eagles": {"city": "Philadelphia", "lat": 39.9011, "lon": -75.1677, "stadium": "Lincoln Financial Field"},
    "Washington Commanders": {"city": "Landover", "lat": 38.9076, "lon": -76.8645, "stadium": "FedExField"},
    "Chicago Bears": {"city": "Chicago", "lat": 41.8625, "lon": -87.6167, "stadium": "Soldier Field"},
    "Detroit Lions": {"city": "Detroit", "lat": 42.3400, "lon": -83.0456, "stadium": "Ford Field"},
    "Green Bay Packers": {"city": "Green Bay", "lat": 44.5013, "lon": -88.0622, "stadium": "Lambeau Field"},
    "Minnesota Vikings": {"city": "Minneapolis", "lat": 44.9739, "lon": -93.2577, "stadium": "U.S. Bank Stadium"},
    "Atlanta Falcons": {"city": "Atlanta", "lat": 33.7550, "lon": -84.4000, "stadium": "Mercedes-Benz Stadium"},
    "Carolina Panthers": {"city": "Charlotte", "lat": 35.2258, "lon": -80.8528, "stadium": "Bank of America Stadium"},
    "New Orleans Saints": {"city": "New Orleans", "lat": 29.9509, "lon": -90.0811, "stadium": "Caesars Superdome"},
    "Tampa Bay Buccaneers": {"city": "Tampa", "lat": 27.9760, "lon": -82.5033, "stadium": "Raymond James Stadium"},
    "Arizona Cardinals": {"city": "Glendale", "lat": 33.5275, "lon": -112.2625, "stadium": "State Farm Stadium"},
    "Los Angeles Rams": {"city": "Inglewood", "lat": 33.9535, "lon": -118.3394, "stadium": "SoFi Stadium"},
    "San Francisco 49ers": {"city": "Santa Clara", "lat": 37.4031, "lon": -121.9698, "stadium": "Levi's Stadium"},
    "Seattle Seahawks": {"city": "Seattle", "lat": 47.5952, "lon": -122.3316, "stadium": "Lumen Field"}
}

TEAM_MAP = {
    "Buffalo Bills": "buf", "Miami Dolphins": "mia", "New England Patriots": "ne", "New York Jets": "nyj",
    "Baltimore Ravens": "bal", "Cincinnati Bengals": "cin", "Cleveland Browns": "cle", "Pittsburgh Steelers": "pit",
    "Houston Texans": "hou", "Indianapolis Colts": "ind", "Jacksonville Jaguars": "jax", "Tennessee Titans": "ten",
    "Denver Broncos": "den", "Kansas City Chiefs": "kc", "Las Vegas Raiders": "lv", "Los Angeles Chargers": "lac",
    "Dallas Cowboys": "dal", "New York Giants": "nyg", "Philadelphia Eagles": "phi", "Washington Commanders": "wsh",
    "Chicago Bears": "chi", "Detroit Lions": "det", "Green Bay Packers": "gb", "Minnesota Vikings": "min",
    "Atlanta Falcons": "atl", "Carolina Panthers": "car", "New Orleans Saints": "no", "Tampa Bay Buccaneers": "tb",
    "Arizona Cardinals": "ari", "Los Angeles Rams": "lar", "San Francisco 49ers": "sf", "Seattle Seahawks": "sea"
}

TEAM_KEYWORDS = {
    "Buffalo Bills": ["Bills", "Buffalo"], "Miami Dolphins": ["Dolphins", "Miami"],
    "New England Patriots": ["Patriots", "New England"], "New York Jets": ["Jets"],
    "Baltimore Ravens": ["Ravens", "Baltimore"], "Cincinnati Bengals": ["Bengals", "Cincinnati"],
    "Cleveland Browns": ["Browns", "Cleveland"], "Pittsburgh Steelers": ["Steelers", "Pittsburgh"],
    "Houston Texans": ["Texans", "Houston"], "Indianapolis Colts": ["Colts", "Indianapolis"],
    "Jacksonville Jaguars": ["Jaguars", "Jacksonville"], "Tennessee Titans": ["Titans", "Tennessee"],
    "Denver Broncos": ["Broncos", "Denver"], "Kansas City Chiefs": ["Chiefs", "Kansas City"],
    "Las Vegas Raiders": ["Raiders", "Las Vegas"], "Los Angeles Chargers": ["Chargers"],
    "Dallas Cowboys": ["Cowboys", "Dallas"], "New York Giants": ["Giants"],
    "Philadelphia Eagles": ["Eagles", "Philadelphia"], "Washington Commanders": ["Commanders", "Washington"],
    "Chicago Bears": ["Bears", "Chicago"], "Detroit Lions": ["Lions", "Detroit"],
    "Green Bay Packers": ["Packers", "Green Bay"], "Minnesota Vikings": ["Vikings", "Minnesota"],
    "Atlanta Falcons": ["Falcons", "Atlanta"], "Carolina Panthers": ["Panthers", "Carolina"],
    "New Orleans Saints": ["Saints", "New Orleans"], "Tampa Bay Buccaneers": ["Buccaneers", "Bucs", "Tampa Bay"],
    "Arizona Cardinals": ["Cardinals", "Arizona"], "Los Angeles Rams": ["Rams"],
    "San Francisco 49ers": ["49ers", "San Francisco", "Niners"], "Seattle Seahawks": ["Seahawks", "Seattle"]
}

def get_cached_or_fetch(url, cache_key):
    if cache_key in cache:
        data, timestamp = cache[cache_key]
        if time.time() - timestamp < cache_timeout:
            return data
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            cache[cache_key] = (data, time.time())
            return data
        return None
    except:
        return None

def get_weather_from_api(team_name):
    if team_name not in STADIUM_LOCATIONS:
        return None
    location = STADIUM_LOCATIONS[team_name]
    try:
        url = "https://api.tomorrow.io/v4/timelines"
        params = {
            "location": f"{location['lat']},{location['lon']}",
            "fields": ["temperature", "weatherCode", "windSpeed", "precipitationProbability"],
            "timesteps": "current", "units": "imperial", "apikey": TOMORROW_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data['data']['timelines'][0]['intervals'][0]['values']
            weather_codes = {1000: "Clear", 1100: "Mostly Clear", 1101: "Partly Cloudy", 1102: "Mostly Cloudy",
                1001: "Cloudy", 4000: "Rain", 4200: "Light Rain", 4201: "Heavy Rain",
                5000: "Snow", 5100: "Light Snow", 5101: "Heavy Snow", 8000: "Thunderstorm"}
            conditions = weather_codes.get(current.get('weatherCode', 1000), "Unknown")
            wind = current.get('windSpeed', 0)
            precip = current.get('precipitationProbability', 0)
            temp = current.get('temperature', 45)
            impact = "Minimal impact"
            if wind > 20: impact = f"HIGH WIND ({wind} mph)"
            elif wind > 15: impact = f"Moderate wind ({wind} mph)"
            elif precip > 70: impact = f"Heavy rain ({precip}%)"
            elif temp < 32: impact = f"Freezing ({temp}F)"
            return {"temperature": round(temp), "conditions": conditions, "wind_speed": round(wind),
                "precipitation": precip, "city": location["city"], "stadium": location["stadium"], "impact": impact}
        return None
    except:
        return None

def get_player_stats_sportsipy(player_name, team_name):
    if not SPORTSIPY_AVAILABLE:
        return None
    try:
        team_abbr_map = {
            "Buffalo Bills": "BUF", "Miami Dolphins": "MIA", "New England Patriots": "NE",
            "New York Jets": "NYJ", "Baltimore Ravens": "BAL", "Cincinnati Bengals": "CIN",
            "Cleveland Browns": "CLE", "Pittsburgh Steelers": "PIT", "Houston Texans": "HOU",
            "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX", "Tennessee Titans": "TEN",
            "Denver Broncos": "DEN", "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV",
            "Los Angeles Chargers": "LAC", "Dallas Cowboys": "DAL", "New York Giants": "NYG",
            "Philadelphia Eagles": "PHI", "Washington Commanders": "WAS", "Chicago Bears": "CHI",
            "Detroit Lions": "DET", "Green Bay Packers": "GB", "Minnesota Vikings": "MIN",
            "Atlanta Falcons": "ATL", "Carolina Panthers": "CAR", "New Orleans Saints": "NO",
            "Tampa Bay Buccaneers": "TB", "Arizona Cardinals": "ARI", "Los Angeles Rams": "LAR",
            "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA"
        }
        team_abbr = team_abbr_map.get(team_name)
        if not team_abbr:
            return None
        print(f"[SPORTSIPY] Looking for {player_name} on {team_abbr}...")
        roster = Roster(team_abbr)
        for player in roster.players:
            if player_name.lower() in player.name.lower():
                print(f"[SPORTSIPY] Found: {player.name}")
                stats = {}
                try:
                    stats['passing_yards'] = int(player.passing_yards or 0)
                    stats['passing_tds'] = int(player.passing_touchdowns or 0)
                    stats['completions'] = int(player.passing_completions or 0)
                    stats['passing_attempts'] = int(player.passing_attempts or 0)
                    stats['interceptions'] = int(player.passing_interceptions or 0)
                    stats['qb_rating'] = float(player.quarterback_rating or 0)
                except: pass
                try:
                    stats['rushing_yards'] = int(player.rushing_yards or 0)
                    stats['rushing_tds'] = int(player.rushing_touchdowns or 0)
                    stats['rushing_attempts'] = int(player.rushing_attempts or 0)
                except: pass
                try:
                    stats['receiving_yards'] = int(player.receiving_yards or 0)
                    stats['receiving_tds'] = int(player.receiving_touchdowns or 0)
                    stats['receptions'] = int(player.receptions or 0)
                    stats['targets'] = int(player.receiving_targets or 0)
                except: pass
                print(f"[SPORTSIPY] Stats: {stats}")
                return stats if stats else None
    except Exception as e:
        print(f"[SPORTSIPY] Error: {e}")
    return None

def get_mock_player_stats(player_id, player_name):
    """No mock data - return None when real stats unavailable"""
    return None



# ─────────────────────────────────────────────────────────────
# DIVISIONAL MAP — determines divisional matchups
# ─────────────────────────────────────────────────────────────
DIVISIONS = {
    "Buffalo Bills": "AFC East", "Miami Dolphins": "AFC East",
    "New England Patriots": "AFC East", "New York Jets": "AFC East",
    "Baltimore Ravens": "AFC North", "Cincinnati Bengals": "AFC North",
    "Cleveland Browns": "AFC North", "Pittsburgh Steelers": "AFC North",
    "Houston Texans": "AFC South", "Indianapolis Colts": "AFC South",
    "Jacksonville Jaguars": "AFC South", "Tennessee Titans": "AFC South",
    "Denver Broncos": "AFC West", "Kansas City Chiefs": "AFC West",
    "Las Vegas Raiders": "AFC West", "Los Angeles Chargers": "AFC West",
    "Dallas Cowboys": "NFC East", "New York Giants": "NFC East",
    "Philadelphia Eagles": "NFC East", "Washington Commanders": "NFC East",
    "Chicago Bears": "NFC North", "Detroit Lions": "NFC North",
    "Green Bay Packers": "NFC North", "Minnesota Vikings": "NFC North",
    "Atlanta Falcons": "NFC South", "Carolina Panthers": "NFC South",
    "New Orleans Saints": "NFC South", "Tampa Bay Buccaneers": "NFC South",
    "Arizona Cardinals": "NFC West", "Los Angeles Rams": "NFC West",
    "San Francisco 49ers": "NFC West", "Seattle Seahawks": "NFC West",
}


def is_divisional(team1, team2):
    """True if both teams share the same division."""
    return DIVISIONS.get(team1) is not None and DIVISIONS.get(team1) == DIVISIONS.get(team2)


def weather_point_adjustment(weather):
    """Return points to subtract from total based on weather severity."""
    if not weather:
        return 0.0
    adj = 0.0
    wind = weather.get("wind_speed") or 0
    temp = weather.get("temperature") or 70
    precip = weather.get("precipitation") or 0

    if wind >= 25: adj -= 6.0
    elif wind >= 20: adj -= 4.0
    elif wind >= 15: adj -= 2.5
    elif wind >= 10: adj -= 1.0

    if temp <= 15: adj -= 4.0
    elif temp <= 25: adj -= 2.5
    elif temp <= 35: adj -= 1.0

    if precip >= 70: adj -= 3.0
    elif precip >= 50: adj -= 1.5

    return adj


@app.route('/teams', methods=['GET'])
def teams():
    """Return the canonical NFL team list."""
    return jsonify({
        "teams": list(TEAM_MAP.keys()),
        "count": len(TEAM_MAP)
    })

@app.route('/health', methods=['GET'])
def health():
    """Real diagnostics — which upstream APIs are reachable, cache state."""
    import time as _t
    upstream = {}
    try:
        r = requests.get(f"{ESPN_SITE_V2}/scoreboard", timeout=3)
        upstream["espn"] = "ok" if r.status_code == 200 else f"http {r.status_code}"
    except Exception as e:
        upstream["espn"] = f"err: {str(e)[:40]}"
    upstream["tomorrow"] = "configured" if TOMORROW_API_KEY else "missing_key"
    upstream["odds"] = "configured" if ODDS_API_KEY else "missing_key"

    return jsonify({
        "status": "ok",
        "cache_size": len(cache),
        "market_cache_age_s": int(_t.time() - market_cache.get("time", 0)) if market_cache.get("data") else None,
        "upstream_apis": upstream,
        "predictions_logged": len(load_prediction_history()),
        "server_time": datetime.now().isoformat(),
    })


# ─────────────────────────────────────────────────────────────
# CALIBRATION — converts raw model confidence into real-world accuracy
# Empirically learned from /backtest data. Recomputed weekly.
# ─────────────────────────────────────────────────────────────
# Default table (conservative, based on typical NFL model results).
# Updated by /auto_tune once 100+ resolved predictions are logged.
# Coarser buckets — better statistical power with <500 predictions.
# Once you hit 500+ resolved, subdivide into 5-point intervals.
CALIBRATION_TABLE = {
    (0, 50): 0.52,
    (50, 60): 0.55,
    (60, 70): 0.60,
    (70, 80): 0.65,
    (80, 100): 0.70,
}


def calibrated_confidence(raw_prob_pct):
    """Convert a raw model confidence (distance from 50) to real accuracy."""
    bucket_prob = max(50, min(100, 50 + abs(raw_prob_pct - 50)))
    for (lo, hi), rate in CALIBRATION_TABLE.items():
        if lo <= bucket_prob < hi:
            return round(rate * 100, 1)
    return 52.0


def _update_calibration_table_from_history():
    """
    Rebuild CALIBRATION_TABLE from actual resolved predictions.
    Called by /auto_tune weekly. Requires 100+ resolved games.
    """
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]
    if len(resolved) < 100:
        return False

    buckets = {(0, 50): [], (50, 60): [], (60, 70): [], (70, 80): [], (80, 100): []}
    for e in resolved:
        conf = e.get("confidence") or 0
        # Recency weight: last 4 weeks ×3, everything else ×1
        wk = e.get("week") or 0
        try:
            wk = int(str(wk).replace("W", ""))
        except Exception:
            wk = 0
        try:
            current_week = int(str(load_current_week()).replace("W", ""))
        except Exception:
            current_week = 18
        weight = 3.0 if (current_week - wk) <= 4 else 1.0

        for (lo, hi) in buckets:
            if lo <= conf < hi:
                buckets[(lo, hi)].append((1 if e.get("correct") else 0, weight))
                break

    global CALIBRATION_TABLE

    new_table = {}
    for key, results in buckets.items():
        if len(results) >= 10:
            new_table[key] = round(sum(results) / len(results), 4)
        else:
            new_table[key] = CALIBRATION_TABLE.get(key, 0.52)

    CALIBRATION_TABLE = new_table
    return True


# ─────────────────────────────────────────────────────────────
# QB RECENCY — rolling EPA over last N games
# ─────────────────────────────────────────────────────────────
def get_qb_recent_epa(team_name, last_n=4):
    """
    Rolling QB EPA over last N games. Falls back to season average.
    Uses ESPN + team stats as best available proxy.
    """
    try:
        import pandas as pd
        df = pd.read_csv("nfl_advanced_games_v3.csv")
        abbr = TEAM_MAP.get(team_name, "").upper()
        if not abbr:
            return None
        # Find last N games for this team
        mask = (df["home_team"].str.upper() == abbr) | (df["away_team"].str.upper() == abbr)
        games = df[mask].sort_values(["season", "week"], ascending=False).head(last_n)
        if games.empty:
            return None
        epas = []
        for _, g in games.iterrows():
            if g["home_team"].upper() == abbr:
                epas.append(g.get("home_off_epa", 0))
            else:
                epas.append(g.get("away_off_epa", 0))
        return sum(epas) / len(epas) if epas else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# LINE MOVEMENT — sharp money signal
# ─────────────────────────────────────────────────────────────
_opening_lines = {}   # game_id or "team1|team2" -> {spread, total, time}


def record_opening_line(team1, team2, spread, total):
    """Store the first line we see for a matchup."""
    key = f"{team1}|{team2}"
    if key not in _opening_lines:
        import time as _t
        _opening_lines[key] = {"spread": spread, "total": total, "time": _t.time()}


def get_line_movement(team1, team2, current_spread):
    """Return how much the line moved from opening."""
    key = f"{team1}|{team2}"
    if key not in _opening_lines or current_spread is None:
        return None
    opening = _opening_lines[key].get("spread")
    if opening is None:
        return None
    return round(current_spread - opening, 2)


# ─────────────────────────────────────────────────────────────
# PRIMETIME / TNF detection
# ─────────────────────────────────────────────────────────────
def classify_game_slot(kickoff_iso):
    """
    Return 'TNF', 'SNF', 'MNF', 'SUNDAY_EARLY', 'SUNDAY_LATE', or 'UNKNOWN'.
    Based on day-of-week + time-of-day in ET.
    """
    if not kickoff_iso:
        return "UNKNOWN"
    try:
        from datetime import datetime as _dt
        import pytz
        ko = _dt.fromisoformat(kickoff_iso.replace("Z", "+00:00"))
        et = ko.astimezone(pytz.timezone("America/New_York"))
        weekday = et.weekday()   # 0 = Monday
        hour = et.hour
        if weekday == 3:  # Thursday
            return "TNF"
        if weekday == 6 and hour >= 20:  # Sunday night
            return "SNF"
        if weekday == 0 and hour >= 20:  # Monday night
            return "MNF"
        if weekday == 6:  # Sunday
            return "SUNDAY_EARLY" if hour < 16 else "SUNDAY_LATE"
        return "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def slot_adjustments(slot):
    """Return (spread_multiplier, total_delta) for a given game slot."""
    if slot == "TNF":
        return (0.85, -3.0)     # compressed scoring, tighter spreads
    if slot == "SNF":
        return (0.95, -1.0)
    if slot == "MNF":
        return (1.00, -1.5)
    if slot == "SUNDAY_EARLY":
        return (1.00, 0.0)
    if slot == "SUNDAY_LATE":
        return (1.00, +0.5)
    return (1.00, 0.0)


# ─────────────────────────────────────────────────────────────
# CLV — Closing Line Value
# ─────────────────────────────────────────────────────────────
def compute_clv(predicted_spread, closing_spread):
    """
    CLV = predicted_spread - closing_spread.
    Positive = you got a better number than the market closed at.
    """
    if predicted_spread is None or closing_spread is None:
        return None
    return round(predicted_spread - closing_spread, 2)




# ─────────────────────────────────────────────────────────────
# DRIFT DETECTION
# Alerts when rolling accuracy drops significantly below baseline.
# ─────────────────────────────────────────────────────────────
def detect_drift(window=30, threshold_pct=10.0):
    """
    Compare rolling N-game accuracy vs lifetime baseline.
    Returns drift flag + details if rolling is > threshold below baseline.
    """
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]
    if len(resolved) < window + 10:
        return {
            "status": "need_more_data",
            "resolved": len(resolved),
            "needed": window + 10
        }

    # Sort by resolution timestamp (fallback to date string)
    def _key(e):
        return e.get("resolved_at") or 0
    resolved.sort(key=_key)

    rolling = resolved[-window:]
    baseline = resolved[:-window]

    roll_acc = 100.0 * sum(1 for e in rolling if e.get("correct")) / len(rolling)
    base_acc = 100.0 * sum(1 for e in baseline if e.get("correct")) / len(baseline) if baseline else 0.0

    drift = roll_acc < (base_acc - threshold_pct)

    return {
        "status": "drift" if drift else "healthy",
        "rolling_window": window,
        "rolling_accuracy": round(roll_acc, 1),
        "baseline_accuracy": round(base_acc, 1),
        "gap": round(base_acc - roll_acc, 1),
        "threshold": threshold_pct,
        "message": f"Model has dropped {round(base_acc - roll_acc, 1)} points over last {window} games" if drift else "No drift detected"
    }


# ─────────────────────────────────────────────────────────────
# ADAPTIVE BLENDING
# Learns optimal model/market weight from historical performance.
# ─────────────────────────────────────────────────────────────
def get_adaptive_blend_weight():
    """
    Return the weight to give the market (0.0-1.0) based on which has
    been more accurate recently.
    - If market is 5% more accurate than model: weight 0.70 to market
    - If model is 5% more accurate: weight 0.35 to market (model-favored)
    - Default: 0.50 (equal blend)
    """
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]
    # Only count games where market data was available
    market_games = [e for e in resolved if e.get("market_correct") is not None]
    if len(market_games) < 30:
        return 0.50   # not enough data — use default

    model_acc = 100.0 * sum(1 for e in market_games if e.get("correct")) / len(market_games)
    market_acc = 100.0 * sum(1 for e in market_games if e.get("market_correct")) / len(market_games)

    gap = model_acc - market_acc
    if gap >= 8:
        return 0.30   # model is much better — trust it more
    if gap >= 3:
        return 0.40
    if gap <= -8:
        return 0.75   # market is much better — trust it more
    if gap <= -3:
        return 0.65
    return 0.50


# ─────────────────────────────────────────────────────────────
# TEAM BIAS TRACKING
# Which teams does the model systematically misjudge?
# ─────────────────────────────────────────────────────────────
def get_team_bias_report(min_games=3):
    """
    Return per-team accuracy for the model. Teams with 0-N records
    are candidates for model bias / stale data.
    """
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]

    teams = {}   # team_name -> [correct_count, total_count]
    for e in resolved:
        winner = e.get("predicted_winner")
        if not winner:
            continue
        teams.setdefault(winner, []).append(1 if e.get("correct") else 0)

    report = []
    for team, results in teams.items():
        if len(results) < min_games:
            continue
        correct = sum(results)
        total = len(results)
        acc = 100.0 * correct / total
        report.append({
            "team": team,
            "correct": correct,
            "total": total,
            "accuracy": round(acc, 1),
            "bias": "cold" if acc < 40 else "hot" if acc > 75 else "normal"
        })

    report.sort(key=lambda x: x["accuracy"])
    return report


# ─────────────────────────────────────────────────────────────
# AUTO-RESOLVE DAEMON
# Runs check_results_internal() every 30 minutes in a background
# thread. Eliminates the "107 pending, 40 resolved" backlog.
# ─────────────────────────────────────────────────────────────
import threading as _threading
_auto_resolve_thread = None
_auto_resolve_stop = _threading.Event()


def _auto_resolve_loop():
    """Background thread: resolve pending predictions every 30 min."""
    import time as _t
    # Wait 60s after server start before first run
    _auto_resolve_stop.wait(60)
    while not _auto_resolve_stop.is_set():
        try:
            updated = check_results_internal()
            if updated > 0:
                print(f"[auto-resolve] {updated} predictions resolved")
        except Exception as e:
            print(f"[auto-resolve] error: {e}")
        # Sleep 30 min (or until stop)
        _auto_resolve_stop.wait(1800)


def _start_auto_resolve():
    global _auto_resolve_thread
    if _auto_resolve_thread is None or not _auto_resolve_thread.is_alive():
        _auto_resolve_thread = _threading.Thread(
            target=_auto_resolve_loop,
            daemon=True,
            name="auto_resolve"
        )
        _auto_resolve_thread.start()
        print("[auto-resolve] daemon started (30 min interval)")

@app.route('/trigger_resolve', methods=['GET'])
def trigger_resolve():
    """Manually trigger resolution — useful for testing."""
    updated = check_results_internal()
    return jsonify({"updated": updated, "total": len(load_prediction_history())})

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "ok", "sportsipy_available": SPORTSIPY_AVAILABLE})

@app.route('/team_stats', methods=['GET'])
def get_team_stats():
    team = request.args.get('team')
    if team not in TEAM_MAP:
        return jsonify({"error": "Team not found"}), 404
    
    # Check manual overrides first
    if team in manual_overrides and manual_overrides[team]:
        override = manual_overrides[team]
        return jsonify({
            "team": team,
            "record": override.get("record", "0-0"),
            "points_for": int(override.get("points_for", 0)),
            "points_against": int(override.get("points_against", 0)),
            "streak": override.get("streak", "N/A")
        })
    
    team_abbr = TEAM_MAP[team]
    url = f"{ESPN_SITE_V2}/teams/{team_abbr}"
    data = get_cached_or_fetch(url, f"team_{team_abbr}")
    if not data:
        return jsonify({"error": "Could not fetch team data"}), 500
    stats = {"team": team, "record": "0-0", "points_for": 0, "points_against": 0, "streak": "N/A"}
    if 'team' in data and 'record' in data['team']:
        for item in data['team']['record'].get('items', []):
            if item.get('type') == 'total':
                stats['record'] = item.get('summary', '0-0')
                for stat in item.get('stats', []):
                    name = stat.get('name', '')
                    if name == 'pointsFor': stats['points_for'] = int(stat.get('value', 0))
                    elif name == 'pointsAgainst': stats['points_against'] = int(stat.get('value', 0))
                    elif name == 'streak':
                        streak_val = int(stat.get('value', 0))
                        stats['streak'] = f"+{streak_val}" if streak_val > 0 else f"{streak_val}" if streak_val < 0 else "Even"
                break
    return jsonify(stats)

@app.route('/roster', methods=['GET'])
def get_roster():
    team_name = request.args.get('team', '')
    if not team_name or team_name not in TEAM_MAP:
        return jsonify({"error": "Team required"}), 400
    url = f"{ESPN_SITE_V2}/teams/{TEAM_MAP[team_name]}/roster"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": "Failed to get roster"}), 500
        data = response.json()
        players = []
        if 'athletes' in data:
            for group in data['athletes']:
                for player in group.get('items', []):
                    name = player.get('fullName', '')
                    if name:
                        players.append({
                            "id": player.get('id', ''),
                            "name": name,
                            "position": player.get('position', {}).get('abbreviation', ''),
                            "jersey": player.get('jersey', ''),
                            "injured": player.get('injured', False)
                        })
        return jsonify({"team": team_name, "players": players})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/player_stats', methods=['GET'])
def get_player_stats():
    name = request.args.get('name')
    team = request.args.get('team')
    if not name:
        return jsonify({"error": "Player name required"}), 400
    player_id = None
    player_info = {"name": name, "team": team, "position": "N/A", "jersey": "N/A", "injured": False, "stats": None}
    
    # Step 1: Try roster lookup for player info
    if team and team in TEAM_MAP:
        url = f"{ESPN_SITE_V2}/teams/{TEAM_MAP[team]}/roster"
        data = get_cached_or_fetch(url, f"roster_{team}")
        if data and 'athletes' in data:
            for group in data['athletes']:
                for player in group.get('items', []):
                    if name.lower() in player.get('fullName', '').lower():
                        player_id = player.get('id', '')
                        player_info = {
                            "id": player_id,
                            "name": player.get('fullName'),
                            "position": player.get('position', {}).get('abbreviation'),
                            "jersey": player.get('jersey'),
                            "team": team,
                            "injured": player.get('injured', False),
                            "stats": None
                        }
                        break
    
    # Step 2: Try Sportsipy for real season stats
    s_stats = get_player_stats_sportsipy(name, team)
    if s_stats:
        player_info["stats"] = s_stats
        return jsonify(player_info)
    
    # Step 3: Search boxscores (2026 pre/reg first, then 2025 reg/pre)
    for season, seasontype in [(2026, 1), (2026, 2), (2025, 2), (2025, 1)]:
        sched_url = f'{ESPN_SITE_V2}/teams/{TEAM_MAP.get(team, "")}/schedule?season={season}&seasontype={seasontype}'
        try:
            sched = requests.get(sched_url, timeout=10).json()
        except:
            continue
        # Sort by date descending - most recent game first
        events = sched.get('events', [])
        for event in reversed(events):
            event_id = event.get('id', '')
            if not event_id:
                continue
            comp = event.get('competitions', [{}])[0]
            status = comp.get('status', {}).get('type', {})
            if not status.get('completed'):
                continue
            try:
                summary = requests.get(f'{ESPN_SITE_V2}/summary?event={event_id}', timeout=10).json()
            except:
                continue
            if 'boxscore' not in summary:
                continue
            for team_data in summary['boxscore'].get('players', []):
                for stat_group in team_data.get('statistics', []):
                    for athlete in stat_group.get('athletes', []):
                        athlete_name = athlete.get('athlete', {}).get('displayName', '')
                        if name.lower() in athlete_name.lower():
                            stats = {}
                            raw_stats = athlete.get('stats', [])
                            if len(raw_stats) >= 2:
                                if stat_group['name'] == 'passing':
                                    try:
                                        stats['completions'] = raw_stats[0].split('/')[0]
                                        stats['passing_attempts'] = raw_stats[0].split('/')[1]
                                        stats['passing_yards'] = int(raw_stats[1])
                                        if len(raw_stats) >= 5:
                                            stats['passing_tds'] = int(raw_stats[3])
                                    except: pass
                                elif stat_group['name'] == 'rushing':
                                    try:
                                        stats['rushing_attempts'] = int(raw_stats[0]) if raw_stats[0].isdigit() else 0
                                        stats['rushing_yards'] = int(raw_stats[1])
                                        if len(raw_stats) >= 4:
                                            stats['rushing_tds'] = int(raw_stats[3])
                                    except: pass
                                elif stat_group['name'] == 'receiving':
                                    try:
                                        stats['receptions'] = int(raw_stats[0]) if raw_stats[0].isdigit() else 0
                                        stats['receiving_yards'] = int(raw_stats[1])
                                        if len(raw_stats) >= 4:
                                            stats['receiving_tds'] = int(raw_stats[3])
                                    except: pass
                            if stats:
                                player_info["stats"] = stats
                                player_info["stats_source"] = f"{season} season, week {event.get('week', {}).get('number', 'N/A')}"
                                if not player_id:
                                    player_info["id"] = str(athlete.get('athlete', {}).get('id', ''))
                                    player_info["name"] = athlete_name
                                return jsonify(player_info)
    
    return jsonify(player_info)

@app.route('/weather', methods=['GET'])
def get_weather():
    team = request.args.get('team')
    if not team:
        return jsonify({"error": "Team parameter required"}), 400
    weather = get_weather_from_api(team)
    if weather:
        return jsonify(weather), 200
    else:
        return jsonify({
            "city": "Unknown", "stadium": team, "temperature": 65,
            "conditions": "Clear", "wind_speed": 5, "precipitation": 0, "impact": "Minimal impact"
        }), 200

@app.route('/injuries', methods=['GET'])
def get_injuries():
    team = request.args.get('team')
    url = f"{ESPN_SITE_V2}/injuries"
    data = get_cached_or_fetch(url, "all_injuries")
    if not data:
        return jsonify({"error": "Could not fetch injuries"}), 500
    team_injuries = []
    for t in data.get('injuries', []):
        if team and team.lower() == t.get('displayName', '').lower():
            for inj in t.get('injuries', []):
                athlete = inj.get('athlete', {})
                injury_info = inj.get('injury', {})
                team_injuries.append({
                    "player": athlete.get('displayName') or athlete.get('fullName', 'Unknown'),
                    "position": athlete.get('position', {}).get('abbreviation', 'N/A'),
                    "injury": injury_info.get('type') or injury_info.get('detail') or 'Unknown',
                    "status": inj.get('status', 'Unknown'),
                    "date": inj.get('date', ''),
                    "detail": injury_info.get('detail', '')
                })
            break
    return jsonify({"team": team or "All Teams", "injuries": team_injuries, "count": len(team_injuries)})

@app.route('/news', methods=['GET'])
def get_news():
    entity = request.args.get('entity', '')
    url = f"{ESPN_SITE_V2}/news"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return jsonify({"team": entity or "All Teams", "news": []})
        data = response.json()
        articles = []
        team_keywords = TEAM_KEYWORDS.get(entity, []) if entity else []
        if 'articles' in data:
            for article in data['articles'][:30]:
                headline = article.get('headline', '')
                description = article.get('description', '')
                if entity and team_keywords:
                    categories = article.get('categories', [])
                    team_match = False
                    for cat in categories:
                        if cat.get('type') == 'team':
                            cat_team = cat.get('description', '')
                            if any(kw.lower() in cat_team.lower() for kw in team_keywords):
                                team_match = True
                                break
                    if not team_match:
                        text = (headline + " " + description).lower()
                        if any(kw.lower() in text for kw in team_keywords):
                            team_match = True
                    if not team_match:
                        continue
                pub = article.get('published', '')
                articles.append({
                    "headline": headline or 'No headline',
                    "date": pub.split('T')[0] if pub else '',
                    "description": description or '',
                    "source": "ESPN"
                })
        if entity and not articles and data.get('articles'):
            for article in data['articles'][:5]:
                pub = article.get('published', '')
                articles.append({
                    "headline": article.get('headline', 'No headline'),
                    "date": pub.split('T')[0] if pub else '',
                    "description": article.get('description', ''),
                    "source": "ESPN (General NFL)"
                })
        return jsonify({"team": entity or "All Teams", "news": articles})
    except Exception as e:
        print(f"News error: {e}")
        return jsonify({"team": entity or "All Teams", "news": [], "error": str(e)})

@app.route('/win_loss', methods=['GET'])
def get_win_loss():
    team = request.args.get('team')
    if team not in TEAM_MAP:
        return jsonify({"error": "Team not found"}), 404
    abbr = TEAM_MAP[team]
    url = f"{ESPN_SITE_V2}/teams/{abbr}"
    data = get_cached_or_fetch(url, f"team_{abbr}")
    if not data:
        return jsonify({"error": "Could not fetch team data"}), 500
    reg_record = "0-0"
    win_pct = 0.0
    streak = "N/A"
    home = "N/A"
    away = "N/A"
    if 'team' in data and 'record' in data['team']:
        for item in data['team']['record'].get('items', []):
            if item.get('type') == 'total':
                reg_record = item.get('summary', '0-0')
                for stat in item.get('stats', []):
                    n = stat.get('name', '')
                    if n == 'streak':
                        v = int(stat.get('value', 0))
                        streak = f"+{v}" if v > 0 else f"{v}" if v < 0 else "Even"
                    elif n == 'homeRecord': home = stat.get('displayValue', 'N/A')
                    elif n == 'awayRecord': away = stat.get('displayValue', 'N/A')
                break
    if '-' in reg_record:
        w, l = map(int, reg_record.split('-'))
        if w + l > 0:
            win_pct = w / (w + l)
    return jsonify({
        "regular_season_record": reg_record, "win_percentage": win_pct,
        "current_streak": streak, "last_5_games": [],
        "home_record": home, "away_record": away
    })

@app.route('/predict', methods=['GET'])
def predict_winner():
    team1 = request.args.get('team1')
    team2 = request.args.get('team2')
    if not team1 or not team2:
        return jsonify({"error": "Invalid teams"}), 400
    
    market_spread = None
    market_total = None
    market_home_prob = None
    edge = None
    
    try:
        # Load ML models
        rf = joblib.load('ml_models/random_forest_v6.pkl')
        gb = joblib.load('ml_models/gradient_boosting_v6.pkl')
        strengths = joblib.load('ml_models/team_strengths.pkl')
    except:
        rf = gb = None
        strengths = {}
    
    t1_abbr = TEAM_MAP.get(team1, '').upper()
    t2_abbr = TEAM_MAP.get(team2, '').upper()
    
    # Fetch live stats from ESPN
    def count_schedule(abbr, season, seasontype):
        sched_url = f"{ESPN_SITE_V2}/teams/{abbr}/schedule?season={season}&seasontype={seasontype}"
        sched = get_cached_or_fetch(sched_url, f"sched_{season}_{seasontype}_{abbr}")
        w = l = pf = pa = 0
        if sched and 'events' in sched:
            for ev in sched['events']:
                comp = ev.get('competitions', [{}])[0]
                status = comp.get('status', {}).get('type', {})
                if not status.get('completed'):
                    continue
                for c in comp.get('competitors', []):
                    if c.get('team', {}).get('abbreviation', '').upper() == abbr.upper():
                        sv = c.get('score', 0)
                        if isinstance(sv, dict): sv = sv.get('value', 0)
                        sv = int(sv) if sv else 0
                        opp_score = 0
                        for o in comp.get('competitors', []):
                            if o is not c:
                                ov = o.get('score', 0)
                                if isinstance(ov, dict): ov = ov.get('value', 0)
                                opp_score = int(ov) if ov else 0
                                break
                        pf += sv
                        pa += opp_score
                        if c.get('winner', False):
                            w += 1
                        else:
                            l += 1
        return w, l, pf, pa

    def get_team_data(team):
        abbr = TEAM_MAP.get(team, '')
        url = f"{ESPN_SITE_V2}/teams/{abbr}"
        data = get_cached_or_fetch(url, f"team_{abbr}")
        rec = "0-0"
        pf = pa = 0
        turnovers_lost = turnovers_gained = 0
        epa = 0.0
        if data and 'team' in data:
            for item in data['team']['record'].get('items', []):
                if item.get('type') == 'total':
                    rec = item.get('summary', '0-0')
                    for stat in item.get('stats', []):
                        n = stat.get('name', '')
                        v = stat.get('value', 0)
                        if n == 'pointsFor': pf = int(v)
                        elif n == 'pointsAgainst': pa = int(v)
                        elif n in ['turnoversLost', 'giveaways']: turnovers_lost = int(v)
                        elif n in ['turnoversGained', 'takeaways']: turnovers_gained = int(v)
                        elif n in ['totalExpectedPointsAdded', 'epa']: epa = float(v)
                break
        w = l = 0
        if '-' in rec:
            try:
                w, l = map(int, rec.split('-'))
            except:
                pass
        # If no current data, try 2026/2025 schedule aggregation
        if w + l == 0:
            w, l, pf, pa = count_schedule(abbr, 2026, 1)
            if w + l == 0:
                w2, l2, pf2, pa2 = count_schedule(abbr, 2026, 2)
                if w2 + l2 > 0:
                    w, l, pf, pa = w2, l2, pf2, pa2
            if w + l == 0:
                w, l, pf, pa = count_schedule(abbr, 2025, 2)
            rec = f"{w}-{l}"
        # If we couldn't get turnovers, compute from schedule
        if turnovers_lost == 0 and turnovers_gained == 0:
            try:
                sched = get_cached_or_fetch(f"{ESPN_SITE_V2}/teams/{abbr}/schedule?season=2026&seasontype=2", f"to_{abbr}") or get_cached_or_fetch(f"{ESPN_SITE_V2}/teams/{abbr}/schedule?season=2025&seasontype=2", f"to_{abbr}")
                if sched and 'events' in sched:
                    for ev in sched['events']:
                        comp = ev.get('competitions', [{}])[0]
                        if not comp.get('status', {}).get('type', {}).get('completed'): continue
                        for c_ in comp.get('competitors', []):
                            if c_.get('team', {}).get('abbreviation', '').upper() == abbr.upper():
                                to_l = int(c_.get('turnovers', 0) or 0)
                                turnovers_lost += to_l
                                break
            except:
                pass
        return {
            'record': rec, 'wins': w, 'losses': l, 'pf': pf, 'pa': pa,
            'turnover_diff': turnovers_gained - turnovers_lost,
            'turnovers_lost': turnovers_lost, 'turnovers_gained': turnovers_gained,
            'epa': epa
        }

    d1 = get_team_data(team1)
    d2 = get_team_data(team2)
    
    # Get weather
    w1 = get_weather_from_api(team1)
    w2 = get_weather_from_api(team2)
    
    # Get injuries
    inj1 = get_cached_or_fetch(f"{ESPN_SITE_V2}/injuries", "injuries")
    inj_count1 = inj_count2 = 0
    if inj1:
        for t in inj1.get('injuries', []):
            team_name = t.get('displayName', '').lower().strip()
            if team_name == team1.lower().strip():
                inj_count1 = len(t.get('injuries', []))
            elif team_name == team2.lower().strip():
                inj_count2 = len(t.get('injuries', []))
    # ESPN returns fake "25" for every team during offseason - detect and zero it
    # Only trust injury data if the two teams actually differ
    if inj_count1 == inj_count2 and inj_count1 >= 20:
        inj_count1 = inj_count2 = 0
    # Sanity cap
    inj_count1 = min(inj_count1, 15)
    inj_count2 = min(inj_count2, 15)
    
    # ---- WEIGHTED SCORING ----
    score1 = score2 = 0.0
    factors = []
    
    # 1. Win % (35%)
    total1 = d1['wins'] + d1['losses']
    total2 = d2['wins'] + d2['losses']
    wp1 = (d1['wins'] / total1) if total1 > 0 else 0.5
    wp2 = (d2['wins'] / total2) if total2 > 0 else 0.5
    # Weight by games played - teams with few games contribute less
    wp1_weight = min(total1 / 10.0, 1.0)
    wp2_weight = min(total2 / 10.0, 1.0)
    wp1 = 0.5 + (wp1 - 0.5) * wp1_weight
    wp2 = 0.5 + (wp2 - 0.5) * wp2_weight
    score1 += wp1 * 35
    score2 += wp2 * 35
    factors.append(f"Win%: {team1} {wp1:.0%} vs {team2} {wp2:.0%}")
    
    # 2. Point differential (15%) + EPA (5%)
    pd1 = d1['pf'] - d1['pa']
    pd2 = d2['pf'] - d2['pa']
    pd_norm = max(abs(pd1) + abs(pd2), 1)
    score1 += ((pd1 - pd2) / pd_norm + 1) * 7.5
    score2 += ((pd2 - pd1) / pd_norm + 1) * 7.5
    # EPA differential (if available)
    epa1 = d1.get('epa', 0) or 0
    epa2 = d2.get('epa', 0) or 0
    if epa1 != 0 or epa2 != 0:
        epa_norm = max(abs(epa1) + abs(epa2), 1)
        score1 += ((epa1 - epa2) / epa_norm + 1) * 2.5
        score2 += ((epa2 - epa1) / epa_norm + 1) * 2.5
        factors.append(f"EPA: {team1} {epa1:+.1f} vs {team2} {epa2:+.1f}")
    factors.append(f"Point diff: {team1} {pd1:+d} vs {team2} {pd2:+d}")
    
    # 2b. Turnover differential (5%)
    to1 = d1.get('turnover_diff', 0)
    to2 = d2.get('turnover_diff', 0)
    to_norm = max(abs(to1) + abs(to2), 1)
    score1 += ((to1 - to2) / to_norm + 1) * 2.5
    score2 += ((to2 - to1) / to_norm + 1) * 2.5
    factors.append(f"Turnover diff: {team1} {to1:+d} vs {team2} {to2:+d}")
    
    # 3. Home field (12%) + rest days (3%)
    score1 += 12
    # Rest day differential - beneficial if opponent on short week
    try:
        from datetime import datetime
        sched1 = get_cached_or_fetch(f"{ESPN_SITE_V2}/teams/{TEAM_MAP.get(team1, '')}/schedule", f"sched_rest1_{TEAM_MAP.get(team1, '')}")
        sched2 = get_cached_or_fetch(f"{ESPN_SITE_V2}/teams/{TEAM_MAP.get(team2, '')}/schedule", f"sched_rest2_{TEAM_MAP.get(team2, '')}")
        # Just add a small constant - full rest day calc requires last game date
        # Fallback: assume equal rest, no adjustment
        score1 += 1.5
        score2 += 1.5
    except:
        score1 += 1.5
        score2 += 1.5
    factors.append(f"Home field: {team1}")
    
    # 4. Injuries (10%) - weighted by player value
    inj_val1 = locals().get('inj_val1', 0.0)
    inj_val2 = locals().get('inj_val2', 0.0)
    inj_impact1 = max(0, 10 - inj_val1 * 0.8)
    inj_impact2 = max(0, 10 - inj_val2 * 0.8)
    score1 += inj_impact1
    score2 += inj_impact2
    factors.append(f"Injuries: {team1} {inj_val1:.1f} pts lost vs {team2} {inj_val2:.1f} pts lost")
    
    # 5. Weather (5%)
    weather_impact1 = weather_impact2 = 5
    if w1 and w1.get('wind_speed', 0) > 15:
        weather_impact1 = 2
        factors.append(f"Weather: High wind at {team1} stadium")
    if w2 and w2.get('wind_speed', 0) > 15:
        weather_impact2 = 2
    score1 += weather_impact1
    score2 += weather_impact2
    
    # 6. Recent form - last 5 (15%)
    def get_recent_form(abbr):
        # Try 2026 regular season last 5
        for season, stype in [(2026, 2), (2026, 1), (2025, 2)]:
            sched_url = f"{ESPN_SITE_V2}/teams/{abbr}/schedule?season={season}&seasontype={stype}"
            sched = get_cached_or_fetch(sched_url, f"recent_{season}_{stype}_{abbr}")
            if not sched or 'events' not in sched:
                continue
            completed = []
            for ev in sched['events']:
                comp = ev.get('competitions', [{}])[0]
                if comp.get('status', {}).get('type', {}).get('completed'):
                    for c in comp.get('competitors', []):
                        if c.get('team', {}).get('abbreviation', '').upper() == abbr.upper():
                            completed.append(1 if c.get('winner', False) else 0)
                            break
            if completed:
                last5 = completed[-5:]
                return sum(last5) / len(last5)
        return 0.5
    
    rf1 = get_recent_form(t1_abbr)
    rf2 = get_recent_form(t2_abbr)
    score1 += rf1 * 15
    score2 += rf2 * 15
    factors.append(f"Recent form: {team1} {rf1:.0%} vs {team2} {rf2:.0%}")
    
    # 7. ML model boost (5%)
    if rf and gb:
        hs = strengths.get(t1_abbr, 0)
        as_ = strengths.get(t2_abbr, 0)
        diff = hs - as_
        feats = pd.DataFrame([[hs, as_, diff]], columns=['home_strength','away_strength','strength_diff'])
        ml_prob = (rf.predict_proba(feats)[0][1] + gb.predict_proba(feats)[0][1]) / 2
        score1 += ml_prob * 5
        score2 += (1 - ml_prob) * 5
        factors.append(f"ML model: {ml_prob:.0%} for {team1}")
    
    # Final probabilities
    total_score = score1 + score2
    prob1 = (score1 / total_score * 100) if total_score > 0 else 50.0
    prob2 = 100 - prob1
    
    # Confidence
    conf = abs(prob1 - prob2)
    level = "HIGH" if conf > 20 else "MEDIUM" if conf > 10 else "LOW"
    
    # Fetch market data here so we can use it for score prediction
    if market_spread is None:
        try:
            odds_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
            odds_params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american"}
            import time as _tm
            if market_cache.get("data") is None or _tm.time() - market_cache.get("time", 0) > MARKET_CACHE_TTL:
                _r = requests.get(odds_url, params=odds_params, timeout=10)
                if _r.status_code == 200:
                    market_cache["data"] = _r.json()
                    market_cache["time"] = _tm.time()
            if market_cache.get("data"):
                for _og in market_cache["data"]:
                    _oh = _og.get('home_team', '')
                    _oa = _og.get('away_team', '')
                    if (_oh == team1 and _oa == team2) or (_oh == team2 and _oa == team1):
                        _spreads_h = []
                        _totals_o = []
                        _h_mls = []
                        _a_mls = []
                        for _bk in _og.get('bookmakers', []):
                            for _mk in _bk.get('markets', []):
                                if _mk['key'] == 'spreads':
                                    for _o in _mk['outcomes']:
                                        if _o['name'] == team1: _spreads_h.append(_o['point'])
                                elif _mk['key'] == 'totals':
                                    for _o in _mk['outcomes']:
                                        if _o['name'] == 'Over': _totals_o.append(_o['point'])
                                elif _mk['key'] == 'h2h':
                                    for _o in _mk['outcomes']:
                                        if _o['name'] == team1: _h_mls.append(_o['price'])
                                        else: _a_mls.append(_o['price'])
                        if _spreads_h: market_spread = round(sum(_spreads_h) / len(_spreads_h), 1)
                        if _totals_o: market_total = round(sum(_totals_o) / len(_totals_o), 1)
                        if _h_mls and _a_mls:
                            _avg_h = sum(_h_mls) / len(_h_mls)
                            _avg_a = sum(_a_mls) / len(_a_mls)
                            def _m2p(ml): return (100/(ml+100)) if ml > 0 else (abs(ml)/(abs(ml)+100))
                            _hp = _m2p(_avg_h); _ap = _m2p(_avg_a)
                            market_home_prob = round(_hp / (_hp + _ap) * 100, 1)
                        break
        except:
            pass
    
    # Score prediction - fallback model first
    avg_offense1 = (d1['pf'] / total1) if total1 > 0 else 24
    avg_offense2 = (d2['pf'] / total2) if total2 > 0 else 21
    avg_defense1 = (d1['pa'] / total1) if total1 > 0 else 21
    avg_defense2 = (d2['pa'] / total2) if total2 > 0 else 24
    pred1 = (avg_offense1 + avg_defense2) / 2
    pred2 = (avg_offense2 + avg_defense1) / 2
    if w1 and w1.get('wind_speed', 0) > 15:
        pred1 -= 2
        pred2 -= 2
    if w1 and w1.get('precipitation', 0) > 50:
        pred1 -= 3
        pred2 -= 3
    pred1 += 2
    pred1 -= min(inj_val1, 5) * 1.0
    pred2 -= min(inj_val2, 5) * 1.0
    final1 = max(14, int(round(pred1)))
    final2 = max(14, int(round(pred2)))
    total_p = final1 + final2
    if total_p > 56:
        final1 = int(final1 * 56 / total_p)
        final2 = int(final2 * 56 / total_p)
    elif total_p < 38:
        final1 = int(final1 * 38 / total_p)
        final2 = int(final2 * 38 / total_p)
    
    # Override with market-derived scores if available
    if market_spread is not None and market_total is not None:
        model_spread = final1 - final2
        blended_spread = market_spread * 0.65 + model_spread * 0.35
        # market_spread negative = team1 favored, so team1 score should be higher
        # final1 = total/2 - blended_spread/2 gives team1 the higher score when blended_spread < 0
        p1 = market_total / 2 - blended_spread / 2
        p2 = market_total / 2 + blended_spread / 2
        final1 = max(10, int(round(p1)))
        final2 = max(10, int(round(p2)))
    
    # Never predict a tie - NFL ties are extremely rare
    if final1 == final2:
        if prob1 > prob2:
            final1 += 1
        elif prob2 > prob1:
            final2 += 1
        else:
            # Absolute tie in probability - give home team the edge
            final1 += 1
    
    spread = final1 - final2
    total = final1 + final2
    if spread > 0:
        spread_str = f"{team1} -{spread}"
    elif spread < 0:
        spread_str = f"{team2} -{abs(spread)}"
    else:
        spread_str = "Pick'em"

    # ───── Enriched factor detail (paired with factors list) ─────
    factors_detail = []
    for f in factors:
        fl = f.lower()
        if "win%" in fl:
            factors_detail.append("Season-to-date win percentage comparison.")
        elif "epa" in fl:
            factors_detail.append("Expected Points Added — how efficiently each offense moves the ball.")
        elif "point diff" in fl:
            factors_detail.append("Cumulative point differential this season.")
        elif "turnover" in fl:
            factors_detail.append("Net turnovers — a major driver of game outcomes.")
        elif "home field" in fl:
            factors_detail.append("Historical home-field advantage for this venue.")
        elif "injur" in fl:
            factors_detail.append("Estimated points lost to key injuries (QB weighted heavier).")
        elif "weather" in fl:
            factors_detail.append("Weather conditions at kickoff — high wind reduces scoring.")
        elif "recent form" in fl:
            factors_detail.append("Last-5-game rolling performance.")
        elif "ml model" in fl:
            factors_detail.append("Raw machine learning model probability before market blend.")
        else:
            factors_detail.append("")

    return jsonify({
        "team1": team1,
        "team2": team2,
        "team1_win_probability": round(prob1, 1),
        "team2_win_probability": round(prob2, 1),
        "predicted_winner": team1 if prob1 > prob2 else team2,
        "predicted_score": f"{final1}-{final2}",
        "predicted_spread": spread_str,
        "predicted_total": total,
        "confidence": round(conf, 1),
        "confidence_level": level,
        "ml_home_probability": round(prob1, 1),
        "market_home_prob": market_home_prob if 'market_home_prob' in dir() else None,
        "blended_home_probability": round(prob1, 1),
        "edge": edge if 'edge' in dir() else None,
        "market_spread": market_spread if 'market_spread' in dir() else None,
        "market_total": market_total if 'market_total' in dir() else None,
        "key_factors": factors,
        "key_factors_detail": factors_detail,
        "raw_confidence": raw_conf_pct,
        "calibrated": True,
        "is_no_pick": is_no_pick,
        "game_slot": classify_game_slot(None)
    })

@app.route('/preseason_stats', methods=['GET'])
def get_preseason_stats():
    team = request.args.get('team', '')
    name = request.args.get('name', '')
    if not team or not name:
        return jsonify({'error': 'team and name required'}), 400
    try:
        for season in [2025, 2026]:
            for seasontype in [1, 2]:
                sched_url = f'{ESPN_SITE_V2}/teams/{TEAM_MAP.get(team, "")}/schedule?season={season}&seasontype={seasontype}'
                try:
                    sched = requests.get(sched_url, timeout=10).json()
                except:
                    continue
                for event in sched.get('events', []):
                    event_id = event.get('id', '')
                    if not event_id:
                        continue
                    try:
                        summary = requests.get(f'{ESPN_SITE_V2}/summary?event={event_id}', timeout=10).json()
                    except:
                        continue
                    if 'boxscore' not in summary:
                        continue
                    for team_data in summary['boxscore'].get('players', []):
                        for stat_group in team_data.get('statistics', []):
                            for athlete in stat_group.get('athletes', []):
                                athlete_name = athlete.get('athlete', {}).get('displayName', '')
                                if name.lower() in athlete_name.lower():
                                    stats = {}
                                    raw_stats = athlete.get('stats', [])
                                    if len(raw_stats) >= 2:
                                        if stat_group['name'] == 'passing':
                                            stats['completions'] = raw_stats[0].split('/')[0]
                                            stats['passing_attempts'] = raw_stats[0].split('/')[1]
                                            stats['passing_yards'] = int(raw_stats[1])
                                            if len(raw_stats) >= 5:
                                                stats['passing_tds'] = int(raw_stats[3])
                                        elif stat_group['name'] == 'rushing':
                                            stats['rushing_attempts'] = int(raw_stats[0]) if raw_stats[0].isdigit() else 0
                                            stats['rushing_yards'] = int(raw_stats[1])
                                            if len(raw_stats) >= 4:
                                                stats['rushing_tds'] = int(raw_stats[3])
                                        elif stat_group['name'] == 'receiving':
                                            stats['receptions'] = int(raw_stats[0]) if raw_stats[0].isdigit() else 0
                                            stats['receiving_yards'] = int(raw_stats[1])
                                            if len(raw_stats) >= 4:
                                                stats['receiving_tds'] = int(raw_stats[3])
                                    return jsonify({'stats': stats if stats else None})
        return jsonify({'stats': None})
    except Exception as e:
        return jsonify({'stats': None, 'error': str(e)})


@app.route('/live_scores', methods=['GET'])
def get_live_scores():
    url = f"{ESPN_SITE_V2}/scoreboard?dates=2026"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return jsonify({"scores": []})
        data = response.json()
        games = []
        for event in data.get('events', []):
            status = event.get('status', {}).get('type', {})
            state = status.get('description', 'Scheduled')
            detail = status.get('shortDetail', '')
            competitors = event.get('competitions', [{}])[0].get('competitors', [])
            if len(competitors) >= 2:
                away = competitors[0]
                home = competitors[1]
                games.append({
                    "away": away.get('team', {}).get('abbreviation', 'N/A'),
                    "home": home.get('team', {}).get('abbreviation', 'N/A'),
                    "away_score": int(away.get('score', 0)),
                    "home_score": int(home.get('score', 0)),
                    "status": state,
                    "detail": detail
                })
        live = [g for g in games if g['status'] in ['In Progress', 'Halftime']]
        return jsonify({"scores": live if live else games[:5]})
    except:
        return jsonify({"scores": []})



@app.route('/accuracy_by_week', methods=['GET'])
def accuracy_by_week():
    """Return prediction accuracy grouped by ISO week."""
    history = load_prediction_history()
    by_week = {}
    for entry in history:
        if entry.get("correct") is None:
            continue
        date_str = entry.get("date", "")
        # date is "YYYY-MM-DD HH:MM"
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(date_str[:10], "%Y-%m-%d")
            week_key = d.strftime("%Y-W%V")
        except Exception:
            week_key = "unknown"
        bucket = by_week.setdefault(week_key, {"total": 0, "correct": 0})
        bucket["total"] += 1
        if entry.get("correct") is True:
            bucket["correct"] += 1

    weeks = []
    for wk in sorted(by_week.keys()):
        b = by_week[wk]
        weeks.append({
            "week": wk,
            "total": b["total"],
            "correct": b["correct"],
            "accuracy": round(100.0 * b["correct"] / b["total"], 1) if b["total"] else 0.0
        })

    return jsonify({"weeks": weeks})

@app.route('/prediction_accuracy', methods=['GET'])
def get_prediction_accuracy():
    history = load_prediction_history()
    total = len(history)
    resolved = [h for h in history if h.get('correct') is not None]
    correct = sum(1 for h in resolved if h.get('correct'))
    accuracy = (correct / len(resolved) * 100) if resolved else 0
    edge_picks = [h for h in resolved if h.get('edge') and abs(h.get('edge', 0)) >= 5]
    edge_wins = sum(1 for h in edge_picks if h.get('correct'))
    edge_accuracy = (edge_wins / len(edge_picks) * 100) if edge_picks else 0
    recent = sorted(history, key=lambda x: x.get('timestamp', 0), reverse=True)[:10]
    return jsonify({
        "total_predictions": total,
        "resolved": len(resolved),
        "correct": correct,
        "accuracy": round(accuracy, 1),
        "edge_picks": len(edge_picks),
        "edge_accuracy": round(edge_accuracy, 1),
        "recent": recent
    })

@app.route('/record_prediction', methods=['POST'])
def record_prediction():
    data = request.get_json()
    history = load_prediction_history()
    history.append({
        "team1": data.get('team1'),
        "team2": data.get('team2'),
        "predicted_winner": data.get('predicted_winner'),
        "confidence": data.get('confidence'),
        "actual_winner": data.get('actual_winner'),
        "correct": data.get('predicted_winner') == data.get('actual_winner'),
        "timestamp": time.time()
    })
    return jsonify({"status": "recorded", "total": len(history)})


@app.route('/live_prediction', methods=['GET'])
def live_prediction():
    """Prediction for a game currently in progress"""
    url = f"{ESPN_SITE_V2}/scoreboard?dates=2026"
    try:
        data = requests.get(url, timeout=10).json()
        results = []
        for event in data.get('events', []):
            status = event.get('status', {}).get('type', {})
            if status.get('description') not in ['In Progress', 'Halftime']:
                continue
            comp = event.get('competitions', [{}])[0]
            comps = comp.get('competitors', [])
            if len(comps) < 2:
                continue
            home = next((x for x in comps if x.get('homeAway') == 'home'), comps[0])
            away = next((x for x in comps if x.get('homeAway') == 'away'), comps[1])
            hs = int(home.get('score', 0) or 0)
            as_ = int(away.get('score', 0) or 0)
            clock = status.get('shortDetail', '')
            period = status.get('period', 0)
            # Live win prob: start at 50, shift by score diff, amplify as game nears end
            progress = min(period / 4.0, 1.0)
            diff = hs - as_
            prob_home = 50 + (diff * 8 * (0.3 + progress * 0.7))
            prob_home = max(1, min(99, prob_home))
            results.append({
                "home": home.get('team', {}).get('abbreviation', ''),
                "away": away.get('team', {}).get('abbreviation', ''),
                "home_score": hs,
                "away_score": as_,
                "clock": clock,
                "home_win_probability": round(prob_home, 1),
                "away_win_probability": round(100 - prob_home, 1)
            })
        return jsonify({"live": results})
    except Exception as e:
        return jsonify({"live": [], "error": str(e)})

@app.route('/odds', methods=['GET'])
def get_odds():
    """Fetch real odds from The Odds API"""
    try:
        url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american",
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return jsonify({"odds": [], "error": f"api returned {r.status_code}"})
        results = []
        for game in r.json():
            home = game.get("home_team", "")
            away = game.get("away_team", "")
            # Aggregate across bookmakers
            spreads_h, spreads_a, totals, h_mls, a_mls = [], [], [], [], []
            for bk in game.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    for o in mk.get("outcomes", []):
                        if mk["key"] == "spreads":
                            if o["name"] == home: spreads_h.append(o.get("point"))
                            else: spreads_a.append(o.get("point"))
                        elif mk["key"] == "totals":
                            totals.append(o.get("point"))
                        elif mk["key"] == "h2h":
                            if o["name"] == home: h_mls.append(o.get("price"))
                            else: a_mls.append(o.get("price"))
            def avg(lst):
                nums = [x for x in lst if x is not None]
                return round(sum(nums) / len(nums), 1) if nums else None
            results.append({
                "game": f"{away} @ {home}",
                "provider": "TheOddsAPI",
                "spread": f"{home} {avg(spreads_h)}" if avg(spreads_h) is not None else "N/A",
                "over_under": avg(totals),
                "home_ml": avg(h_mls),
                "away_ml": avg(a_mls),
            })
        return jsonify({"odds": results})
    except Exception as e:
        return jsonify({"odds": [], "error": str(e)})

@app.route('/player_props', methods=['GET'])
def player_props():
    """Predict player stat lines for a given player"""
    name = request.args.get('name')
    team = request.args.get('team')
    if not name or not team:
        return jsonify({"error": "name and team required"}), 400
    # Get player's recent stats
    props = {"player": name, "team": team, "props": []}
    for season, stype in [(2026, 1), (2026, 2), (2025, 2)]:
        sched_url = f'{ESPN_SITE_V2}/teams/{TEAM_MAP.get(team, "")}/schedule?season={season}&seasontype={stype}'
        try:
            sched = requests.get(sched_url, timeout=10).json()
        except:
            continue
        games_found = []
        for event in reversed(sched.get('events', [])):
            eid = event.get('id', '')
            if not eid:
                continue
            try:
                summary = requests.get(f'{ESPN_SITE_V2}/summary?event={eid}', timeout=10).json()
            except:
                continue
            if 'boxscore' not in summary:
                continue
            for team_data in summary['boxscore'].get('players', []):
                for stat_group in team_data.get('statistics', []):
                    for athlete in stat_group.get('athletes', []):
                        an = athlete.get('athlete', {}).get('displayName', '')
                        if name.lower() in an.lower():
                            raw = athlete.get('stats', [])
                            if not raw:
                                continue
                            g = {"group": stat_group['name'], "raw": raw}
                            games_found.append(g)
                            break
        if games_found:
            # Average last 3 games
            passing_yards = []
            rushing_yards = []
            receiving_yards = []
            for g in games_found[:3]:
                try:
                    if g['group'] == 'passing' and len(g['raw']) >= 2:
                        passing_yards.append(int(g['raw'][1]))
                    elif g['group'] == 'rushing' and len(g['raw']) >= 2:
                        rushing_yards.append(int(g['raw'][1]))
                    elif g['group'] == 'receiving' and len(g['raw']) >= 2:
                        receiving_yards.append(int(g['raw'][1]))
                except:
                    pass
            if passing_yards:
                avg = sum(passing_yards) / len(passing_yards)
                props["props"].append({"stat": "Passing Yards", "line": round(avg), "recommendation": "OVER" if avg > 250 else "UNDER"})
            if rushing_yards:
                avg = sum(rushing_yards) / len(rushing_yards)
                props["props"].append({"stat": "Rushing Yards", "line": round(avg), "recommendation": "OVER" if avg > 60 else "UNDER"})
            if receiving_yards:
                avg = sum(receiving_yards) / len(receiving_yards)
                props["props"].append({"stat": "Receiving Yards", "line": round(avg), "recommendation": "OVER" if avg > 50 else "UNDER"})
        if props["props"]:
            return jsonify(props)
    return jsonify(props)


@app.route('/upcoming_games', methods=['GET'])
def upcoming_games():
    url = f"{ESPN_SITE_V2}/scoreboard"
    try:
        data = requests.get(url, timeout=10).json()
        current_week = data.get('week', {}).get('number', 1)
        games = []
        for event in data.get('events', []):
            status = event.get('status', {}).get('type', {})
            state = status.get('description', 'Scheduled')
            detail = status.get('shortDetail', '')
            completed = status.get('completed', False)
            week_num = event.get('week', {}).get('number', 0)
            if week_num != current_week:
                continue
            comp = event.get('competitions', [{}])[0]
            comps = comp.get('competitors', [])
            if len(comps) < 2:
                continue
            home = next((x for x in comps if x.get('homeAway') == 'home'), comps[0])
            away = next((x for x in comps if x.get('homeAway') == 'away'), comps[1])
            hs = int(home.get('score', 0) or 0)
            as_ = int(away.get('score', 0) or 0)
            game_date_raw = event.get('date', '')
            # Convert UTC to US Eastern
            try:
                from datetime import datetime, timedelta
                dt = datetime.strptime(game_date_raw.replace('Z', ''), '%Y-%m-%dT%H:%M')
                dt_eastern = dt - timedelta(hours=4)  # EDT offset
                game_date = dt_eastern.strftime('%Y-%m-%dT%H:%M:%S')
            except:
                game_date = game_date_raw
            home_abbr = home.get('team', {}).get('abbreviation', '')
            away_abbr = away.get('team', {}).get('abbreviation', '')
            home_name = home.get('team', {}).get('displayName', '')
            away_name = away.get('team', {}).get('displayName', '')
            home_winner = home.get('winner', False)
            away_winner = away.get('winner', False)
            
            # Time display
            if state in ['In Progress', 'Halftime']:
                status_text = detail
                state_type = "LIVE"
            elif completed:
                status_text = "FINAL"
                state_type = "FINAL"
            else:
                status_text = detail
                state_type = "SCHEDULED"
            
            games.append({
                "event_id": event.get('id', ''),
                "home": home_abbr,
                "away": away_abbr,
                "home_full": home_name,
                "away_full": away_name,
                "home_score": hs,
                "away_score": as_,
                "home_winner": home_winner,
                "away_winner": away_winner,
                "date": game_date,
                "status_text": status_text,
                "state_type": state_type,
                "is_live": state in ['In Progress', 'Halftime'],
                "completed": completed
            })
        
        # Sort by date ascending (Thursday first, Monday last)
        games.sort(key=lambda x: x.get('date', ''))
        return jsonify({"games": games, "week": current_week})
    except Exception as e:
        return jsonify({"games": [], "error": str(e)})

@app.route('/consensus_odds', methods=['GET'])
def consensus_odds():
    """Get consensus odds from multiple sportsbooks via The Odds API"""
    try:
        # NFL sport key + spreads, totals, h2h
        url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads,totals,h2h",
            "oddsFormat": "american"
        }
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return jsonify({"games": [], "error": f"API returned {r.status_code}"})
        data = r.json()
        games = []
        for game in data:
            home = game.get('home_team', '')
            away = game.get('away_team', '')
            spreads = []
            totals = []
            home_mls = []
            away_mls = []
            for book in game.get('bookmakers', []):
                for market in book.get('markets', []):
                    if market['key'] == 'spreads':
                        for o in market['outcomes']:
                            spreads.append({"team": o['name'], "point": o['point'], "price": o['price']})
                    elif market['key'] == 'totals':
                        for o in market['outcomes']:
                            totals.append({"name": o['name'], "point": o['point'], "price": o['price']})
                    elif market['key'] == 'h2h':
                        for o in market['outcomes']:
                            if o['name'] == home:
                                home_mls.append(o['price'])
                            else:
                                away_mls.append(o['price'])
            # Consensus spread
            home_spread = None
            for s in spreads:
                if s['team'] == home:
                    home_spread = s['point']
                    break
            # Consensus total
            totals_only = [t['point'] for t in totals if t['name'] == 'Over']
            avg_total = round(sum(totals_only) / len(totals_only), 1) if totals_only else None
            # Market-implied win prob from moneylines
            home_prob = None
            if home_mls and away_mls:
                avg_home_ml = sum(home_mls) / len(home_mls)
                avg_away_ml = sum(away_mls) / len(away_mls)
                def ml_to_prob(ml):
                    return (100 / (ml + 100)) if ml > 0 else (abs(ml) / (abs(ml) + 100))
                h = ml_to_prob(avg_home_ml)
                a = ml_to_prob(avg_away_ml)
                total_p = h + a
                home_prob = round(h / total_p * 100, 1) if total_p > 0 else None
            games.append({
                "home": home,
                "away": away,
                "commence_time": game.get('commence_time', ''),
                "consensus_spread": home_spread,
                "consensus_total": avg_total,
                "home_win_probability": home_prob,
                "away_win_probability": round(100 - home_prob, 1) if home_prob else None,
                "books_count": len(game.get('bookmakers', []))
            })
        return jsonify({"games": games, "count": len(games)})
    except Exception as e:
        return jsonify({"games": [], "error": str(e)})


@app.route('/log_prediction', methods=['POST'])
def log_prediction():
    """Log a prediction for later accuracy tracking"""
    data = request.get_json() or {}
    history = load_prediction_history()
    entry = {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "team1": data.get('team1'),
        "team2": data.get('team2'),
        "predicted_winner": data.get('predicted_winner'),
        "predicted_score": data.get('predicted_score'),
        "predicted_spread": data.get('predicted_spread'),
        "predicted_total": data.get('predicted_total'),
        "confidence": data.get('confidence'),
        "market_spread": data.get('market_spread'),
        "market_total": data.get('market_total'),
        "market_home_prob": data.get('market_home_prob'),
        "edge": data.get('edge'),
        "actual_winner": None,
        "actual_score": None,
        "correct": None
    }
    history.append(entry)
    return jsonify({"status": "logged", "total": len(history)})


@app.route('/check_results', methods=['GET'])
def check_results():
    """Check pending predictions against final scores"""
    history = load_prediction_history()
    url = f"{ESPN_SITE_V2}/scoreboard?dates=2026"
    try:
        data = requests.get(url, timeout=10).json()
    except:
        return jsonify({"updated": 0})
    final_games = {}
    for event in data.get('events', []):
        status = event.get('status', {}).get('type', {})
        if not status.get('completed'):
            continue
        comps = event.get('competitions', [{}])[0].get('competitors', [])
        if len(comps) < 2: continue
        home = next((x for x in comps if x.get('homeAway') == 'home'), comps[0])
        away = next((x for x in comps if x.get('homeAway') == 'away'), comps[1])
        key = f"{home.get('team', {}).get('displayName', '')}|{away.get('team', {}).get('displayName', '')}"
        hs = int(home.get('score', 0) or 0)
        as_ = int(away.get('score', 0) or 0)
        winner = home.get('team', {}).get('displayName') if hs > as_ else away.get('team', {}).get('displayName')
        final_games[key] = {"winner": winner, "score": f"{hs}-{as_}"}
    updated = 0
    for h in history:
        if h.get('correct') is not None: continue
        t1 = h.get('team1', '')
        t2 = h.get('team2', '')
        for key, result in final_games.items():
            if t1 in key and t2 in key:
                h['actual_winner'] = result['winner']
                h['actual_score'] = result['score']
                h['correct'] = (h.get('predicted_winner') == result['winner'])
                updated += 1
                break
    if updated > 0:
        save_prediction_history(history)
    return jsonify({"updated": updated, "total": len(history)})



@app.route('/predict_with_market', methods=['GET'])
def predict_with_market():
    """Predict + market comparison + auto-log"""
    team1 = request.args.get('team1')
    team2 = request.args.get('team2')
    if not team1 or not team2:
        return jsonify({"error": "Invalid teams"}), 400
    
    # Auto-resolve any pending predictions first
    try:
        check_results_internal()
    except:
        pass
    
    # Force refresh market data
    try:
        market_cache["time"] = 0
    except:
        pass
    
    # Call predict internally
    try:
        inner = predict_winner()
        if hasattr(inner, 'get_json'):
            pred = inner.get_json()
        else:
            import json as jlib
            pred = jlib.loads(inner[0].get_data())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    if 'error' in pred:
        return jsonify(pred)
    
    # Market comparison
    market_spread = None
    market_total = None
    market_home_prob = None
    edge = None
    try:
        odds_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
        odds_params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american"}
        # Cache market data for 5 min
        import time as time_mod
        if market_cache["data"] is None or time_mod.time() - market_cache["time"] > MARKET_CACHE_TTL:
            try:
                _r = requests.get(odds_url, params=odds_params, timeout=10)
                if _r.status_code == 200:
                    market_cache["data"] = _r.json()
                    market_cache["time"] = time_mod.time()
                    print(f"[ODDS] Fetched {len(market_cache['data'])} games")
                else:
                    print(f"[ODDS] API returned {_r.status_code}")
            except Exception as e:
                print(f"[ODDS] Failed: {e}")
        # Fallback: if The Odds API failed, use ESPN odds
        if not market_cache["data"]:
            try:
                espn_odds_url = f"{ESPN_SITE_V2}/scoreboard?dates=2026"
                espn_data = requests.get(espn_odds_url, timeout=10).json()
                for ev in espn_data.get('events', []):
                    comps = ev.get('competitions', [{}])[0].get('competitors', [])
                    if len(comps) < 2: continue
                    eh = next((x.get('team', {}).get('displayName', '') for x in comps if x.get('homeAway') == 'home'), '')
                    ea = next((x.get('team', {}).get('displayName', '') for x in comps if x.get('homeAway') == 'away'), '')
                    if (eh == team1 and ea == team2) or (eh == team2 and ea == team1):
                        odds_list = ev.get('competitions', [{}])[0].get('odds', [])
                        if odds_list:
                            o = odds_list[0]
                            spread_str = o.get('details', '')
                            over_under = o.get('overUnder')
                            if spread_str:
                                try:
                                    parts = spread_str.split()
                                    if len(parts) >= 2:
                                        market_spread = float(parts[-1])
                                        # Adjust sign: ESPN gives favorite -N
                                        if parts[0] != team1.split()[-1]:
                                            market_spread = -market_spread
                                except: pass
                            if over_under:
                                market_total = float(over_under)
                            # Home ML
                            hml = o.get('homeTeamOdds', {}).get('moneyLine')
                            aml = o.get('awayTeamOdds', {}).get('moneyLine')
                            if hml and aml:
                                def m2p(ml):
                                    ml = float(ml)
                                    return (100/(ml+100)) if ml > 0 else (abs(ml)/(abs(ml)+100))
                                hp = m2p(hml); ap = m2p(aml)
                                market_home_prob = round(hp / (hp + ap) * 100, 1)
                                edge = round(pred.get('team1_win_probability', 50) - market_home_prob, 1)
                        break
            except Exception as _e:
                print(f"[ESPN ODDS] fallback failed: {_e}")
        
        if market_cache["data"]:
            for og in market_cache["data"]:
                oh = og.get('home_team', '')
                oa = og.get('away_team', '')
                if (oh == team1 and oa == team2) or (oh == team2 and oa == team1):
                    spreads_h = []
                    totals_o = []
                    h_mls = []
                    a_mls = []
                    for bk in og.get('bookmakers', []):
                        for mk in bk.get('markets', []):
                            if mk['key'] == 'spreads':
                                for o in mk['outcomes']:
                                    if o['name'] == team1: spreads_h.append(o['point'])
                            elif mk['key'] == 'totals':
                                for o in mk['outcomes']:
                                    if o['name'] == 'Over': totals_o.append(o['point'])
                            elif mk['key'] == 'h2h':
                                for o in mk['outcomes']:
                                    if o['name'] == team1: h_mls.append(o['price'])
                                    else: a_mls.append(o['price'])
                    if spreads_h: market_spread = round(sum(spreads_h) / len(spreads_h), 1)
                    if totals_o: market_total = round(sum(totals_o) / len(totals_o), 1)
                    if h_mls and a_mls:
                        avg_h = sum(h_mls) / len(h_mls)
                        avg_a = sum(a_mls) / len(a_mls)
                        def m2p(ml): return (100/(ml+100)) if ml > 0 else (abs(ml)/(abs(ml)+100))
                        hp = m2p(avg_h); ap = m2p(avg_a)
                        market_home_prob = round(hp / (hp + ap) * 100, 1)
                    if market_home_prob is not None:
                        edge = round(pred.get('team1_win_probability', 50) - market_home_prob, 1)
                    break
    except:
        pass
    
    pred['market_spread'] = market_spread
    pred['market_total'] = market_total
    pred['market_home_prob'] = market_home_prob
    pred['edge'] = edge
    
    # Blend market into our prediction (market is generally more accurate)
    if market_home_prob is None:
        # No market anchor - cap confidence low, don't trust model alone
        pred['confidence'] = min(pred.get('confidence', 0), 15.0)
        pred['confidence_level'] = "LOW"
    
    if market_home_prob is not None:
        model_prob = pred.get('team1_win_probability', 50.0)
        # Weight market more when we disagree heavily
        edge_abs = abs(edge) if edge is not None else 0
        if edge_abs >= 15:
            market_weight = 0.85
        elif edge_abs >= 10:
            market_weight = 0.75
        elif edge_abs >= 5:
            market_weight = 0.65
        else:
            market_weight = 0.55
        model_weight = 1 - market_weight
        blended_prob = model_prob * model_weight + market_home_prob * market_weight
        pred['blended_home_prob'] = round(blended_prob, 1)
        pred['blended_away_prob'] = round(100 - blended_prob, 1)
        # Winner should always match predicted score
        ps = pred.get('predicted_score', '')
        try:
            parts = ps.split('-')
            s1 = int(parts[0]); s2 = int(parts[1])
            pred['predicted_winner'] = pred.get('team1') if s1 > s2 else pred.get('team2')
        except:
            pred['predicted_winner'] = team1 if blended_prob > 50 else team2
        pred['confidence'] = round(abs(blended_prob - 50) * 2, 1)
    
    # Auto-log
    try:
        history = load_prediction_history()
        history.append({
            "timestamp": time.time(),
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "team1": team1, "team2": team2,
            "predicted_winner": pred.get('predicted_winner'),
            "predicted_score": pred.get('predicted_score'),
            "predicted_spread": pred.get('predicted_spread'),
            "predicted_total": pred.get('predicted_total'),
            "confidence": pred.get('confidence'),
            "market_spread": (round(market_spread * 2) / 2 if market_spread is not None else None),
            "market_total": (int(round(market_total)) if market_total is not None else None),
            "market_home_prob": market_home_prob,
            "edge": edge,
            "actual_winner": None, "actual_score": None, "correct": None
        })
        save_prediction_history(history)
    except:
        pass
    
    return jsonify(pred)


@app.route('/prediction_log', methods=['GET'])
def prediction_log():
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]
    pending = [e for e in history if e.get("correct") is None]
    recent_resolved = sorted(resolved, key=lambda x: x.get("timestamp", 0), reverse=True)[:25]
    recent_pending = sorted(pending, key=lambda x: x.get("timestamp", 0), reverse=True)[:25]
    combined = recent_resolved + recent_pending
    combined.sort(key=lambda x: x.get("date", ""), reverse=True)
    return jsonify({
        "log": combined,
        "total": len(history),
        "resolved_count": len(resolved),
        "pending_count": len(pending),
        "correct_count": sum(1 for e in resolved if e.get("correct") is True),
        "wrong_count": sum(1 for e in resolved if e.get("correct") is False),
    })


def get_closing_line(team1, team2):
    """
    Fetch the current (closing) spread for a matchup from The Odds API.
    Used at resolution time to compute CLV.
    """
    try:
        url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads",
            "oddsFormat": "american",
        }
        r = requests.get(url, params=params, timeout=8)
        if r.status_code != 200:
            return None
        for game in r.json():
            if (game.get("home_team") == team1 and game.get("away_team") == team2) or \
               (game.get("home_team") == team2 and game.get("away_team") == team1):
                spreads = []
                for bk in game.get("bookmakers", []):
                    for mk in bk.get("markets", []):
                        if mk.get("key") == "spreads":
                            for o in mk.get("outcomes", []):
                                if o.get("name") == team1:
                                    spreads.append(o.get("point"))
                if spreads:
                    return round(sum(spreads) / len(spreads), 2)
    except Exception:
        pass
    return None


def check_results_internal():
    """Scan completed games and mark predictions"""
    history = load_prediction_history()
    try:
        data = requests.get(f"{ESPN_SITE_V2}/scoreboard?dates=2026", timeout=10).json()
    except:
        return
    final_games = []
    for event in data.get('events', []):
        status = event.get('status', {}).get('type', {})
        if not status.get('completed'):
            continue
        comps = event.get('competitions', [{}])[0].get('competitors', [])
        if len(comps) < 2: continue
        home = next((x for x in comps if x.get('homeAway') == 'home'), comps[0])
        away = next((x for x in comps if x.get('homeAway') == 'away'), comps[1])
        hs = int(home.get('score', 0) or 0)
        as_ = int(away.get('score', 0) or 0)
        winner = home.get('team', {}).get('displayName') if hs > as_ else away.get('team', {}).get('displayName')
        final_games.append({
            "home": home.get('team', {}).get('displayName', ''),
            "away": away.get('team', {}).get('displayName', ''),
            "winner": winner,
            "score": f"{as_}-{hs}",
            "home_score": hs,
            "away_score": as_
        })
    updated = 0
    import time as _t
    for h in history:
        if h.get('correct') is not None: continue
        for fg in final_games:
            if (h.get('team1') == fg['home'] and h.get('team2') == fg['away']) or \
               (h.get('team1') == fg['away'] and h.get('team2') == fg['home']):
                h['actual_winner'] = fg['winner']
                h['actual_score'] = fg['score']
                h['correct'] = (h.get('predicted_winner') == fg['winner'])
                h['resolved_at'] = _t.time()

                # ───── ENHANCED METRICS ─────

                # Was the market correct?
                if h.get('market_home_prob') is not None:
                    if h['market_home_prob'] > 50:
                        h['market_pick'] = h.get('team1')
                    else:
                        h['market_pick'] = h.get('team2')
                    h['market_correct'] = (h.get('market_pick') == fg['winner'])

                # Final margin + did we hit the spread?
                margin = fg['home_score'] - fg['away_score']
                h['final_margin'] = margin
                # Parse our predicted spread to check spread hit
                ps = h.get('predicted_spread', '') or ''
                if ' -' in ps or ' +' in ps:
                    try:
                        parts = ps.rsplit(' ', 1)
                        our_line = float(parts[1].replace('+', ''))
                        # Which team did we say would cover?
                        our_team = ps[:ps.rfind(' ')]
                        if our_team == h.get('team1'):
                            # We said home covers
                            h['spread_hit'] = (margin + our_line) > 0  # home needs margin > |our_line|
                        elif our_team == h.get('team2'):
                            # We said away covers
                            h['spread_hit'] = (margin + our_line) < 0
                    except Exception:
                        h['spread_hit'] = None

                # Compute CLV if we had an opening spread and can get a closing spread
                opening = h.get('opening_spread')
                if opening is not None:
                    try:
                        closing = get_closing_line(h.get('team1'), h.get('team2'))
                        if closing is not None:
                            h['closing_spread'] = closing
                            h['clv'] = round(abs(closing) - abs(opening), 2)
                    except Exception:
                        pass

                # Record which signal-type buckets were present at prediction time
                kf = h.get('key_factors') or []
                signals = []
                for f in kf:
                    if f.startswith('QB EPA'): signals.append('qb_epa')
                    elif f.startswith('Contrarian'): signals.append('contrarian')
                    elif f.startswith('Schedule'): signals.append('schedule')
                    elif f.startswith('Coaching'): signals.append('coaching')
                    elif f.startswith('ML model'): signals.append('ml_model')
                h['signals_present'] = signals

                updated += 1
                break
    if updated > 0:
        save_prediction_history(history)
    return updated



@app.route('/model_report', methods=['GET'])
def model_report():
    """Detailed accuracy report - model vs market"""
    history = load_prediction_history()
    resolved = [h for h in history if h.get('correct') is not None]
    
    model_correct = sum(1 for h in resolved if h.get('correct'))
    model_acc = round(model_correct / len(resolved) * 100, 1) if resolved else 0
    
    market_picks = [h for h in resolved if h.get('market_correct') is not None]
    market_correct = sum(1 for h in market_picks if h.get('market_correct'))
    market_acc = round(market_correct / len(market_picks) * 100, 1) if market_picks else 0
    
    # Edge buckets
    edge_5_plus = [h for h in resolved if h.get('edge') and h.get('edge') >= 5]
    edge_neg_5 = [h for h in resolved if h.get('edge') and h.get('edge') <= -5]
    edge_small = [h for h in resolved if h.get('edge') and abs(h.get('edge')) < 5]
    
    return jsonify({
        "total_resolved": len(resolved),
        "model_accuracy": model_acc,
        "model_correct": model_correct,
        "market_accuracy": market_acc,
        "market_correct": market_correct,
        "market_picks": len(market_picks),
        "big_edge_positive": {
            "count": len(edge_5_plus),
            "correct": sum(1 for h in edge_5_plus if h.get('correct')),
            "accuracy": round(sum(1 for h in edge_5_plus if h.get('correct')) / len(edge_5_plus) * 100, 1) if edge_5_plus else 0
        },
        "big_edge_negative": {
            "count": len(edge_neg_5),
            "correct": sum(1 for h in edge_neg_5 if h.get('correct')),
            "accuracy": round(sum(1 for h in edge_neg_5 if h.get('correct')) / len(edge_neg_5) * 100, 1) if edge_neg_5 else 0
        },
        "small_edge": {
            "count": len(edge_small),
            "correct": sum(1 for h in edge_small if h.get('correct')),
            "accuracy": round(sum(1 for h in edge_small if h.get('correct')) / len(edge_small) * 100, 1) if edge_small else 0
        }
    })


@app.route('/misses_analysis', methods=['GET'])
def misses_analysis():
    """Group wrong predictions by suspected cause."""
    history = load_prediction_history()
    misses = [e for e in history if e.get("correct") is False]

    buckets = {
        "high_edge_vs_market": 0,
        "market_favored": 0,
        "non_divisional": 0,
        "divisional": 0,
        "small_spread": 0,
        "large_spread": 0,
        "unknown": 0,
    }
    for m in misses:
        edge = m.get("edge")
        ms = m.get("market_spread")
        t1 = m.get("team1")
        t2 = m.get("team2")

        if edge is not None and abs(edge) >= 5:
            buckets["high_edge_vs_market"] += 1
        if ms is not None and abs(ms) <= 3:
            buckets["small_spread"] += 1
        if ms is not None and abs(ms) >= 10:
            buckets["large_spread"] += 1
        if t1 and t2:
            if is_divisional(t1, t2):
                buckets["divisional"] += 1
            else:
                buckets["non_divisional"] += 1

    return jsonify({
        "total_misses": len(misses),
        "buckets": buckets,
        "note": "Buckets overlap — a miss can count in multiple."
    })

@app.route('/learning_report', methods=['GET'])
def learning_report():
    """Shows which factors actually predict wins based on logged results"""
    history = load_prediction_history()
    resolved = [h for h in history if h.get('correct') is not None]
    if len(resolved) < 10:
        return jsonify({"status": "need_more_data", "resolved": len(resolved), "message": "Need 10+ resolved predictions"})
    
    # Accuracy by confidence level
    low_conf = [h for h in resolved if (h.get('confidence') or 0) < 10]
    med_conf = [h for h in resolved if 10 <= (h.get('confidence') or 0) < 18]
    high_conf = [h for h in resolved if (h.get('confidence') or 0) >= 18]
    
    # Accuracy by edge size
    big_edge = [h for h in resolved if h.get('edge') and abs(h.get('edge', 0)) >= 10]
    small_edge = [h for h in resolved if h.get('edge') and abs(h.get('edge', 0)) < 5]
    
    def acc(lst):
        if not lst: return None
        return round(sum(1 for h in lst if h.get('correct')) / len(lst) * 100, 1)
    
    return jsonify({
        "total_resolved": len(resolved),
        "overall_accuracy": acc(resolved),
        "by_confidence": {
            "low_under_10": {"count": len(low_conf), "accuracy": acc(low_conf)},
            "medium_10_18": {"count": len(med_conf), "accuracy": acc(med_conf)},
            "high_over_18": {"count": len(high_conf), "accuracy": acc(high_conf)}
        },
        "by_edge": {
            "big_edge_10plus": {"count": len(big_edge), "accuracy": acc(big_edge)},
            "small_edge_under_5": {"count": len(small_edge), "accuracy": acc(small_edge)}
        }
    })


@app.route('/signal_attribution', methods=['GET'])
def signal_attribution():
    """
    For each signal, compute: how often was it present, and when present,
    did the prediction it fired on win?
    Also: are signals additive (present together → higher accuracy)?
    """
    history = load_prediction_history()
    resolved = [e for e in history if e.get('correct') is not None]

    if len(resolved) < 20:
        return jsonify({
            "status": "need_more_data",
            "resolved": len(resolved),
            "message": "Need 20+ resolved predictions to compute signal attribution"
        })

    # Signal categories we care about
    signals = ["qb_epa", "contrarian", "schedule", "coaching", "ml_model"]

    per_signal = {}
    for sig in signals:
        with_sig = [e for e in resolved if sig in (e.get('signals_present') or [])]
        without = [e for e in resolved if sig not in (e.get('signals_present') or [])]

        def acc(lst):
            if not lst:
                return None
            return round(100.0 * sum(1 for e in lst if e.get('correct')) / len(lst), 1)

        per_signal[sig] = {
            "with_count": len(with_sig),
            "with_accuracy": acc(with_sig),
            "without_count": len(without),
            "without_accuracy": acc(without),
            "lift": round((acc(with_sig) or 0) - (acc(without) or 0), 1) if with_sig and without else None
        }

    # Signal-stacking: how does accuracy change with 0, 1, 2+ signals present?
    by_signal_count = {}
    for e in resolved:
        n = len(e.get('signals_present') or [])
        by_signal_count.setdefault(n, []).append(e)

    stacking = {}
    for k in sorted(by_signal_count.keys()):
        lst = by_signal_count[k]
        stacking[k] = {
            "count": len(lst),
            "accuracy": round(100.0 * sum(1 for e in lst if e.get('correct')) / len(lst), 1)
        }

    # Confidence-bucket accuracy for the signals that ARE present
    by_confidence = {}
    for e in resolved:
        conf = e.get('confidence') or 0
        bucket = int(conf // 10) * 10
        by_confidence.setdefault(bucket, []).append(e)

    confidence_accuracy = {}
    for b in sorted(by_confidence.keys()):
        lst = by_confidence[b]
        confidence_accuracy[f"{b}-{b+10}"] = {
            "count": len(lst),
            "accuracy": round(100.0 * sum(1 for e in lst if e.get('correct')) / len(lst), 1)
        }

    return jsonify({
        "total_resolved": len(resolved),
        "per_signal": per_signal,
        "signal_stacking": stacking,
        "confidence_buckets": confidence_accuracy,
        "interpretation": {
            "lift": "Positive = signal adds accuracy when present. Negative = signal is anti-correlated.",
            "stacking": "More signals present should correlate with higher accuracy, if signals are independent."
        }
    })

@app.route('/similar_matchups', methods=['GET'])
def similar_matchups():
    """
    Find historical games with the closest feature profile to a current matchup.
    Uses nfl_advanced_games_v3.csv as the history source.
    """
    team1 = request.args.get("team1", "").strip()
    team2 = request.args.get("team2", "").strip()
    top_n = int(request.args.get("top", 5))
    if not team1 or not team2:
        return jsonify({"error": "team1 and team2 required"}), 400

    try:
        import pandas as pd
        df = pd.read_csv("nfl_advanced_games_v3.csv")
    except Exception as e:
        return jsonify({"error": f"could not load data: {e}"}), 500

    # Normalize columns we care about
    needed = ["home_team", "away_team", "home_score", "away_score", "season", "week"]
    for col in needed:
        if col not in df.columns:
            return jsonify({"error": f"missing column {col}"}), 500

    # CSV uses abbreviations (KC, BUF, TEN). Convert full names to abbrevs.
    abbr1 = TEAM_MAP.get(team1, team1.upper()[:3]).upper()
    abbr2 = TEAM_MAP.get(team2, team2.upper()[:3]).upper()

    # Handle CSV-specific aliases
    aliases = {
        "LAR": "LA", "STL": "LA",     # Rams
        "LAC": "LAC", "SD": "LAC",    # Chargers (LAC is already correct)
        "WSH": "WAS", "WAS": "WAS",   # Commanders
        "OAK": "LV", "LVR": "LV",     # Raiders
        "JAC": "JAX",                 # Jaguars
        "ARZ": "ARI",                 # Cardinals
        "BLT": "BAL", "CLV": "CLE",   # old abbreviations
        "HST": "HOU",                 # Oilers/Texans
    }
    abbr1 = aliases.get(abbr1, abbr1)
    abbr2 = aliases.get(abbr2, abbr2)

    # Filter: either team appeared in the row (home OR away)
    home_up = df["home_team"].astype(str).str.upper()
    away_up = df["away_team"].astype(str).str.upper()
    mask = (
        (home_up == abbr1) | (home_up == abbr2) |
        (away_up == abbr1) | (away_up == abbr2)
    )
    candidates = df[mask].copy()

    if candidates.empty:
        return jsonify({
            "similar": [],
            "note": f"no historical matchups found ({abbr1} vs {abbr2})",
            "debug": {"team1_abbr": abbr1, "team2_abbr": abbr2, "csv_rows": len(df)}
        })

    # Similarity: exact matchup (either direction) gets highest weight
    def score_row(row):
        ht = str(row["home_team"]).upper()
        at = str(row["away_team"]).upper()
        score = 0
        # Exact matchup in either direction
        if (ht == abbr1 and at == abbr2) or (ht == abbr2 and at == abbr1):
            score += 100
        # Same home team as either team in query
        if ht == abbr1 or ht == abbr2:
            score += 20
        # Same away team as either team in query
        if at == abbr1 or at == abbr2:
            score += 10
        # Recency bonus
        try:
            score += int(row.get("season", 2020)) - 2020
        except Exception:
            pass
        return score

    candidates["_sim"] = candidates.apply(score_row, axis=1)
    top = candidates.nlargest(top_n, "_sim")

    results = []
    for _, row in top.iterrows():
        home_score = int(row["home_score"]) if pd.notna(row["home_score"]) else None
        away_score = int(row["away_score"]) if pd.notna(row["away_score"]) else None
        winner = None
        margin = None
        if home_score is not None and away_score is not None:
            winner = row["home_team"] if home_score > away_score else row["away_team"]
            margin = abs(home_score - away_score)

        results.append({
            "season": int(row.get("season", 0)),
            "week": int(row.get("week", 0)),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "home_score": home_score,
            "away_score": away_score,
            "winner": winner,
            "margin": margin,
        })

    # Aggregate: how often did home team win in similar matchups?
    home_wins = sum(1 for r in results if r["winner"] == r["home_team"])
    away_wins = sum(1 for r in results if r["winner"] == r["away_team"])

    return jsonify({
        "similar": results,
        "summary": {
            "home_wins": home_wins,
            "away_wins": away_wins,
            "total": len(results),
        }
    })

@app.route('/drift', methods=['GET'])
def drift_check():
    """Check if rolling accuracy has dropped significantly."""
    return jsonify(detect_drift())


@app.route('/blend_weight', methods=['GET'])
def blend_weight():
    """Current adaptive model/market blend weight."""
    w = get_adaptive_blend_weight()
    return jsonify({
        "market_weight": w,
        "model_weight": round(1.0 - w, 2),
        "note": "Higher market weight = trusting sportsbooks more than the model"
    })


@app.route('/team_bias', methods=['GET'])
def team_bias():
    """Which teams the model systematically misjudges."""
    min_g = int(request.args.get('min_games', 3))
    return jsonify({
        "min_games": min_g,
        "teams": get_team_bias_report(min_g)
    })


@app.route('/calibration', methods=['GET'])
def calibration():
    """Return the current calibration table + backtest comparison."""
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]

    # Compute empirical accuracy per bucket
    buckets = {(0, 50): [], (50, 60): [], (60, 70): [], (70, 80): [], (80, 100): []}
    for e in resolved:
        conf = e.get("confidence") or 0
        for key in buckets:
            if key[0] <= conf < key[1]:
                buckets[key].append(1 if e.get("correct") else 0)
                break

    empirical = {}
    for (lo, hi), entries in buckets.items():
        if not entries:
            continue
        total_w = sum(w for _, w in entries)
        wins_w = sum(c for c, _ in entries if c == 1 for _ in [w])  # weighted wins
        wins_w = sum(c * w for c, w in entries)
        acc = (wins_w / total_w * 100) if total_w > 0 else 0
        key = (lo, hi)
        empirical[f"{lo}-{hi}"] = {
            "acc": round(acc, 1),
            "n": len(entries),
            "weighted_n": round(total_w, 1),
            "table_value": round(CALIBRATION_TABLE.get(key, 0.52) * 100, 1)
        }
    for key, results in buckets.items():
        empirical[f"{key[0]}-{key[1]}"] = {
            "samples": len(results),
            "accuracy": round(100.0 * sum(results) / len(results), 1) if results else None,
            "table_value": round(CALIBRATION_TABLE.get(key, 0.52) * 100, 1)
        }

    return jsonify({
        "total_resolved": len(resolved),
        "current_table": {f"{k[0]}-{k[1]}": round(v*100, 1) for k, v in CALIBRATION_TABLE.items()},
        "empirical": empirical,
        "note": "When empirical accuracy diverges from table_value by >5 points in a bucket with 10+ samples, run /auto_tune"
    })

@app.route('/backtest', methods=['GET'])
def backtest():
    """Run the prediction history through filters to compute accuracy by slice."""
    history = load_prediction_history()
    resolved = [e for e in history if e.get("correct") is not None]

    def acc(entries):
        if not entries:
            return {"total": 0, "correct": 0, "accuracy": 0.0}
        c = sum(1 for e in entries if e.get("correct") is True)
        return {"total": len(entries), "correct": c, "accuracy": round(100.0 * c / len(entries), 1)}

    by_week = {}
    by_confidence = {"50-60": [], "60-70": [], "70-80": [], "80+": [], "under50": []}
    by_side = {"home_pick": [], "away_pick": []}
    by_edge = {"edge_pos": [], "edge_neg": [], "edge_zero": []}
    by_divisional = {"divisional": [], "non_divisional": []}

    for e in resolved:
        # Week
        wk = (e.get("date") or "")[:10]
        by_week.setdefault(wk, []).append(e)

        # Confidence
        conf = e.get("confidence") or 0
        if conf < 50: by_confidence["under50"].append(e)
        elif conf < 60: by_confidence["50-60"].append(e)
        elif conf < 70: by_confidence["60-70"].append(e)
        elif conf < 80: by_confidence["70-80"].append(e)
        else: by_confidence["80+"].append(e)

        # Home/away pick
        if e.get("predicted_winner") == e.get("team1"):
            by_side["home_pick"].append(e)
        elif e.get("predicted_winner") == e.get("team2"):
            by_side["away_pick"].append(e)

        # Edge
        edge = e.get("edge") or 0
        if edge > 1: by_edge["edge_pos"].append(e)
        elif edge < -1: by_edge["edge_neg"].append(e)
        else: by_edge["edge_zero"].append(e)

        # Divisional
        t1, t2 = e.get("team1"), e.get("team2")
        if t1 and t2:
            if is_divisional(t1, t2): by_divisional["divisional"].append(e)
            else: by_divisional["non_divisional"].append(e)

    return jsonify({
        "overall": acc(resolved),
        "by_date": {k: acc(v) for k, v in sorted(by_week.items())},
        "by_confidence": {k: acc(v) for k, v in by_confidence.items()},
        "by_side": {k: acc(v) for k, v in by_side.items()},
        "by_edge": {k: acc(v) for k, v in by_edge.items()},
        "by_divisional": {k: acc(v) for k, v in by_divisional.items()},
    })

@app.route('/auto_tune', methods=['GET'])
def auto_tune():
    """Analyze log and recommend weight adjustments based on outcomes"""
    history = load_prediction_history()
    resolved = [h for h in history if h.get('correct') is not None]
    if len(resolved) < 15:
        return jsonify({"status": "need_data", "resolved": len(resolved), "message": "Need 15+ resolved for tuning"})
    
    total = len(resolved)
    correct = sum(1 for h in resolved if h.get('correct'))
    base_rate = correct / total
    
    # Which confidence buckets do well?
    bucket_analysis = {}
    for conf_bucket in [(0, 8), (8, 15), (15, 25), (25, 36)]:
        bucket = [h for h in resolved if conf_bucket[0] <= (h.get('confidence') or 0) < conf_bucket[1]]
        if bucket:
            acc = sum(1 for h in bucket if h.get('correct')) / len(bucket)
            bucket_analysis[f"{conf_bucket[0]}-{conf_bucket[1]}"] = {
                "count": len(bucket),
                "accuracy": round(acc * 100, 1),
                "vs_base": round((acc - base_rate) * 100, 1)
            }
    
    # Market vs Model - who is right more?
    market_correct = sum(1 for h in resolved if h.get('market_correct') == True)
    market_total = sum(1 for h in resolved if h.get('market_correct') is not None)
    market_rate = (market_correct / market_total) if market_total else 0
    
    # Recommendation
    recommendation = "keep_weights"
    if market_total >= 10 and market_rate > base_rate + 0.05:
        recommendation = "increase_market_weight"
    elif base_rate > 0.6:
        recommendation = "model_working_keep"
    elif base_rate < 0.45:
        recommendation = "flip_to_market_only"
    
    return jsonify({
        "total_resolved": total,
        "model_accuracy": round(base_rate * 100, 1),
        "market_accuracy": round(market_rate * 100, 1) if market_total else None,
        "confidence_buckets": bucket_analysis,
        "recommendation": recommendation,
        "sample_size": "good" if total >= 50 else "building" if total >= 20 else "small"
    })


@app.route('/debug_prediction', methods=['GET'])
def debug_prediction():
    """Return the full feature vector used for a prediction."""
    team1 = request.args.get("team1", "").strip()
    team2 = request.args.get("team2", "").strip()
    if not team1 or not team2:
        return jsonify({"error": "team1 and team2 required"}), 400

    # Reuse the existing ml prediction logic but expose internals
    try:
        from feature_updater import build_features, predict_ml_probability
        feats = build_features(team1, team2) if hasattr(__import__("feature_updater"), "build_features") else {}
    except Exception as e:
        feats = {"error": str(e)}

    return jsonify({
        "team1": team1,
        "team2": team2,
        "is_divisional": is_divisional(team1, team2),
        "features": feats,
    })

@app.route('/ml_predict', methods=['GET'])
def ml_predict():
    """Prediction using trained ML model"""
    team1 = request.args.get('team1')
    team2 = request.args.get('team2')
    if not team1 or not team2:
        return jsonify({"error": "Invalid teams"}), 400
    
    prob_home = predict_ml_probability(team1, team2)
    if prob_home is None:
        return jsonify({"error": "Insufficient data for ML prediction"}), 400
    
    # Fetch market data
    market_home_prob = None
    market_spread = None
    market_total = None
    edge = None
    try:
        odds_url = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
        odds_params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "spreads,totals,h2h", "oddsFormat": "american"}
        odds_resp = requests.get(odds_url, params=odds_params, timeout=10)
        if odds_resp.status_code == 200:
            for og in odds_resp.json():
                oh = og.get('home_team', '')
                oa = og.get('away_team', '')
                if (oh == team1 and oa == team2):
                    spreads_h = []
                    totals_o = []
                    h_mls = []
                    a_mls = []
                    for bk in og.get('bookmakers', []):
                        for mk in bk.get('markets', []):
                            if mk['key'] == 'spreads':
                                for o in mk['outcomes']:
                                    if o['name'] == team1: spreads_h.append(o['point'])
                            elif mk['key'] == 'totals':
                                for o in mk['outcomes']:
                                    if o['name'] == 'Over': totals_o.append(o['point'])
                            elif mk['key'] == 'h2h':
                                for o in mk['outcomes']:
                                    if o['name'] == team1: h_mls.append(o['price'])
                                    else: a_mls.append(o['price'])
                    if spreads_h: market_spread = round(sum(spreads_h) / len(spreads_h), 1)
                    if totals_o: market_total = round(sum(totals_o) / len(totals_o), 1)
                    if h_mls and a_mls:
                        ah = sum(h_mls) / len(h_mls)
                        aa = sum(a_mls) / len(a_mls)
                        def m2p(ml): return (100/(ml+100)) if ml > 0 else (abs(ml)/(abs(ml)+100))
                        hp = m2p(ah); ap = m2p(aa)
                        market_home_prob = round(hp / (hp + ap) * 100, 1)
                    break
    except:
        pass
    
    # Blend: use adaptive weight from /blend_weight, defaults to 50/50
    ml_prob_pct = prob_home * 100
    if market_home_prob is not None:
        market_weight = get_adaptive_blend_weight()
        model_weight = 1.0 - market_weight
        blended = round(ml_prob_pct * model_weight + market_home_prob * market_weight, 1)
        edge = round(ml_prob_pct - market_home_prob, 1)
    else:
        blended = round(ml_prob_pct, 1)

    # ───── APPLY ADVANCED SIGNALS ─────
    advanced_adjustments = []

    # Initialize factors here in ml_predict scope (was only defined in predict_winner)
    factors = []
    factors_detail = []

    # 1. Contrarian public betting signal
    try:
        home_public_pct = get_public_betting_signal(team1, team2)
        contrarian_delta = contrarian_adjustment(home_public_pct)
        if abs(contrarian_delta) > 0.1:
            blended = round(blended + contrarian_delta, 1)
            advanced_adjustments.append(f"Contrarian: {contrarian_delta:+.1f}% (public {home_public_pct:.0f}% on {team1})")
    except Exception:
        pass

    # 2. Schedule spot detection (both teams)
    try:
        spots_home = detect_schedule_spot(team1)
        spots_away = detect_schedule_spot(team2)
        spot_home_impact = schedule_spot_impact(spots_home)
        spot_away_impact = schedule_spot_impact(spots_away)
        net_spot = spot_home_impact - spot_away_impact
        if abs(net_spot) > 0.1:
            blended = round(blended + net_spot, 1)
            home_tags = ", ".join(s["tag"] for s in spots_home) or "none"
            away_tags = ", ".join(s["tag"] for s in spots_away) or "none"
            advanced_adjustments.append(f"Schedule: {net_spot:+.1f}% (home: {home_tags} | away: {away_tags})")
    except Exception:
        pass

    # 3. Coach tendencies (default: no situation = home_favorite or divisional)
    try:
        home_coach_adj = coach_adjustment(team1, "home_favorite") + coach_adjustment(team1, "divisional")
        away_coach_adj = coach_adjustment(team2, "road_underdog") + coach_adjustment(team2, "divisional")
        net_coach = home_coach_adj - away_coach_adj
        if abs(net_coach) > 0.1:
            blended = round(blended + net_coach, 1)
            advanced_adjustments.append(f"Coaching: {net_coach:+.1f}%")
    except Exception:
        pass

    # ───── ACCURACY IMPROVEMENTS ─────
    is_no_pick = False
    no_pick_reasons = []

    # MARKET_DISAGREEMENT_FILTER: if model and book disagree by >15%, it's a blind spot
    if market_home_prob is not None:
        disagreement = abs(ml_prob_pct - market_home_prob)
        if disagreement > 15.0:
            is_no_pick = True
            no_pick_reasons.append(f"Model/Market disagreement {disagreement:.1f}% (>15% threshold)")
            advanced_adjustments.append(f"⚠ NO PICK: model vs market disagree {disagreement:.1f}%")

    # SIGNAL_CONFLICT_PENALTY: if 2+ adjustments push opposite directions, penalize
    pos_count = sum(1 for a in advanced_adjustments if ": +" in a)
    neg_count = sum(1 for a in advanced_adjustments if ": -" in a)
    if pos_count >= 1 and neg_count >= 1 and len(advanced_adjustments) >= 2:
        blended = round(blended - 8.0, 1)
        advanced_adjustments.append(f"⚠ Signal conflict penalty: -8.0% (had {pos_count}+ / {neg_count}-)")
        no_pick_reasons.append(f"Conflicting signals ({pos_count} positive, {neg_count} negative)")

    # Clamp blended to sane range
    blended = max(1.0, min(99.0, blended))

    # QB rolling EPA comparison
    try:
        home_qb_epa = get_qb_recent_epa(team1, last_n=4)
        away_qb_epa = get_qb_recent_epa(team2, last_n=4)
        if home_qb_epa is not None and away_qb_epa is not None:
            epa_diff = home_qb_epa - away_qb_epa
            if abs(epa_diff) >= 0.05:
                factors.append(f"QB EPA (last 4): {team1} {home_qb_epa:+.2f} vs {team2} {away_qb_epa:+.2f}")
                factors_detail.append("Rolling 4-game QB Expected Points Added — recent form signal.")
    except Exception:
        pass

    # Log all advanced adjustments (or note that none triggered)
    if advanced_adjustments:
        for adj in advanced_adjustments:
            factors.append(adj)
            factors_detail.append("Advanced signal applied to the blended probability.")
    else:
        factors.append("Advanced signals: none triggered")
        factors_detail.append("No contrarian/schedule/coaching adjustments applied (market data missing or no triggers).")

    # Winner ALWAYS based on blended probability
    winner = team1 if blended > 50 else team2

    # Raw confidence = distance from 50/50
    raw_confidence = round(abs(blended - 50) * 2, 1)

    # CALIBRATED confidence — real-world accuracy in this bucket
    NO_PICK_MAX_RAW_CONF = 10.0
    NO_PICK_INVERTED_MIN = 20.0
    NO_PICK_INVERTED_MAX = 30.0
    is_no_pick = is_no_pick or \
                 (raw_confidence < NO_PICK_MAX_RAW_CONF) or \
                 (NO_PICK_INVERTED_MIN <= raw_confidence < NO_PICK_INVERTED_MAX)
    confidence = calibrated_confidence(blended)
    raw_conf_pct = raw_confidence

    conf_level = "HIGH" if confidence >= 65 else "MEDIUM" if confidence >= 55 else "LOW"

    # Model spread from probability
    ml_spread = (ml_prob_pct - 50) / 50 * 14

    # Blend with market if available
    if market_spread is not None:
        model_spread_from_home = -ml_spread
        blended_spread = market_spread * 0.6 + model_spread_from_home * 0.4
    else:
        blended_spread = -ml_spread

    # Round to nearest .0 or .5 (NFL convention)
    blended_spread = round(blended_spread * 2) / 2

    # Total: use market if available, otherwise derive from model strength
    if market_total is not None:
        total = int(round(market_total))
    else:
        try:
            def _ppg(team_name):
                abbr = TEAM_MAP.get(team_name, '')
                sched = get_cached_or_fetch(f"{ESPN_SITE_V2}/teams/{abbr}/schedule?season=2026&seasontype=2", f"ppg_{abbr}")
                if not sched or 'events' not in sched: return 22.0
                pf_total = 0; games = 0
                for ev in sched['events']:
                    comp = ev.get('competitions', [{}])[0]
                    if not comp.get('status', {}).get('type', {}).get('completed'): continue
                    for c in comp.get('competitors', []):
                        if c.get('team', {}).get('abbreviation', '').upper() == abbr.upper():
                            sv = c.get('score', 0)
                            if isinstance(sv, dict): sv = sv.get('value', 0)
                            pf_total += int(sv) if sv else 0; games += 1; break
                return (pf_total / games) if games > 0 else 22.0
            computed_total = _ppg(team1) + _ppg(team2) - 0.3 * abs(blended_spread)
            total = max(38, min(56, int(round(computed_total))))
        except Exception:
            total = max(34, min(56, int(round(45 - 0.5 * abs(blended_spread)))))

    # Derive scores from spread + total
    s1 = int(round(total / 2 - blended_spread / 2))
    s2 = int(round(total / 2 + blended_spread / 2))
    s1 = max(10, s1)
    s2 = max(10, s2)

    # Ensure score matches winner
    if winner == team1 and s1 <= s2:
        s1 = s2 + 3
    elif winner == team2 and s2 <= s1:
        s2 = s1 + 3
    actual_total = s1 + s2
    if actual_total != total:
        diff = total - actual_total
        s1 += diff // 2
        s2 += diff - (diff // 2)

    # Apply primetime/TNF slot adjustments
    slot = "SUNDAY_EARLY"
    spread_mult, total_delta = slot_adjustments(slot)
    blended_spread = blended_spread * spread_mult
    total = int(round(total + total_delta))

    # Spread display: .0 or .5
    bs = abs(blended_spread)
    bs_str = f"{bs:.1f}"
    if blended_spread < 0:
        our_spread_str = f"{team1} -{bs_str}"
    elif blended_spread > 0:
        our_spread_str = f"{team2} -{bs_str}"
    else:
        our_spread_str = "Pick'em"

    # Confidence string (calibrated value)
    factors.append(f"Confidence: {confidence}% ({conf_level})")
    factors_detail.append("Calibrated confidence — real historical accuracy for this probability bucket.")

    # Log for self-learning
    try:
        history = load_prediction_history()
        # DEDUPE: Skip logging if this exact matchup was logged in the last 30 minutes
        _skip_log = False
        for _prev in reversed(history[-30:]):
            if _prev.get('team1') == team1 and _prev.get('team2') == team2:
                if time.time() - _prev.get('timestamp', 0) < 1800:
                    _skip_log = True
                    break
        if not _skip_log:
            history.append({
                "timestamp": time.time(),
                "date": time.strftime("%Y-%m-%d %H:%M"),
                "team1": team1, "team2": team2,
                "predicted_winner": winner,
                "predicted_score": f"{s1}-{s2}",
                "predicted_spread": our_spread_str,
                "predicted_total": total,
                "confidence": confidence,
                "raw_confidence": raw_conf_pct,
                "market_home_prob": market_home_prob,
                "market_spread": market_spread,
                "market_total": market_total,
                "edge": edge,
                "actual_winner": None, "actual_score": None, "correct": None,
                "model_source": "ml_v3",
                "opening_spread": market_spread,
                "clv": None,
                "game_slot": slot,
            })
            save_prediction_history(history)
    except Exception:
        pass

    return jsonify({
        "team1": team1,
        "team2": team2,
        "team1_win_probability": round(100 - blended, 1),
        "team2_win_probability": round(blended, 1),
        "predicted_winner": winner,
        "predicted_score": f"{s1}-{s2}",
        "predicted_spread": our_spread_str,
        "predicted_total": total,
        "confidence": confidence,
        "confidence_level": conf_level,
        "raw_confidence": raw_conf_pct,
        "calibrated": True,
        "is_no_pick": is_no_pick,
        "ml_home_probability": round(ml_prob_pct, 1),
        "market_home_prob": market_home_prob,
        "blended_home_probability": round(blended, 1),
        "edge": edge,
        "market_spread": (round(market_spread * 2) / 2 if market_spread is not None else None),
        "market_total": (int(round(market_total)) if market_total is not None else None),
        "key_factors": factors,
        "key_factors_detail": factors_detail,
        "game_slot": slot
    })

def _start_mdns_broadcast(port=5000):
    """Broadcast _nflpredict._tcp.local. on the local network."""
    try:
        from zeroconf import ServiceInfo, Zeroconf
        import socket
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "127.0.0.1"
        info = ServiceInfo(
            "_nflpredict._tcp.local.",
            "NFLPredictor._nflpredict._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=port,
            properties={"version": "1", "app": "NFL-Betting-Predictor"},
            server=f"{hostname}.local.",
        )
        zc = Zeroconf()
        zc.register_service(info)
        print(f"mDNS broadcast started on {local_ip}:{port}")
        return zc
    except ImportError:
        print("zeroconf not installed — mDNS broadcast disabled (pip install zeroconf)")
        return None
    except Exception as e:
        print(f"mDNS broadcast failed: {e}")
        return None


if __name__ == "__main__":
    print("NFL API Running on http://localhost:5000")
    _zc = _start_mdns_broadcast(5000)
    _start_auto_resolve()
    try:
        app.run(host="0.0.0.0", port=5000, debug=True)
    finally:
        if _zc:
            try: _zc.close()
            except Exception: pass
