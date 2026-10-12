package com.bestg.betting

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.*
import android.text.method.ScrollingMovementMethod
import android.app.AlertDialog
import android.content.Context
import android.content.SharedPreferences
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.button.MaterialButton
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

class MainActivity : AppCompatActivity() {

    private lateinit var spinnersRow: LinearLayout
    private lateinit var teamSpinner: Spinner
    private lateinit var playerSpinner: Spinner
    private lateinit var resultText: TextView
    private lateinit var scoreBanner: TextView
    private lateinit var loadingIndicator: ProgressBar
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var gamesContainer: LinearLayout
    private lateinit var gamesScroll: ScrollView
    private lateinit var gamesList: LinearLayout
    private lateinit var apiService: ApiService
    private lateinit var sharedPrefs: SharedPreferences

    private var currentMode = "STATS"
    private var helpCycle = 0
    private var currentTeam = ""
    private var currentPlayer = ""
    private var opponentTeam = ""
    private var serverIp = "10.0.0.60"

    private val allNFLTeams = listOf(
        "Buffalo Bills", "Miami Dolphins", "New England Patriots", "New York Jets",
        "Baltimore Ravens", "Cincinnati Bengals", "Cleveland Browns", "Pittsburgh Steelers",
        "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Tennessee Titans",
        "Denver Broncos", "Kansas City Chiefs", "Las Vegas Raiders", "Los Angeles Chargers",
        "Dallas Cowboys", "New York Giants", "Philadelphia Eagles", "Washington Commanders",
        "Chicago Bears", "Detroit Lions", "Green Bay Packers", "Minnesota Vikings",
        "Atlanta Falcons", "Carolina Panthers", "New Orleans Saints", "Tampa Bay Buccaneers",
        "Arizona Cardinals", "Los Angeles Rams", "San Francisco 49ers", "Seattle Seahawks"
    )

    private val manualStats = mutableMapOf<String, MutableMap<String, String>>()
    private val scoreHandler = Handler(Looper.getMainLooper())
    private val favoriteTeams = mutableSetOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        sharedPrefs = getSharedPreferences("NFL_Betting_Prefs", Context.MODE_PRIVATE)
        loadManualOverrides()
        favoriteTeams.addAll(sharedPrefs.getStringSet("favorite_teams", emptySet()) ?: emptySet())
        serverIp = sharedPrefs.getString("server_ip", "10.0.0.60") ?: "10.0.0.60"

        spinnersRow = findViewById(R.id.spinnersRow)
        teamSpinner = findViewById(R.id.teamSpinner)
        playerSpinner = findViewById(R.id.playerSpinner)
        resultText = findViewById(R.id.resultText)
        scoreBanner = findViewById(R.id.scoreBanner)
        loadingIndicator = findViewById(R.id.loadingIndicator)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        gamesContainer = findViewById(R.id.gamesContainer)
        gamesScroll = findViewById(R.id.gamesScroll)
        gamesList = findViewById(R.id.gamesList)

        resultText.movementMethod = ScrollingMovementMethod()
        scoreBanner.isSelected = true
        setupRetrofit()
        playerSpinner.visibility = View.GONE

        swipeRefresh.setOnRefreshListener {
            when (currentMode) {
                "STATS" -> getTeamStats()
                "PLAYER" -> getPlayerStats()
                "PREDICT" -> fetchPrediction(currentTeam, opponentTeam)
            }
            fetchLiveScores()
        }



