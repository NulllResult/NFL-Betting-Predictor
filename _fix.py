c=open("betting_api.py").read()
e="""@app.route('/live_scores', methods=['GET'])
def get_live_scores():
    url = f"{ESPN_SITE_V2}/scoreboard?dates=2026"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return jsonify({"scores": []})
        data = response.json()
        games = []
        for event in data.get("events", []):
            status = event.get("status", {}).get("type", {})
            state = status.get("description", "Scheduled")
            detail = status.get("shortDetail", "")
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            if len(competitors) >= 2:
                away = competitors[0]
                home = competitors[1]
                games.append({"away": away.get("team", {}).get("abbreviation", "N/A"), "home": home.get("team", {}).get("abbreviation", "N/A"), "away_score": int(away.get("score", 0)), "home_score": int(home.get("score", 0)), "status": state, "detail": detail})
        live = [g for g in games if g["status"] in ["In Progress", "Halftime"]]
        return jsonify({"scores": live if live else games[:5]})
    except:
        return jsonify({"scores": []})
"""
c=c.replace("if __name__ == '__main__':",e+"\nif __name__ == '__main__':")
open("betting_api.py","w").write(c)
print("Done")