        findViewById<MaterialButton>(R.id.testButton).setOnClickListener { testConnection() }
        findViewById<MaterialButton>(R.id.loadStatsButton).setOnClickListener { findViewById<MaterialButton>(R.id.refreshAllButton).text = "REFRESH"; setStatsMode() }
        findViewById<MaterialButton>(R.id.loadPlayerButton).setOnClickListener { findViewById<MaterialButton>(R.id.refreshAllButton).text = "REFRESH"; setPlayerMode() }
        findViewById<MaterialButton>(R.id.predictButton).setOnClickListener { findViewById<MaterialButton>(R.id.refreshAllButton).text = "REFRESH"; setPredictMode() }
        findViewById<MaterialButton>(R.id.refreshAllButton).setOnClickListener {
            if (currentMode == "PREDICT" && gamesContainer.visibility == View.GONE) {
                // Act as BACK button
                gamesContainer.visibility = View.VISIBLE
                swipeRefresh.visibility = View.GONE
                findViewById<MaterialButton>(R.id.refreshAllButton).text = "REFRESH"
                setPredictMode()
            } else {
                when (currentMode) {
                    "STATS" -> getTeamStats()
                    "PLAYER" -> getPlayerStats()
                    "PREDICT" -> fetchPrediction(currentTeam, opponentTeam)
                }
                fetchLiveScores()
            }
        }
        findViewById<MaterialButton>(R.id.clearButton).setOnClickListener { resultText.text = "" }
        findViewById<MaterialButton>(R.id.helpButton).setOnClickListener {
            // Always hide games container so we can show text
            gamesContainer.visibility = View.GONE
            swipeRefresh.visibility = View.VISIBLE
            resultText.visibility = View.VISIBLE
            helpCycle = (helpCycle + 1) % 7
            when (helpCycle) {
                0 -> showHelp()
                1 -> showAccuracy()
                2 -> showPredictionLog()
                3 -> showLivePredictions()
                4 -> showOdds()
                5 -> {
                    if (currentPlayer.isEmpty()) {
                        resultText.text = "Select a player first in PLAYER mode\n\nTap HELP again to continue"
                    } else {
                        showPlayerProps()
                    }
                }
                6 -> showServerIpDialog()
            }
        }

        setPredictMode()
        fetchLiveScores()
        startScoreUpdates()
    }

    private fun setupRetrofit() {
        val retrofit = Retrofit.Builder()
            .baseUrl("http://$serverIp:5000/")
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        apiService = retrofit.create(ApiService::class.java)
    }

    private fun startScoreUpdates() {
        scoreHandler.postDelayed(object : Runnable {
            override fun run() {
                fetchLiveScores()
                scoreHandler.postDelayed(this, 30000)
            }
        }, 30000)
    }

    private fun fetchLiveScores() {
        apiService.getLiveScores().enqueue(object : Callback<LiveScoresResponse> {
            override fun onResponse(call: Call<LiveScoresResponse>, response: Response<LiveScoresResponse>) {
                if (response.isSuccessful) {
                    val scores = response.body()?.scores ?: emptyList()
                    if (scores.isNotEmpty()) {
                        scoreBanner.text = scores.joinToString(" | ") {
                            "${it.away} ${it.away_score}-${it.home_score} ${it.home} (${it.detail.ifEmpty { it.status }})"
                        }
                    }
                }
            }
            override fun onFailure(call: Call<LiveScoresResponse>, t: Throwable) {}
        })
    }

    private var optionsDialog: AlertDialog? = null
    
    private fun toggleFavorite() {
        if (currentTeam.isEmpty()) return
        if (favoriteTeams.contains(currentTeam)) {
            favoriteTeams.remove(currentTeam)
            Toast.makeText(this, "$currentTeam removed", Toast.LENGTH_SHORT).show()
        } else {
            favoriteTeams.add(currentTeam)
            Toast.makeText(this, "$currentTeam added", Toast.LENGTH_SHORT).show()
        }
        sharedPrefs.edit().putStringSet("favorite_teams", favoriteTeams).apply()
    }

    private fun showPredictionLog() {
        resultText.text = "Loading prediction log..."
        apiService.getPredictionLog().enqueue(object : Callback<PredictionLogResponse> {
            override fun onResponse(call: Call<PredictionLogResponse>, response: Response<PredictionLogResponse>) {
                val entries = response.body()?.log ?: emptyList()
                val total = response.body()?.total ?: 0
                if (entries.isEmpty()) {
                    resultText.text = "No predictions logged yet\nTotal: 0\n\nEvery time you tap a game in PREDICT mode, it gets logged here."
                    return
                }
                val sb = StringBuilder()
                sb.append("PREDICTION LOG (" + total + " total)\n")
                sb.append("==============================\n\n")
                for (e in entries) {
                    val resultIcon = when (e.correct) {
                        true -> "✓ CORRECT"
                        false -> "✗ WRONG"
                        else -> "⏳ PENDING"
                    }
                    sb.append(e.date ?: "")
                    sb.append("\n")
                    sb.append(e.team1 ?: "?" + " vs " + (e.team2 ?: "?"))
                    sb.append("\n")
                    sb.append("Pick: " + (e.predicted_winner ?: "?") + " (" + (e.predicted_score ?: "?") + ")\n")
                    sb.append("Confidence: " + (e.confidence?.toString() ?: "?") + "%\n")
                    if (e.actual_winner != null) {
                        sb.append("Actual: " + e.actual_winner + " " + (e.actual_score ?: "") + "\n")
                    }
                    sb.append(resultIcon + "\n\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<PredictionLogResponse>, t: Throwable) {
                resultText.text = "Failed to load log: " + t.message
            }
        })
    }

    private fun showAccuracy() {
        apiService.getAccuracy().enqueue(object : Callback<AccuracyResponse> {
            override fun onResponse(call: Call<AccuracyResponse>, response: Response<AccuracyResponse>) {
                if (response.isSuccessful) {
                    val a = response.body()
                    resultText.text = "PREDICTION ACCURACY\n==============================\n\nTotal: ${a?.total_predictions ?: 0}\nCorrect: ${a?.correct ?: 0}\nAccuracy: ${a?.accuracy ?: 0.0}%"
                } else {
                    resultText.text = "No predictions recorded yet"
                }
            }
            override fun onFailure(call: Call<AccuracyResponse>, t: Throwable) {
                resultText.text = "Could not load accuracy"
            }
        })
    }

    private fun showLivePredictions() {
        resultText.text = "Loading live predictions..."
        apiService.getLivePredictions().enqueue(object : Callback<LivePredictionResponse> {
            override fun onResponse(call: Call<LivePredictionResponse>, response: Response<LivePredictionResponse>) {
                val games = response.body()?.live ?: emptyList()
                if (games.isEmpty()) {
                    resultText.text = "No live games right now"
                    return
                }
                val sb = StringBuilder()
                sb.append("LIVE GAME PREDICTIONS\n==============================\n\n")
                for (g in games) {
                    sb.append("${g.away} ${g.away_score} - ${g.home_score} ${g.home}\n")
                    sb.append("  ${g.clock}\n")
                    sb.append("  Live win prob: ${g.home} ${g.home_win_probability}% / ${g.away} ${g.away_win_probability}%\n\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<LivePredictionResponse>, t: Throwable) {
                resultText.text = "Failed to load live predictions"
            }
        })
    }

    private fun showOdds() {
        resultText.text = "Loading odds..."
        apiService.getOdds().enqueue(object : Callback<OddsResponse> {
            override fun onResponse(call: Call<OddsResponse>, response: Response<OddsResponse>) {
                val odds = response.body()?.odds ?: emptyList()
                if (odds.isEmpty()) {
                    resultText.text = "No odds available"
                    return
                }
                val sb = StringBuilder()
                sb.append("BETTING ODDS\n==============================\n\n")
                for (o in odds) {
                    sb.append("${o.game}\n")
                    sb.append("  Spread: ${o.spread}\n")
                    sb.append("  O/U: ${o.over_under}\n")
                    sb.append("  Home ML: ${o.home_ml} | Away ML: ${o.away_ml}\n")
                    sb.append("  Source: ${o.provider}\n\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<OddsResponse>, t: Throwable) {
                resultText.text = "Failed to load odds"
            }
        })
    }

    private fun showPlayerProps() {
        if (currentPlayer.isEmpty() || currentTeam.isEmpty()) {
            resultText.text = "Select a player first (PLAYER mode)"
            return
        }
        resultText.text = "Loading props for $currentPlayer..."
        apiService.getPlayerProps(currentPlayer, currentTeam).enqueue(object : Callback<PlayerPropsResponse> {
            override fun onResponse(call: Call<PlayerPropsResponse>, response: Response<PlayerPropsResponse>) {
                val p = response.body()
                val sb = StringBuilder()
                sb.append("PLAYER PROPS: ${p?.player ?: currentPlayer}\n==============================\n\n")
                if (p?.props.isNullOrEmpty()) {
                    sb.append("No prop data available")
                } else {
                    for (prop in (p?.props ?: emptyList())) {
                        sb.append("${prop.stat}: ${prop.line}\n")
                        sb.append("  Recommendation: ${prop.recommendation}\n\n")
                    }
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<PlayerPropsResponse>, t: Throwable) {
                resultText.text = "Failed to load props"
            }
        })
    }

    private fun showServerIpDialog() {
        val input = EditText(this)
        input.setText(serverIp)
        AlertDialog.Builder(this)
            .setTitle("Set Server IP")
            .setMessage("Current: $serverIp:5000")
            .setView(input)
            .setPositiveButton("Save & Test") { _, _ ->
                val newIp = input.text.toString().trim()
                if (newIp.isNotBlank()) {
                    serverIp = newIp
                    sharedPrefs.edit().putString("server_ip", newIp).apply()
                    setupRetrofit()
                    testConnection()
                }
            }.setNegativeButton("Cancel", null).show()
    }

    private fun setStatsMode() {
        currentMode = "STATS"
        gamesContainer.visibility = View.VISIBLE
        swipeRefresh.visibility = View.VISIBLE
        resultText.visibility = View.VISIBLE
        spinnersRow.visibility = View.GONE
        resultText.text = "Select a team"
        val numberedTeams = allNFLTeams.mapIndexed { index, team -> "${index + 1}. $team" }
        val teamAdapter = ArrayAdapter(this, R.layout.spinner_item, numberedTeams)
        teamAdapter.setDropDownViewResource(R.layout.spinner_dropdown_item)
        teamSpinner.adapter = teamAdapter
        teamSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                currentTeam = allNFLTeams[position]; getTeamStats()
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    private fun setPlayerMode() {
        currentMode = "PLAYER"
        gamesContainer.visibility = View.GONE
        swipeRefresh.visibility = View.VISIBLE
        resultText.visibility = View.VISIBLE
        spinnersRow.visibility = View.VISIBLE
        playerSpinner.visibility = View.VISIBLE
        val numberedTeams = allNFLTeams.mapIndexed { index, team -> "${index + 1}. $team" }
        val teamAdapter = ArrayAdapter(this, R.layout.spinner_item, numberedTeams)
        teamAdapter.setDropDownViewResource(R.layout.spinner_dropdown_item)
        teamSpinner.adapter = teamAdapter
        teamSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                currentTeam = allNFLTeams[position]; loadRosterForTeam(currentTeam)
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    private fun setPredictMode() {
        currentMode = "PREDICT"
        spinnersRow.visibility = View.GONE
        swipeRefresh.visibility = View.GONE
        gamesContainer.visibility = View.VISIBLE
        gamesList.removeAllViews()
        
        val loadingText = TextView(this)
        loadingText.text = "Loading this week..."
        loadingText.setTextColor(0xFF8899aa.toInt())
        loadingText.textSize = 14f
        loadingText.setPadding(24, 24, 24, 24)
        gamesList.addView(loadingText)

        apiService.getUpcomingGames().enqueue(object : Callback<UpcomingGamesResponse> {
            override fun onResponse(call: Call<UpcomingGamesResponse>, response: Response<UpcomingGamesResponse>) {
                val games = response.body()?.games ?: emptyList()
                val week = response.body()?.week ?: 1
                gamesList.removeAllViews()
                if (games.isEmpty()) {
                    val tv = TextView(this@MainActivity)
                    tv.text = "No games this week"
                    tv.setTextColor(0xFF8899aa.toInt())
                    tv.setPadding(24, 24, 24, 24)
                    gamesList.addView(tv)
                    return
                }
                
                // Week header
                val weekHeader = TextView(this@MainActivity)
                weekHeader.text = "WEEK $week"
                weekHeader.setTextColor(0xFFFFFFFF.toInt())
                weekHeader.textSize = 22f
                weekHeader.setTypeface(null, android.graphics.Typeface.BOLD)
                weekHeader.setPadding(16, 16, 16, 16)
                gamesList.addView(weekHeader)
                
                var lastDay = ""
                for (g in games) {
                    // Determine day group from date
                    var dayLabel = ""
                    try {
                        val datePart = (g.date ?: "").substring(0, 10)
                        val sdf = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
                        val date = sdf.parse(datePart)
                        val dayOfWeek = java.text.SimpleDateFormat("EEEE, MMM d", java.util.Locale.US)
                        dayLabel = dayOfWeek.format(date)
                    } catch (e: Exception) {
                        dayLabel = ""
                    }
                    
                    // Add day header if it changed
                    if (dayLabel.isNotEmpty() && dayLabel != lastDay) {
                        val dayHeader = TextView(this@MainActivity)
                        dayHeader.text = dayLabel
                        dayHeader.setTextColor(0xFF4a9eff.toInt())
                        dayHeader.textSize = 14f
                        dayHeader.setTypeface(null, android.graphics.Typeface.BOLD)
                        dayHeader.setPadding(16, 24, 16, 8)
                        gamesList.addView(dayHeader)
                        lastDay = dayLabel
                    }
                    
                    // Create card
                    val card = LinearLayout(this@MainActivity)
                    card.orientation = LinearLayout.VERTICAL
                    val bg = android.graphics.drawable.GradientDrawable()
                    if (g.is_live == true) {
                        bg.setColor(0xFF1a2f4a.toInt())
                        bg.setStroke(3, 0xFFff4444.toInt())
                    } else if (g.completed == true) {
                        bg.setColor(0xFF141824.toInt())
                    } else {
                        bg.setColor(0xFF1e2740.toInt())
                    }
                    bg.cornerRadius = 12f
                    card.background = bg
                    card.setPadding(20, 16, 20, 16)
                    val cardLp = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT
                    )
                    cardLp.setMargins(12, 6, 12, 6)
                    card.layoutParams = cardLp
                    card.isClickable = true
                    
                    // Status row
                    val statusRow = TextView(this@MainActivity)
                    val statusColor = when (g.state_type) {
                        "LIVE" -> 0xFFff4444.toInt()
                        "FINAL" -> 0xFF8899aa.toInt()
                        else -> 0xFF4a9eff.toInt()
                    }
                    statusRow.text = g.status_text
                    statusRow.setTextColor(statusColor)
                    statusRow.textSize = 11f
                    statusRow.setTypeface(null, android.graphics.Typeface.BOLD)
                    card.addView(statusRow)
                    
                    // Away team row
                    val awayRow = TextView(this@MainActivity)
                    val awayColor = if (g.away_winner == true) 0xFF00ff88.toInt() else 0xFFdde4f0.toInt()
                    awayRow.text = "${g.away_full}    ${if (g.completed == true || g.is_live == true) g.away_score.toString() else ""}"
                    awayRow.setTextColor(awayColor)
                    awayRow.textSize = 17f
                    awayRow.setPadding(0, 8, 0, 0)
                    if (g.away_winner == true) awayRow.setTypeface(null, android.graphics.Typeface.BOLD)
                    card.addView(awayRow)
                    
                    // Home team row
                    val homeRow = TextView(this@MainActivity)
                    val homeColor = if (g.home_winner == true) 0xFF00ff88.toInt() else 0xFFdde4f0.toInt()
                    homeRow.text = "${g.home_full}    ${if (g.completed == true || g.is_live == true) g.home_score.toString() else ""}"
                    homeRow.setTextColor(homeColor)
                    homeRow.textSize = 17f
                    homeRow.setPadding(0, 4, 0, 0)
                    if (g.home_winner == true) homeRow.setTypeface(null, android.graphics.Typeface.BOLD)
                    card.addView(homeRow)
                    
                    card.setOnClickListener {
                        currentTeam = g.home_full
                        opponentTeam = g.away_full
                        gamesContainer.visibility = View.GONE
                        swipeRefresh.visibility = View.VISIBLE
                        resultText.visibility = View.VISIBLE
                        resultText.text = "Analyzing ${g.away_full} @ ${g.home_full}..."
                        fetchPrediction(g.home_full, g.away_full)
                        // Re-enable back button
                        findViewById<MaterialButton>(R.id.refreshAllButton).text = "← BACK"
                    }
                    gamesList.addView(card)
                }
            }
            override fun onFailure(call: Call<UpcomingGamesResponse>, t: Throwable) {
                gamesList.removeAllViews()
                val tv = TextView(this@MainActivity)
                tv.text = "Failed: ${t.message}"
                tv.setTextColor(0xFFff4444.toInt())
                tv.setPadding(24, 24, 24, 24)
                gamesList.addView(tv)
            }
        })
    }

    private fun loadRosterForTeam(teamName: String) {
        showLoading(true)
        apiService.getRoster(teamName).enqueue(object : Callback<RosterResponse> {
            override fun onResponse(call: Call<RosterResponse>, response: Response<RosterResponse>) {
                showLoading(false)
                if (response.isSuccessful) {
                    val players = response.body()?.players ?: emptyList()
                    if (players.isEmpty()) { resultText.text = "No players found"; return }
                    val playerNames = players.mapIndexed { index, player ->
                        "${index + 1}. ${player.name} (${player.position})${if (player.injured == true) " [INJ]" else ""}"
                    }
                    val adapter = ArrayAdapter(this@MainActivity, R.layout.spinner_item, playerNames)
                    adapter.setDropDownViewResource(R.layout.spinner_dropdown_item)
                    playerSpinner.adapter = adapter
                    playerSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                        override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                            if (position >= 0 && position < players.size) {
                                currentPlayer = players[position].name ?: ""; getPlayerStats()
                            }
                        }
                        override fun onNothingSelected(parent: AdapterView<*>?) {}
                    }
                    resultText.text = "${players.size} players loaded\nSelect a player"
                }
            }
            override fun onFailure(call: Call<RosterResponse>, t: Throwable) { showLoading(false) }
        })
    }

    private fun getTeamStats() {
        val team = currentTeam; if (team.isEmpty()) return
        showLoading(true)
        val manual = manualStats[team]
        if (manual != null && manual.isNotEmpty()) { showLoading(false); displayManualStats(team, manual); return }
        apiService.getTeamStats(team).enqueue(object : Callback<TeamStatsResponse> {
            override fun onResponse(call: Call<TeamStatsResponse>, response: Response<TeamStatsResponse>) {
                val stats = response.body()
                apiService.getWinLoss(team).enqueue(object : Callback<WinLossResponse> {
                    override fun onResponse(call: Call<WinLossResponse>, wlResponse: Response<WinLossResponse>) {
                        val wl = wlResponse.body()
                        apiService.getWeather(team).enqueue(object : Callback<WeatherResponse> {
                            override fun onResponse(call: Call<WeatherResponse>, weatherResponse: Response<WeatherResponse>) {
                                val weather = weatherResponse.body()
                                apiService.getInjuries(team).enqueue(object : Callback<InjuriesResponse> {
                                    override fun onResponse(call: Call<InjuriesResponse>, injResponse: Response<InjuriesResponse>) {
                                        val injuries = injResponse.body()
                                        apiService.getNews(team).enqueue(object : Callback<NewsResponse> {
                                            override fun onResponse(call: Call<NewsResponse>, newsResponse: Response<NewsResponse>) {
                                                showLoading(false)
                                                displayFullStats(team, stats, wl, weather, injuries, newsResponse.body())
                                            }
                                            override fun onFailure(call: Call<NewsResponse>, t: Throwable) { showLoading(false) }
                                        })
                                    }
                                    override fun onFailure(call: Call<InjuriesResponse>, t: Throwable) { showLoading(false) }
                                })
                            }
                            override fun onFailure(call: Call<WeatherResponse>, t: Throwable) { showLoading(false) }
                        })
                    }
                    override fun onFailure(call: Call<WinLossResponse>, t: Throwable) { showLoading(false) }
                })
            }
            override fun onFailure(call: Call<TeamStatsResponse>, t: Throwable) { showLoading(false) }
        })
    }

    private fun displayFullStats(team: String, stats: TeamStatsResponse?, wl: WinLossResponse?,
                                  weather: WeatherResponse?, injuries: InjuriesResponse?, news: NewsResponse?) {
        val sb = StringBuilder()
        sb.append("$team\n==============================\n\n[ TEAM STATS ]\n")
        if (stats != null && wl != null) {
            sb.append("Record: ${wl.regular_season_record ?: "N/A"}\n")
            sb.append("Win: ${String.format("%.1f", (wl.win_percentage ?: 0.0) * 100)}%\n")
            sb.append("PF: ${stats.points_for ?: 0}  PA: ${stats.points_against ?: 0}\n")
            sb.append("Streak: ${stats.streak ?: "N/A"}\n")
        }
        sb.append("\n[ WEATHER ]\n")
        if (weather != null) sb.append("${weather.temperature ?: "--"}F, ${weather.conditions ?: "N/A"}\n${weather.impact ?: ""}\n")
        sb.append("\n[ INJURIES ]\n")
        if (injuries?.injuries != null && injuries.injuries.isNotEmpty()) {
            val items = injuries.injuries
            for (i in 0 until minOf(items.size, 5)) {
                val item = items[i]
                sb.append("- ${item.player ?: "Unknown"} (${item.position ?: "N/A"}): ${item.status ?: "N/A"}\n")
            }
        } else sb.append("None reported\n")
        sb.append("\n[ NEWS ]\n")
        if (news?.news != null && news.news.isNotEmpty()) {
            val items = news.news
            for (i in 0 until minOf(items.size, 3)) {
                sb.append("${i+1}. ${items[i].headline ?: ""}\n")
            }
        } else sb.append("No recent news\n")
        resultText.text = sb.toString()
    }

    private fun displayManualStats(team: String, manual: MutableMap<String, String>) {
        resultText.text = "$team (MANUAL)\nRecord: ${manual["record"] ?: "N/A"}\nPF: ${manual["points_for"] ?: 0}  PA: ${manual["points_against"] ?: 0}"
    }

    private fun getPlayerStats() {
        if (currentPlayer.isEmpty()) return
        showLoading(true)
        apiService.getPlayerStats(currentPlayer, currentTeam).enqueue(object : Callback<PlayerStatsResponse> {
            override fun onResponse(call: Call<PlayerStatsResponse>, response: Response<PlayerStatsResponse>) {
                showLoading(false)
                if (response.isSuccessful) displayPlayerStats(response.body())
            }
            override fun onFailure(call: Call<PlayerStatsResponse>, t: Throwable) { showLoading(false) }
        })
    }

    private fun displayPlayerStats(p: PlayerStatsResponse?) {
        if (p == null) return
        val sb = StringBuilder()
        sb.append("${p.name}\n")
        sb.append("Position: ${p.position ?: "N/A"} | #${p.jersey ?: "N/A"}\n")
        sb.append("Team: ${p.team ?: currentTeam}\n")
        sb.append("Status: ${if (p.injured == true) "INJURED" else "Active"}\n")
        val s = p.stats
        if (s == null) {
            sb.append("\nNo season stats available")
            resultText.text = sb.toString()
            return
        }
        if (s.passing_yards != null) {
            sb.append("\n[ PASSING ]\n")
            sb.append("Yards: ${s.passing_yards}\n")
            if (s.passing_tds != null) sb.append("TDs: ${s.passing_tds}\n")
            if (s.completions != null && s.passing_attempts != null) sb.append("Comp: ${s.completions}/${s.passing_attempts}\n")
            if (s.interceptions != null) sb.append("INTs: ${s.interceptions}\n")
        }
        if (s.rushing_yards != null) {
            sb.append("\n[ RUSHING ]\n")
            sb.append("Yards: ${s.rushing_yards}\n")
            if (s.rushing_tds != null) sb.append("TDs: ${s.rushing_tds}\n")
        }
        if (s.receiving_yards != null) {
            sb.append("\n[ RECEIVING ]\n")
            sb.append("Yards: ${s.receiving_yards}\n")
            if (s.receiving_tds != null) sb.append("TDs: ${s.receiving_tds}\n")
            if (s.receptions != null) sb.append("Rec: ${s.receptions}\n")
        }
        resultText.text = sb.toString()
    }

    private fun fetchPrediction(team1: String, team2: String) {
        if (team1.isEmpty() || team2.isEmpty()) return
        showLoading(true)
        apiService.getMlPrediction(team1, team2).enqueue(object : Callback<MlPredictionResponse> {
            override fun onResponse(call: Call<MlPredictionResponse>, response: Response<MlPredictionResponse>) {
                showLoading(false)
                if (response.isSuccessful) {
                    val p = response.body()
                    val sb = StringBuilder()
                    sb.append("${team1} vs ${team2}\n")
                    sb.append("==============================\n\n")
                    sb.append("${p?.predicted_winner ?: "?"} WINS\n\n")
                    sb.append("Predicted Score: ${p?.predicted_score ?: "N/A"}\n")
                    sb.append("Spread: ${p?.predicted_spread ?: "N/A"}\n")
                    sb.append("Total: ${p?.predicted_total ?: "N/A"}\n\n")
                    sb.append("Blended Win Probability:\n")
                    sb.append("  ${team1}: ${p?.blended_home_probability ?: "?"}%\n")
                    sb.append("  ${team2}: ${100 - (p?.blended_home_probability ?: 50.0)}%\n\n")
                    sb.append("ML Model: ${p?.ml_home_probability ?: "?"}% home\n")
                    if (p?.market_home_prob != null) {
                        sb.append("Market: ${p.market_home_prob}% home\n")
                        sb.append("Edge: ${p.edge}%\n\n")
                    }
                    if (p?.market_spread != null) {
                        sb.append("SPORTSBOOK LINE\n")
                        sb.append("  Spread: ${p.market_spread}\n")
                        sb.append("  Total: ${p.market_total}\n\n")
                    }
                    sb.append("Confidence: ${p?.confidence}% (${p?.confidence_level})\n")
                    resultText.text = sb.toString()
                } else {
                    resultText.text = "ML prediction not available for this matchup"
                }
            }
            override fun onFailure(call: Call<MlPredictionResponse>, t: Throwable) {
                showLoading(false)
                resultText.text = "Error: ${t.message}"
            }
        })
    }

    private fun loadManualOverrides() {
        sharedPrefs.getStringSet("manual_overrides", emptySet())?.forEach { entry ->
            val parts = entry.split("|")
            if (parts.size == 3) manualStats.getOrPut(parts[0]) { mutableMapOf() }[parts[1]] = parts[2]
        }
    }

    private fun saveManualOverride(team: String, statName: String, value: String) {
        manualStats.getOrPut(team) { mutableMapOf() }[statName] = value
        sharedPrefs.edit().putStringSet("manual_overrides", manualStats.flatMap { (t, s) -> s.map { "$t|${it.key}|${it.value}" } }.toSet()).apply()
    }

    private fun showManualOverrideDialog() {
        val team = currentTeam
        AlertDialog.Builder(this).setTitle("Manual Override - $team")
            .setItems(arrayOf("Record", "Points For", "Points Against", "Reset")) { _, which ->
                when (which) {
                    0 -> showStatEditDialog(team, "record")
                    1 -> showStatEditDialog(team, "points_for")
                    2 -> showStatEditDialog(team, "points_against")
                    3 -> { manualStats.remove(team); getTeamStats() }
                }
            }.show()
    }

    private fun showStatEditDialog(team: String, statKey: String) {
        val input = EditText(this)
        input.setText(manualStats[team]?.get(statKey) ?: "")
        AlertDialog.Builder(this).setTitle("Edit $statKey").setView(input)
            .setPositiveButton("Save") { _, _ -> saveManualOverride(team, statKey, input.text.toString()); getTeamStats() }
            .setNegativeButton("Cancel", null).show()
    }

    private fun testConnection() {
        showLoading(true)
        apiService.testConnection().enqueue(object : Callback<TestResponse> {
            override fun onResponse(call: Call<TestResponse>, response: Response<TestResponse>) {
                showLoading(false)
                resultText.text = if (response.isSuccessful) "Server: $serverIp:5000\nConnected!" else "Server error"
            }
            override fun onFailure(call: Call<TestResponse>, t: Throwable) { showLoading(false); resultText.text = "Cannot reach $serverIp:5000" }
        })
    }

    private fun showHelp() {
        resultText.text = "HELP - $serverIp:5000\n\nSTATS: Team info\nPLAYER: Player stats\nPREDICT: Tap a game to predict\n\nLong press HELP for:\n- Change Server IP\n- Toggle Favorites\n- View Accuracy\n- Live Predictions\n- Betting Odds\n- Player Props\n- Manual Override"
    }

    private fun showLoading(show: Boolean) {
        loadingIndicator.visibility = if (show) View.VISIBLE else View.GONE
        if (!show) swipeRefresh.isRefreshing = false
    }
}
