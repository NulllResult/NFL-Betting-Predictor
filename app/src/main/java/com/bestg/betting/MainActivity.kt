@file:Suppress(
    "UnnecessarySafeCall",
    "RedundantElvisOperator",
    "NAME_SHADOWING",
    "DEPRECATION"
)

package com.bestg.betting

/**
 * MainActivity — Primary entry point of the NFL Betting Predictor Android app.
 *
 * Responsibilities:
 *  - STATS / PLAYER / PREDICT mode switching
 *  - HELP cycle (14 modes: help, accuracy, log, live, odds, props, preseason, h2h, week-chart, backtest, find-server, notifs, theme, server-ip)
 *  - Retrofit calls to the Flask backend
 *  - Renders predictions with probability bars, section dividers, and similar matchups
 *  - State snapshots to MainViewModel to survive rotation
 *
 * Data preservation:
 *  - prediction_history.json is written only by the server; never by the client
 *  - manual overrides are stored in SharedPreferences as JSON (legacy pipe format still readable)
 *  - watched predictions are stored in SharedPreferences
 */

import com.bestg.betting.models.*
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.widget.*
import android.widget.ImageView
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
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import androidx.core.content.ContextCompat
import com.google.gson.Gson

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

    private lateinit var viewModel: MainViewModel
    private var currentMode = "STATS"
    private var helpCycle = 0
    private var logFilter = "ALL"   // ALL | CORRECT | WRONG | PENDING
    private var latestScores: List<LiveScore> = emptyList()
    private var scorePage = 0
    private var scoreRotator: Runnable? = null
    private val watchedKeys = mutableSetOf<String>()
    private var currentTeam = ""
    private var currentPlayer = ""
    private var opponentTeam = ""
    private var serverIp = "10.0.0.60"
    private val inFlightCalls = mutableListOf<retrofit2.Call<*>>()

    private var allNFLTeams = listOf(
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

        viewModel = androidx.lifecycle.ViewModelProvider(this)[MainViewModel::class.java]
        sharedPrefs = getSharedPreferences("NFL_Betting_Prefs", Context.MODE_PRIVATE)

        // Apply saved theme preference
        val savedTheme = sharedPrefs.getString("theme_mode", "dark") ?: "dark"
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(
            if (savedTheme == "dark") androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES
            else androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO
        )
        loadManualOverrides()
        favoriteTeams.addAll(sharedPrefs.getStringSet("favorite_teams", emptySet()) ?: emptySet())
        watchedKeys.addAll(sharedPrefs.getStringSet("watched_predictions", emptySet()) ?: emptySet())
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
        setupRetrofit()
        fetchTeamsFromServer()
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
            helpCycle = (helpCycle + 1) % 14
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
                6 -> showPreseasonStats()
                7 -> showHeadToHead()
                8 -> showAccuracyByWeek()
                9 -> showBacktest()
                10 -> autoDetectServer()
                11 -> toggleNotifications()
                12 -> toggleTheme()
                13 -> showServerIpDialog()
            }
            updateHelpButtonLabel()
        }

        AppLog.i("onCreate complete")
        // Restore from ViewModel if we have prior state (e.g., after rotation)
        val vmTeam = viewModel.currentTeam.value ?: ""
        val vmPlayer = viewModel.currentPlayer.value ?: ""
        val vmOpp = viewModel.opponentTeam.value ?: ""
        val vmText = viewModel.lastPredictionText.value ?: ""

        if (vmTeam.isNotBlank()) currentTeam = vmTeam
        if (vmPlayer.isNotBlank()) currentPlayer = vmPlayer
        if (vmOpp.isNotBlank()) opponentTeam = vmOpp
        if (vmText.isNotBlank()) resultText.text = vmText

        setPredictMode()
        fetchLiveScores()
        startScoreUpdates()
        updateHelpButtonLabel()
        attachLogStarHandler()
    }

    override fun onResume() {
        super.onResume()
        startScoreUpdates()
        fetchLiveScores()
    }

    override fun onPause() {
        super.onPause()
        stopScoreUpdates()
        stopScoreRotation()
        // Snapshot current UI state to ViewModel — survives rotation
        viewModel.setMode(currentMode)
        viewModel.setCurrentTeam(currentTeam)
        viewModel.setCurrentPlayer(currentPlayer)
        viewModel.setOpponentTeam(opponentTeam)
        viewModel.setLogFilter(logFilter)
        viewModel.setServerIp(serverIp)
        viewModel.setLatestScores(latestScores)
        viewModel.setLastPredictionText(resultText.text.toString())
    }

    override fun onDestroy() {
        super.onDestroy()
        stopScoreUpdates()
        scoreHandler.removeCallbacksAndMessages(null)
    }

    private fun cancelAllInFlight() {
        synchronized(inFlightCalls) {
            for (call in inFlightCalls) {
                try { call.cancel() } catch (_: Throwable) {}
            }
            inFlightCalls.clear()
        }
    }

    private fun <T> retrofit2.Call<T>.tracked(): retrofit2.Call<T> {
        synchronized(inFlightCalls) { inFlightCalls.add(this) }
        return this
    }



    private val teamAbbrevMap = mapOf(
        "Buffalo Bills" to "buf", "Miami Dolphins" to "mia", "New England Patriots" to "ne", "New York Jets" to "nyj",
        "Baltimore Ravens" to "bal", "Cincinnati Bengals" to "cin", "Cleveland Browns" to "cle", "Pittsburgh Steelers" to "pit",
        "Houston Texans" to "hou", "Indianapolis Colts" to "ind", "Jacksonville Jaguars" to "jax", "Tennessee Titans" to "ten",
        "Denver Broncos" to "den", "Kansas City Chiefs" to "kc", "Las Vegas Raiders" to "lv", "Los Angeles Chargers" to "lac",
        "Dallas Cowboys" to "dal", "New York Giants" to "nyg", "Philadelphia Eagles" to "phi", "Washington Commanders" to "wsh",
        "Chicago Bears" to "chi", "Detroit Lions" to "det", "Green Bay Packers" to "gb", "Minnesota Vikings" to "min",
        "Atlanta Falcons" to "atl", "Carolina Panthers" to "car", "New Orleans Saints" to "no", "Tampa Bay Buccaneers" to "tb",
        "Arizona Cardinals" to "ari", "Los Angeles Rams" to "lar", "San Francisco 49ers" to "sf", "Seattle Seahawks" to "sea"
    )


    /**
     * Builds a horizontal row: [logo] Team Name    Score
     * Used in the PREDICT game cards.
     */
    private fun makeTeamRow(
        teamName: String,
        score: Int?,
        isWinner: Boolean
    ): LinearLayout {
        val row = LinearLayout(this)
        row.orientation = LinearLayout.HORIZONTAL
        row.gravity = android.view.Gravity.CENTER_VERTICAL
        row.setPadding(0, 6, 0, 0)

        // Logo
        val logo = ImageView(this)
        val logoSizePx = (28 * resources.displayMetrics.density).toInt()
        val lp = LinearLayout.LayoutParams(logoSizePx, logoSizePx)
        lp.setMargins(0, 0, 12, 0)
        logo.layoutParams = lp
        logo.setImageResource(getTeamLogo(teamName))
        logo.scaleType = ImageView.ScaleType.FIT_CENTER
        row.addView(logo)

        // Team name
        val nameTv = TextView(this)
        nameTv.text = teamName
        nameTv.textSize = 17f
        nameTv.setTextColor(
            if (isWinner) ContextCompat.getColor(this, R.color.text_winner)
            else ContextCompat.getColor(this, R.color.text_primary)
        )
        if (isWinner) nameTv.setTypeface(null, android.graphics.Typeface.BOLD)
        val nameLp = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        nameTv.layoutParams = nameLp
        row.addView(nameTv)

        // Score
        if (score != null) {
            val scoreTv = TextView(this)
            scoreTv.text = score.toString()
            scoreTv.textSize = 18f
            scoreTv.setTypeface(android.graphics.Typeface.MONOSPACE, android.graphics.Typeface.BOLD)
            scoreTv.setTextColor(
                if (isWinner) ContextCompat.getColor(this, R.color.text_winner)
                else ContextCompat.getColor(this, R.color.text_primary)
            )
            row.addView(scoreTv)
        }

        return row
    }


    private fun probBar(pct: Double): String {
        val filled = (pct / 5).toInt().coerceIn(0, 20)
        return "\u2588".repeat(filled) + "\u2591".repeat(20 - filled)
    }

    private fun sectionHeader(title: String): String {
        return "\u2501".repeat(30) + "\n" + " " + title + "\n" + "\u2501".repeat(30) + "\n"
    }

    private fun confidenceLevel(pct: Double?): Triple<String, Int, Int> {
        val p = pct ?: 0.0
        return when {
            p >= 65.0 -> Triple("HIGH", R.color.confidence_high, 0)
            p >= 55.0 -> Triple("MEDIUM", R.color.confidence_medium, 0)
            else -> Triple("LOW", R.color.confidence_low, 0)
        }
    }

    private fun teamRowInline(teamName: String): android.text.SpannableString {
        // We can't embed drawables in a TextView without ImageSpan, but we
        // can render inline "[logo] TeamName" in the text view via a small
        // bullet character followed by the name. Actual logos go in game cards.
        // This is called only in fetchPrediction to keep things compact.
        return android.text.SpannableString(teamName)
    }

    private fun getTeamLogo(teamName: String): Int {
        val abbrev = teamAbbrevMap[teamName] ?: "pit"
        val resId = resources.getIdentifier("logo_$abbrev", "drawable", packageName)
        return if (resId != 0) resId else R.drawable.logo_pit
    }

    private fun fetchTeamsFromServer() {
        apiService.getTeams().enqueue(object : Callback<com.bestg.betting.models.TeamsResponse> {
            override fun onResponse(call: Call<com.bestg.betting.models.TeamsResponse>, response: Response<com.bestg.betting.models.TeamsResponse>) {
                val teams = response.body()?.teams
                if (!teams.isNullOrEmpty()) {
                    allNFLTeams = teams
                }
            }
            override fun onFailure(call: Call<com.bestg.betting.models.TeamsResponse>, t: Throwable) {
                // Silent — hardcoded list stays as fallback
            }
        })
    }

    private fun setupRetrofit() {
        cancelAllInFlight()
        val client = okhttp3.OkHttpClient.Builder()
            .connectTimeout(5, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
            .writeTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
            .build()
        val retrofit = Retrofit.Builder()
            .baseUrl("http://$serverIp:5000/")
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
        apiService = retrofit.create(ApiService::class.java)
        AppLog.i("Retrofit set up for $serverIp:5000")
    }

    private var scoreUpdateRunnable: Runnable? = null

    private fun startScoreUpdates() {
        stopScoreUpdates()
        val runnable = object : Runnable {
            override fun run() {
                fetchLiveScores()
                scoreHandler.postDelayed(this, 30000)
            }
        }
        scoreUpdateRunnable = runnable
        scoreHandler.postDelayed(runnable, 30000)
    }

    private fun stopScoreUpdates() {
        scoreUpdateRunnable?.let { scoreHandler.removeCallbacks(it) }
        scoreUpdateRunnable = null
    }

    private fun fetchLiveScores() {
        apiService.getLiveScores().enqueue(object : Callback<LiveScoresResponse> {
            override fun onResponse(call: Call<LiveScoresResponse>, response: Response<LiveScoresResponse>) {
                if (response.isSuccessful) {
                    val scores = response.body()?.scores ?: emptyList()
                    latestScores = scores
                    if (scores.isEmpty()) {
                        scoreBanner.text = "No live games"
                    } else {
                        renderScorePage()
                        startScoreRotation(scores.size)
                    }
                }
            }
            override fun onFailure(call: Call<LiveScoresResponse>, t: Throwable) {
                AppLog.w("live_scores failed: ${t.message}")
            }
        })
    }

    private fun renderScorePage() {
        val scores = latestScores
        if (scores.isEmpty()) {
            scoreBanner.text = "No live games"
            return
        }
        // Show 2 games at a time, separated by " | "
        val perPage = 2
        val totalPages = (scores.size + perPage - 1) / perPage
        val page = scorePage % totalPages
        val start = page * perPage
        val end = minOf(start + perPage, scores.size)
        val slice = scores.subList(start, end)
        scoreBanner.text = slice.joinToString("  |  ") {
            "${it.away} ${it.away_score}-${it.home_score} ${it.home} (${it.detail.ifEmpty { it.status }})"
        }
    }

    private fun startScoreRotation(totalGames: Int) {
        // Stop any existing rotation
        scoreRotator?.let { scoreHandler.removeCallbacks(it) }
        if (totalGames <= 2) return   // no need to rotate if only 1 page

        val runnable = object : Runnable {
            override fun run() {
                scorePage = (scorePage + 1) % ((latestScores.size + 1) / 2)
                renderScorePage()
                scoreHandler.postDelayed(this, 6000)
            }
        }
        scoreRotator = runnable
        scoreHandler.postDelayed(runnable, 6000)
    }

    private fun stopScoreRotation() {
        scoreRotator?.let { scoreHandler.removeCallbacks(it) }
        scoreRotator = null
    }

    private var optionsDialog: AlertDialog? = null
    

    private fun toggleWatched(key: String) {
        if (watchedKeys.contains(key)) {
            watchedKeys.remove(key)
            Toast.makeText(this, "Removed from watchlist", Toast.LENGTH_SHORT).show()
        } else {
            watchedKeys.add(key)
            Toast.makeText(this, "Added to watchlist", Toast.LENGTH_SHORT).show()
        }
        sharedPrefs.edit().putStringSet("watched_predictions", watchedKeys).apply()
    }

    private fun isWatched(key: String): Boolean = watchedKeys.contains(key)

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
        showLoading(true)
        resultText.text = "Loading prediction log..."
        apiService.getPredictionLog().enqueue(object : Callback<PredictionLogResponse> {
            override fun onResponse(call: Call<PredictionLogResponse>, response: Response<PredictionLogResponse>) {
                showLoading(false)
                val allEntries = response.body()?.log ?: emptyList()
                lastLogEntries = allEntries
                val total = response.body()?.total ?: 0

                if (allEntries.isEmpty()) {
                    resultText.text = "No predictions logged yet\nTotal: 0\n\nEvery time you tap a game in PREDICT mode, it gets logged here."
                    return
                }

                val correctCount = allEntries.count { it.correct == true }
                val wrongCount = allEntries.count { it.correct == false }
                val pendingCount = allEntries.count { it.correct == null }

                // Apply filter (display-only, data is untouched)
                val entries = when (logFilter) {
                    "CORRECT" -> allEntries.filter { it.correct == true }
                    "WRONG"   -> allEntries.filter { it.correct == false }
                    "PENDING" -> allEntries.filter { it.correct == null }
                    "STARRED" -> allEntries.filter {
                        val k = "${it.date}|${it.team1}|${it.team2}"
                        isWatched(k)
                    }
                    else      -> allEntries
                }

                val sb = StringBuilder()
                sb.append("PREDICTION LOG\n")
                sb.append("==============================\n")
                sb.append("Total: " + total + "  (${allEntries.size} loaded)\n")
                sb.append("✓ $correctCount  ✗ $wrongCount  ⏳ $pendingCount\n")
                sb.append("Filter: [$logFilter]\n")
                sb.append("==============================\n\n")

                if (entries.isEmpty()) {
                    sb.append("No entries match filter '$logFilter'\n")
                } else {
                    for (e in entries) {
                        val resultIcon = when (e.correct) {
                            true -> "\u2713 CORRECT"
                            false -> "\u2717 WRONG"
                            else -> "\u23F3 PENDING"
                        }
                        val key = "${e.date}|${e.team1}|${e.team2}"
                        val star = if (isWatched(key)) "\u2605 " else ""
                        sb.append(star + (e.date ?: ""))
                        sb.append("\n")
                        sb.append((e.team1 ?: "?") + " vs " + (e.team2 ?: "?"))
                        sb.append("\n")
                        sb.append("Pick: " + (e.predicted_winner ?: "?") + " (" + (e.predicted_score ?: "?") + ")\n")
                        sb.append("Confidence: " + (e.confidence?.toString() ?: "?") + "%\n")
                        if (e.actual_winner != null) {
                            sb.append("Actual: " + e.actual_winner + " " + (e.actual_score ?: "") + "\n")
                        }
                        sb.append(resultIcon + "\n\n")
                    }
                }

                resultText.text = sb.toString()
                showLogFilterDialog()
            }
            override fun onFailure(call: Call<PredictionLogResponse>, t: Throwable) {
                showLoading(false)
                AppLog.e("prediction_log failed", t)
                resultText.text = "Failed to load log: " + t.message
                Toast.makeText(this@MainActivity, "Log failed: ${t.message}", Toast.LENGTH_SHORT).show()
            }
        })
    }


    private var lastLogEntries: List<PredictionLogEntry> = emptyList()

    private fun attachLogStarHandler() {
        resultText.setOnLongClickListener {
            if (lastLogEntries.isEmpty()) return@setOnLongClickListener false
            val top = lastLogEntries.take(20)
            val labels = top.map { e ->
                val k = "${e.date}|${e.team1}|${e.team2}"
                val star = if (isWatched(k)) "\u2605 " else "\u2606 "
                "$star${e.date ?: ""}  ${e.team1 ?: "?"} vs ${e.team2 ?: "?"}"
            }.toTypedArray()
            AlertDialog.Builder(this)
                .setTitle("Tap to star / unstar")
                .setItems(labels) { _, which ->
                    val e = top[which]
                    val k = "${e.date}|${e.team1}|${e.team2}"
                    toggleWatched(k)
                    // Refresh view after toggle
                    reloadLogQuiet()
                }
                .setNegativeButton("Close", null)
                .show()
            true
        }
    }

    private fun showLogFilterDialog() {
        AlertDialog.Builder(this)
            .setTitle("Filter: $logFilter")
            .setItems(arrayOf("ALL", "CORRECT", "WRONG", "PENDING", "STARRED")) { _, which ->
                logFilter = arrayOf("ALL", "CORRECT", "WRONG", "PENDING", "STARRED")[which]
                // Re-render, but don't chain dialogs forever
                if (currentMode == "STATS" || currentMode == "PREDICT") {
                    // Fallback: silently reload without re-showing dialog
                    reloadLogQuiet()
                } else {
                    reloadLogQuiet()
                }
            }
            .setNegativeButton("Close", null)
            .show()
    }

    private fun reloadLogQuiet() {
        apiService.getPredictionLog().enqueue(object : Callback<PredictionLogResponse> {
            override fun onResponse(call: Call<PredictionLogResponse>, response: Response<PredictionLogResponse>) {
                val allEntries = response.body()?.log ?: emptyList()
                lastLogEntries = allEntries
                val total = response.body()?.total ?: 0
                if (allEntries.isEmpty()) return

                val correctCount = allEntries.count { it.correct == true }
                val wrongCount = allEntries.count { it.correct == false }
                val pendingCount = allEntries.count { it.correct == null }

                val entries = when (logFilter) {
                    "CORRECT" -> allEntries.filter { it.correct == true }
                    "WRONG"   -> allEntries.filter { it.correct == false }
                    "PENDING" -> allEntries.filter { it.correct == null }
                    else      -> allEntries
                }

                val sb = StringBuilder()
                sb.append("PREDICTION LOG\n")
                sb.append("==============================\n")
                sb.append("Total: " + total + "  (${allEntries.size} loaded)\n")
                sb.append("\u2713 $correctCount  \u2717 $wrongCount  \u23F3 $pendingCount\n")
                sb.append("Filter: [$logFilter]\n")
                sb.append("==============================\n\n")
                if (entries.isEmpty()) {
                    sb.append("No entries match filter '$logFilter'\n")
                } else {
                    for (e in entries) {
                        val resultIcon = when (e.correct) {
                            true -> "\u2713 CORRECT"
                            false -> "\u2717 WRONG"
                            else -> "\u23F3 PENDING"
                        }
                        val key = "${e.date}|${e.team1}|${e.team2}"
                        val star = if (isWatched(key)) "\u2605 " else ""
                        sb.append(star + (e.date ?: ""))
                        sb.append("\n")
                        sb.append((e.team1 ?: "?") + " vs " + (e.team2 ?: "?"))
                        sb.append("\n")
                        sb.append("Pick: " + (e.predicted_winner ?: "?") + " (" + (e.predicted_score ?: "?") + ")\n")
                        sb.append("Confidence: " + (e.confidence?.toString() ?: "?") + "%\n")
                        if (e.actual_winner != null) {
                            sb.append("Actual: " + e.actual_winner + " " + (e.actual_score ?: "") + "\n")
                        }
                        sb.append(resultIcon + "\n\n")
                    }
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<PredictionLogResponse>, t: Throwable) {}
        })
    }

    private fun showAccuracy() {
        showLoading(true)
        resultText.text = "Loading accuracy..."
        apiService.getAccuracy().enqueue(object : Callback<AccuracyResponse> {
            override fun onResponse(call: Call<AccuracyResponse>, response: Response<AccuracyResponse>) {
                showLoading(false)
                if (response.isSuccessful) {
                    val a = response.body()
                    resultText.text = "PREDICTION ACCURACY\n==============================\n\nTotal: ${a?.total_predictions ?: 0}\nCorrect: ${a?.correct ?: 0}\nAccuracy: ${a?.accuracy ?: 0.0}%"
                } else {
                    resultText.text = "No predictions recorded yet"
                }
            }
            override fun onFailure(call: Call<AccuracyResponse>, t: Throwable) {
                showLoading(false)
                AppLog.e("accuracy failed", t)
                resultText.text = "Could not load accuracy"
                Toast.makeText(this@MainActivity, "Accuracy failed", Toast.LENGTH_SHORT).show()
            }
        })
    }

    private fun showLivePredictions() {
        showLoading(true)
        resultText.text = "Loading live predictions..."
        apiService.getLivePredictions().enqueue(object : Callback<LivePredictionResponse> {
            override fun onResponse(call: Call<LivePredictionResponse>, response: Response<LivePredictionResponse>) {
                showLoading(false)
                val games = response.body()?.live ?: emptyList()
                if (games.isEmpty()) {
                    resultText.text = "No live games right now"
                    return
                }
                val sb = StringBuilder()
                sb.append("LIVE GAME PREDICTIONS\n")
                sb.append("==============================\n")
                sb.append("${games.size} game(s) in progress\n\n")

                for (g in games) {
                    val scoreDiff = g.home_score - g.away_score
                    val leader = when {
                        scoreDiff > 0 -> g.home
                        scoreDiff < 0 -> g.away
                        else -> null
                    }

                    sb.append("${g.away}  ${g.away_score}  @  ${g.home_score}  ${g.home}\n")

                    if (leader != null) {
                        sb.append("  \u25B6 $leader leads by ${Math.abs(scoreDiff)}\n")
                    } else {
                        sb.append("  \u25B6 Tied game\n")
                    }

                    sb.append("  Clock: ${g.clock}\n")

                    // Win probability bar (home)
                    val hp = g.home_win_probability
                    val ap = g.away_win_probability
                    val homeBlocks = (hp / 5).toInt().coerceIn(0, 20)
                    val probBar = "\u2588".repeat(homeBlocks) + "\u2591".repeat(20 - homeBlocks)
                    sb.append("  Home win: $probBar ${String.format("%.1f", hp)}%\n")
                    sb.append("  Away win: ${String.format("%.1f", ap)}%\n")

                    // Predicted final score if server provided it
                    if (g.predicted_final_home != null && g.predicted_final_away != null) {
                        sb.append("  Projected final: ${g.away} ${g.predicted_final_away} @ ${g.predicted_final_home} ${g.home}\n")
                    }

                    // Live spread if provided
                    if (g.home_spread != null) {
                        val sp = g.home_spread
                        val spText = if (sp > 0) "+${sp}" else "$sp"
                        sb.append("  Live spread: ${g.home} $spText\n")
                    }

                    // Momentum if provided
                    if (!g.momentum.isNullOrBlank()) {
                        sb.append("  Momentum: ${g.momentum}\n")
                    }

                    // Update count
                    if (g.period != null) {
                        sb.append("  Period: Q${g.period}\n")
                    }

                    sb.append("\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<LivePredictionResponse>, t: Throwable) {
                showLoading(false)
                AppLog.e("live_prediction failed", t)
                resultText.text = "Failed to load live predictions"
                Toast.makeText(this@MainActivity, "Live predictions failed", Toast.LENGTH_SHORT).show()
            }
        })
    }

    private fun showOdds() {
        showLoading(true)
        resultText.text = "Loading odds..."
        apiService.getOdds().enqueue(object : Callback<OddsResponse> {
            override fun onResponse(call: Call<OddsResponse>, response: Response<OddsResponse>) {
                showLoading(false)
                val odds = response.body()?.odds ?: emptyList()
                if (odds.isEmpty()) {
                    resultText.text = "No odds available"
                    return
                }
                val sb = StringBuilder()
                sb.append("BETTING ODDS\n")
                sb.append("==============================\n")
                sb.append("${odds.size} game(s) with lines\n\n")

                // Helper: convert American ML to implied probability
                fun impliedProb(ml: Any?): Double? {
                    val m = when (ml) {
                        is Number -> ml.toDouble()
                        is String -> ml.replace("+", "").toDoubleOrNull() ?: return null
                        else -> return null
                    }
                    return if (m > 0) 100.0 / (m + 100.0) * 100.0
                    else (-m) / ((-m) + 100.0) * 100.0
                }

                for (o in odds) {
                    sb.append("\u25B6 ${o.game}\n")
                    sb.append("  Source: ${o.provider}\n")

                    // Spread line
                    val spreadStr = o.spread?.toString() ?: "N/A"
                    sb.append("  Spread: $spreadStr\n")

                    // Total
                    val totalStr = o.over_under?.toString() ?: "N/A"
                    sb.append("  Total:  $totalStr\n")

                    // Moneylines + implied probabilities
                    val homeMl = o.home_ml?.toString() ?: "N/A"
                    val awayMl = o.away_ml?.toString() ?: "N/A"
                    sb.append("  Home ML: $homeMl\n")
                    sb.append("  Away ML: $awayMl\n")

                    val hp = impliedProb(o.home_ml)
                    val ap = impliedProb(o.away_ml)
                    if (hp != null && ap != null) {
                        val vig = hp + ap
                        sb.append("  Implied: home ${String.format("%.1f", hp)}% / away ${String.format("%.1f", ap)}%\n")
                        sb.append("  Vig: ${String.format("%.1f", vig - 100.0)}%\n")

                        // Value badge: if a side is under 45% implied, flag as longshot value
                        when {
                            hp < 40.0 -> sb.append("  \u26A0 Home is a +value longshot\n")
                            ap < 40.0 -> sb.append("  \u26A0 Away is a +value longshot\n")
                            hp > 65.0 -> sb.append("  \u26A0 Home heavy favorite\n")
                            ap > 65.0 -> sb.append("  \u26A0 Away heavy favorite\n")
                            else -> sb.append("  \u2713 Balanced line\n")
                        }
                    }

                    sb.append("\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<OddsResponse>, t: Throwable) {
                showLoading(false)
                AppLog.e("odds failed", t)
                resultText.text = "Failed to load odds"
                Toast.makeText(this@MainActivity, "Odds failed", Toast.LENGTH_SHORT).show()
            }
        })
    }

    private fun showPlayerProps() {
        if (currentPlayer.isEmpty() || currentTeam.isEmpty()) {
            resultText.text = "Select a player first (PLAYER mode)"
            return
        }
        showLoading(true)
        resultText.text = "Loading props for $currentPlayer..."
        apiService.getPlayerProps(currentPlayer, currentTeam).enqueue(object : Callback<PlayerPropsResponse> {
            override fun onResponse(call: Call<PlayerPropsResponse>, response: Response<PlayerPropsResponse>) {
                showLoading(false)
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
                showLoading(false)
                resultText.text = "Failed to load props"
                Toast.makeText(this@MainActivity, "Props failed", Toast.LENGTH_SHORT).show()
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
                    cancelAllInFlight()
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

        // Pull-to-refresh on the games list
        swipeRefresh.setOnRefreshListener {
            swipeRefresh.isRefreshing = false
            setPredictMode()
        }
        
        val loadingText = TextView(this)
        loadingText.text = "Loading this week..."
        loadingText.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_secondary))
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
                    tv.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_secondary))
                    tv.setPadding(24, 24, 24, 24)
                    gamesList.addView(tv)
                    return
                }
                
                // Week header
                val weekHeader = TextView(this@MainActivity)
                weekHeader.text = "WEEK $week"
                weekHeader.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_white))
                weekHeader.textSize = 22f
                weekHeader.setTypeface(null, android.graphics.Typeface.BOLD)
                weekHeader.setPadding(16, 16, 16, 16)
                gamesList.addView(weekHeader)
                
                var lastDay = ""
                for (g in games) {
                    // Determine day group from date
                    val dayLabel: String = try {
                        val datePart = (g.date ?: "").substring(0, 10)
                        val sdf = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
                        val date = sdf.parse(datePart)
                        val dayOfWeek = java.text.SimpleDateFormat("EEEE, MMM d", java.util.Locale.US)
                        if (date != null) dayOfWeek.format(date) else ""
                    } catch (e: Exception) {
                        ""
                    }
                    
                    // Add day header if it changed
                    if (dayLabel.isNotEmpty() && dayLabel != lastDay) {
                        val dayHeader = TextView(this@MainActivity)
                        dayHeader.text = dayLabel
                        dayHeader.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.day_header))
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
                        bg.setColor(ContextCompat.getColor(this@MainActivity, R.color.card_live_bg))
                        bg.setStroke(3, ContextCompat.getColor(this@MainActivity, R.color.card_live_stroke))
                    } else if (g.completed == true) {
                        bg.setColor(ContextCompat.getColor(this@MainActivity, R.color.card_completed_bg))
                    } else {
                        bg.setColor(ContextCompat.getColor(this@MainActivity, R.color.card_default_bg))
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
                        "LIVE" -> ContextCompat.getColor(this@MainActivity, R.color.status_live)
                        "FINAL" -> ContextCompat.getColor(this@MainActivity, R.color.status_final)
                        else -> ContextCompat.getColor(this@MainActivity, R.color.status_upcoming)
                    }
                    statusRow.text = g.status_text
                    statusRow.setTextColor(statusColor)
                    statusRow.textSize = 11f
                    statusRow.setTypeface(null, android.graphics.Typeface.BOLD)
                    card.addView(statusRow)
                    
                    // Away team row (with logo)
                    val awayRow = makeTeamRow(
                        teamName = g.away_full,
                        score = if (g.completed == true || g.is_live == true) g.away_score else null,
                        isWinner = g.away_winner == true
                    )
                    card.addView(awayRow)
                    
                    // Home team row (with logo)
                    val homeRow = makeTeamRow(
                        teamName = g.home_full,
                        score = if (g.completed == true || g.is_live == true) g.home_score else null,
                        isWinner = g.home_winner == true
                    )
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
                tv.setTextColor(ContextCompat.getColor(this@MainActivity, R.color.text_error))
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
        val team = currentTeam
        if (team.isEmpty()) return

        val manual = manualStats[team]
        if (manual != null && manual.isNotEmpty()) {
            showLoading(false)
            displayManualStats(team, manual)
            return
        }

        showLoading(true)

        lifecycleScope.launch {
            try {
                val statsDeferred = async { apiService.getTeamStats(team).await() }
                val wlDeferred = async { apiService.getWinLoss(team).await() }
                val weatherDeferred = async { apiService.getWeather(team).await() }
                val injuriesDeferred = async { apiService.getInjuries(team).await() }
                val newsDeferred = async { apiService.getNews(team).await() }

                val stats = statsDeferred.await()
                val wl = wlDeferred.await()
                val weather = weatherDeferred.await()
                val injuries = injuriesDeferred.await()
                val news = newsDeferred.await()

                showLoading(false)
                displayFullStats(team, stats, wl, weather, injuries, news)
            } catch (e: Exception) {
                showLoading(false)
                resultText.text = "Failed to load stats: ${e.message}"
            }
        }
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
                    // Calculate spread from predicted score to ensure consistency
                    val pScore = p?.predicted_score
                    val spreadText = if (pScore != null && pScore.contains("-")) {
                        val parts = pScore.split("-")
                        val s1 = parts[0].trim().toIntOrNull() ?: 0
                        val s2 = parts[1].trim().toIntOrNull() ?: 0
                        val diff = s1 - s2
                        when {
                            diff > 0 -> "${p?.team1 ?: "Team 1"} -$diff"
                            diff < 0 -> "${p?.team2 ?: "Team 2"} -${-diff}"
                            else -> "Pick 'Em"
                        }
                    } else {
                        p?.predicted_spread ?: "N/A"
                    }
                    sb.append("Model Spread: $spreadText\n")
                    sb.append("Total: ${p?.predicted_total ?: "N/A"}\n\n")
                    sb.append("Blended Win Probability:\n")
                    val blendedHome = p?.blended_home_probability
                    if (blendedHome != null) {
                        sb.append("  ${team1}: ${blendedHome}%\n")
                        sb.append("  ${team2}: ${100 - blendedHome}%\n")
                    } else {
                        sb.append("  N/A\n")
                    }
                    sb.append("\n")

                    val mlHome = p?.ml_home_probability
                    if (mlHome != null) {
                        sb.append("ML Model: ${mlHome}% home\n")
                    }

                    val marketHome = p?.market_home_prob
                    val edge = p?.edge
                    if (marketHome != null) {
                        sb.append("Market: ${marketHome}% home\n")
                    }
                    if (edge != null) {
                        sb.append("Edge: ${edge}%\n")
                    }
                    if (marketHome != null || edge != null) {
                        sb.append("\n")
                    }
                    if (p?.market_spread != null) {
                        sb.append("SPORTSBOOK LINE\n")
                        sb.append("  Spread: ${p.market_spread}\n")
                        sb.append("  Total: ${p.market_total}\n\n")
                    }
                    resultText.text = sb.toString()

                    // Fire secondary request for similar matchups and append to output
                    apiService.getSimilarMatchups(team1, team2).enqueue(object : Callback<com.bestg.betting.models.SimilarMatchupsResponse> {
                        override fun onResponse(call: Call<com.bestg.betting.models.SimilarMatchupsResponse>, simResp: Response<com.bestg.betting.models.SimilarMatchupsResponse>) {
                            val sims = simResp.body()?.similar ?: emptyList()
                            val summary = simResp.body()?.summary
                            val current = resultText.text.toString()
                            val sb2 = StringBuilder(current)
                            if (sims.isEmpty()) {
                                sb2.append("   No historical matchups found\n")
                            } else {
                                for (m in sims) {
                                    val season = m.season ?: 0
                                    val week = m.week ?: 0
                                    val awayT = m.away_team ?: "?"
                                    val homeT = m.home_team ?: "?"
                                    val awScore = m.away_score ?: 0
                                    val hmScore = m.home_score ?: 0
                                    val winner = m.winner ?: "?"
                                    val margin = m.margin ?: 0
                                    sb2.append("   ${season} W${week}: $awayT $awScore @ $homeT $hmScore — $winner by $margin\n")
                                }
                                if (summary != null) {
                                    sb2.append("\n   Historical: home ${summary.home_wins}/${summary.total}  |  away ${summary.away_wins}/${summary.total}\n")
                                }
                            }
                            resultText.text = sb2.toString()
                        }
                        override fun onFailure(call: Call<com.bestg.betting.models.SimilarMatchupsResponse>, t: Throwable) {
                            val current = resultText.text.toString()
                            val sb2 = StringBuilder(current)
                            sb2.append("   Failed to load similar matchups\n")
                            resultText.text = sb2.toString()
                        }
                    })
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
        // Preferred format: JSON in a string
        val json = sharedPrefs.getString("manual_overrides_json", null)
        if (json != null) {
            try {
                val type = object : com.google.gson.reflect.TypeToken<MutableMap<String, MutableMap<String, String>>>() {}.type
                val parsed: MutableMap<String, MutableMap<String, String>>? = Gson().fromJson(json, type)
                if (parsed != null) {
                    manualStats.clear()
                    manualStats.putAll(parsed)
                    return
                }
            } catch (_: Throwable) {}
        }
        // Fallback: legacy pipe format (still readable, never destroyed)
        sharedPrefs.getStringSet("manual_overrides", emptySet())?.forEach { entry ->
            val parts = entry.split("|")
            if (parts.size == 3) manualStats.getOrPut(parts[0]) { mutableMapOf() }[parts[1]] = parts[2]
        }
    }

    private fun saveManualOverride(team: String, statName: String, value: String) {
        manualStats.getOrPut(team) { mutableMapOf() }[statName] = value
        // Write JSON — legacy pipe format is preserved on disk for safety
        val json = Gson().toJson(manualStats)
        sharedPrefs.edit().putString("manual_overrides_json", json).apply()
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
        resultText.text = "Testing all endpoints on $serverIp:5000...\n\n"

        // Kick off each endpoint in parallel and collect results
        val results = java.util.Collections.synchronizedList(mutableListOf<String>())
        val total = 8
        val startTime = System.currentTimeMillis()

        fun done() {
            val elapsed = System.currentTimeMillis() - startTime
            val sb = StringBuilder()
            sb.append("SERVER HEALTH CHECK\n")
            sb.append("==============================\n")
            sb.append("Host: $serverIp:5000\n")
            sb.append("Time: ${elapsed}ms total\n")
            sb.append("==============================\n\n")
            synchronized(results) {
                for (r in results) sb.append(r).append("\n")
            }
            resultText.text = sb.toString()
            showLoading(false)
        }

        // 1. /test
        apiService.testConnection().enqueue(object : Callback<TestResponse> {
            override fun onResponse(call: Call<TestResponse>, response: Response<TestResponse>) {
                results.add(if (response.isSuccessful) "\u2713 /test" else "\u2717 /test  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<TestResponse>, t: Throwable) {
                results.add("\u2717 /test  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 2. /live_scores
        apiService.getLiveScores().enqueue(object : Callback<LiveScoresResponse> {
            override fun onResponse(call: Call<LiveScoresResponse>, response: Response<LiveScoresResponse>) {
                val count = response.body()?.scores?.size ?: 0
                results.add(if (response.isSuccessful) "\u2713 /live_scores  ($count games)" else "\u2717 /live_scores  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<LiveScoresResponse>, t: Throwable) {
                results.add("\u2717 /live_scores  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 3. /upcoming_games
        apiService.getUpcomingGames().enqueue(object : Callback<UpcomingGamesResponse> {
            override fun onResponse(call: Call<UpcomingGamesResponse>, response: Response<UpcomingGamesResponse>) {
                val count = response.body()?.games?.size ?: 0
                val week = response.body()?.week ?: 0
                results.add(if (response.isSuccessful) "\u2713 /upcoming_games  (week $week, $count games)" else "\u2717 /upcoming_games  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<UpcomingGamesResponse>, t: Throwable) {
                results.add("\u2717 /upcoming_games  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 4. /prediction_accuracy
        apiService.getAccuracy().enqueue(object : Callback<AccuracyResponse> {
            override fun onResponse(call: Call<AccuracyResponse>, response: Response<AccuracyResponse>) {
                val acc = response.body()?.accuracy ?: 0.0
                results.add(if (response.isSuccessful) "\u2713 /prediction_accuracy  (${acc}%)" else "\u2717 /prediction_accuracy  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<AccuracyResponse>, t: Throwable) {
                results.add("\u2717 /prediction_accuracy  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 5. /prediction_log
        apiService.getPredictionLog().enqueue(object : Callback<PredictionLogResponse> {
            override fun onResponse(call: Call<PredictionLogResponse>, response: Response<PredictionLogResponse>) {
                val entryCount = response.body()?.total ?: 0
                results.add(if (response.isSuccessful) "\u2713 /prediction_log  ($entryCount entries)" else "\u2717 /prediction_log  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<PredictionLogResponse>, t: Throwable) {
                results.add("\u2717 /prediction_log  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 6. /odds
        apiService.getOdds().enqueue(object : Callback<OddsResponse> {
            override fun onResponse(call: Call<OddsResponse>, response: Response<OddsResponse>) {
                val count = response.body()?.odds?.size ?: 0
                results.add(if (response.isSuccessful) "\u2713 /odds  ($count games)" else "\u2717 /odds  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<OddsResponse>, t: Throwable) {
                results.add("\u2717 /odds  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 7. /weather for a known team
        apiService.getWeather("Kansas City Chiefs").enqueue(object : Callback<WeatherResponse> {
            override fun onResponse(call: Call<WeatherResponse>, response: Response<WeatherResponse>) {
                val temp = response.body()?.temperature
                results.add(if (response.isSuccessful) "\u2713 /weather  ($temp\u00B0F KC)" else "\u2717 /weather  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<WeatherResponse>, t: Throwable) {
                results.add("\u2717 /weather  ${t.message}")
                if (results.size == total) done()
            }
        })

        // 8. /ml_predict for a known matchup
        apiService.getMlPrediction("Kansas City Chiefs", "Buffalo Bills").enqueue(object : Callback<MlPredictionResponse> {
            override fun onResponse(call: Call<MlPredictionResponse>, response: Response<MlPredictionResponse>) {
                val winner = response.body()?.predicted_winner
                results.add(if (response.isSuccessful) "\u2713 /ml_predict  ($winner)" else "\u2717 /ml_predict  HTTP ${response.code()}")
                if (results.size == total) done()
            }
            override fun onFailure(call: Call<MlPredictionResponse>, t: Throwable) {
                results.add("\u2717 /ml_predict  ${t.message}")
                if (results.size == total) done()
            }
        })
    }


    private fun updateHelpButtonLabel() {
        val helpBtn = findViewById<MaterialButton>(R.id.helpButton)
        val labels = listOf(
            "HELP",
            "ACCURACY",
            "PRED LOG",
            "LIVE PICKS",
            "ODDS",
            "PROPS",
            "SERVER IP"
        )
        val nextLabel = labels[(helpCycle + 1) % labels.size]
        helpBtn.text = "$nextLabel \u2192"
    }



    private fun showHeadToHead() {
        if (currentTeam.isEmpty() || opponentTeam.isEmpty()) {
            resultText.text = "H2H needs a matchup.\n\nGo to PREDICT mode, tap a game, then tap HELP 7 times."
            return
        }
        showLoading(true)
        resultText.text = "Building H2H: $currentTeam vs $opponentTeam..."

        // Pull both team stats in parallel and diff them
        lifecycleScope.launch {
            try {
                val homeStats = async { apiService.getTeamStats(currentTeam).await() }
                val awayStats = async { apiService.getTeamStats(opponentTeam).await() }
                val homeWl = async { apiService.getWinLoss(currentTeam).await() }
                val awayWl = async { apiService.getWinLoss(opponentTeam).await() }

                val hs = homeStats.await()
                val as_ = awayStats.await()
                val hw = homeWl.await()
                val aw = awayWl.await()

                showLoading(false)
                val sb = StringBuilder()
                sb.append("HEAD-TO-HEAD\n")
                sb.append("==============================\n\n")
                sb.append("$currentTeam (home)  vs  $opponentTeam (away)\n\n")

                sb.append("RECORD\n")
                sb.append("  $currentTeam: ${hw.regular_season_record ?: "N/A"}  (${String.format("%.1f", (hw.win_percentage ?: 0.0) * 100)}%)\n")
                sb.append("  $opponentTeam: ${aw.regular_season_record ?: "N/A"}  (${String.format("%.1f", (aw.win_percentage ?: 0.0) * 100)}%)\n\n")

                sb.append("POINTS\n")
                sb.append("  $currentTeam:  PF ${hs.points_for ?: 0}  PA ${hs.points_against ?: 0}\n")
                sb.append("  $opponentTeam: PF ${as_.points_for ?: 0}  PA ${as_.points_against ?: 0}\n\n")

                val homeDiff = (hs.points_for ?: 0) - (hs.points_against ?: 0)
                val awayDiff = (as_.points_for ?: 0) - (as_.points_against ?: 0)
                sb.append("POINT DIFFERENTIAL\n")
                sb.append("  $currentTeam:  ${if (homeDiff >= 0) "+" else ""}$homeDiff\n")
                sb.append("  $opponentTeam: ${if (awayDiff >= 0) "+" else ""}$awayDiff\n\n")

                sb.append("STREAKS\n")
                sb.append("  $currentTeam:  ${hs.streak ?: "N/A"}\n")
                sb.append("  $opponentTeam: ${as_.streak ?: "N/A"}\n\n")

                sb.append("EDGE\n")
                when {
                    homeDiff > awayDiff -> sb.append("  $currentTeam by ${homeDiff - awayDiff} pts\n")
                    awayDiff > homeDiff -> sb.append("  $opponentTeam by ${awayDiff - homeDiff} pts\n")
                    else -> sb.append("  Even matchup\n")
                }

                resultText.text = sb.toString()
            } catch (e: Exception) {
                showLoading(false)
                resultText.text = "H2H failed: ${e.message}"
            }
        }
    }

    private fun showPreseasonStats() {
        if (currentPlayer.isEmpty() || currentTeam.isEmpty()) {
            resultText.text = "Select a player first in PLAYER mode, then tap HELP"
            return
        }
        showLoading(true)
        resultText.text = "Loading preseason stats for $currentPlayer..."
        apiService.getPreseasonStats(currentTeam, currentPlayer).enqueue(object : Callback<com.bestg.betting.models.PreseasonStatsResponse> {
            override fun onResponse(call: Call<com.bestg.betting.models.PreseasonStatsResponse>, response: Response<com.bestg.betting.models.PreseasonStatsResponse>) {
                showLoading(false)
                val s = response.body()?.stats
                if (s == null) {
                    resultText.text = "No preseason data for $currentPlayer"
                    return
                }
                val sb = StringBuilder()
                sb.append("PRESEASON: $currentPlayer\n")
                sb.append("==============================\n\n")
                if (s.passing_yards != null) {
                    sb.append("[ PASSING ]\n")
                    sb.append("Yards: ${s.passing_yards}\n")
                    if (s.passing_tds != null) sb.append("TDs: ${s.passing_tds}\n")
                    if (s.completions != null && s.passing_attempts != null)
                        sb.append("Comp: ${s.completions}/${s.passing_attempts}\n")
                    if (s.interceptions != null) sb.append("INTs: ${s.interceptions}\n")
                    sb.append("\n")
                }
                if (s.rushing_yards != null) {
                    sb.append("[ RUSHING ]\n")
                    sb.append("Yards: ${s.rushing_yards}\n")
                    if (s.rushing_tds != null) sb.append("TDs: ${s.rushing_tds}\n")
                    sb.append("\n")
                }
                if (s.receiving_yards != null) {
                    sb.append("[ RECEIVING ]\n")
                    sb.append("Yards: ${s.receiving_yards}\n")
                    if (s.receiving_tds != null) sb.append("TDs: ${s.receiving_tds}\n")
                    if (s.receptions != null) sb.append("Rec: ${s.receptions}\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<com.bestg.betting.models.PreseasonStatsResponse>, t: Throwable) {
                showLoading(false)
                resultText.text = "Failed: ${t.message}"
            }
        })
    }



    private fun showAccuracyByWeek() {
        showLoading(true)
        resultText.text = "Loading weekly accuracy..."
        apiService.getAccuracyByWeek().enqueue(object : Callback<com.bestg.betting.models.AccuracyByWeekResponse> {
            override fun onResponse(call: Call<com.bestg.betting.models.AccuracyByWeekResponse>, response: Response<com.bestg.betting.models.AccuracyByWeekResponse>) {
                showLoading(false)
                val weeks = response.body()?.weeks ?: emptyList()
                if (weeks.isEmpty()) {
                    resultText.text = "No completed weeks yet\n\nPredictions resolve automatically as games finish."
                    return
                }
                val sb = StringBuilder()
                sb.append("ACCURACY BY WEEK\n")
                sb.append("==============================\n\n")
                for (w in weeks) {
                    val pct = w.accuracy
                    val bars = (pct / 5).toInt().coerceIn(0, 20)
                    val bar = "\u2588".repeat(bars) + "\u2591".repeat(20 - bars)
                    sb.append("${w.week}  ${String.format("%5.1f", pct)}%  $bar\n")
                    sb.append("           ${w.correct}/${w.total}\n\n")
                }
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<com.bestg.betting.models.AccuracyByWeekResponse>, t: Throwable) {
                showLoading(false)
                resultText.text = "Failed: ${t.message}"
                Toast.makeText(this@MainActivity, "Weekly accuracy failed", Toast.LENGTH_SHORT).show()
            }
        })
    }




    private fun toggleNotifications() {
        val current = sharedPrefs.getBoolean("notif_enabled", false)
        val next = !current
        sharedPrefs.edit().putBoolean("notif_enabled", next).apply()

        // Request POST_NOTIFICATIONS runtime permission on Android 13+
        if (next && android.os.Build.VERSION.SDK_INT >= 33) {
            try {
                requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 1001)
            } catch (_: Throwable) {}
        }

        if (next) {
            scheduleNotifications()
            resultText.text = "\uD83D\uDD14 NOTIFICATIONS: ON\n\nYou will be alerted when:\n- A new NFL game goes live\n\nWorker runs every ~15 min in the background.\n\nTap HELP 12x to turn off."
        } else {
            cancelNotifications()
            resultText.text = "\uD83D\uDD15 NOTIFICATIONS: OFF\n\nNo background checks.\n\nTap HELP 12x to turn back on."
        }
        Toast.makeText(this, "Notifications: ${if (next) "ON" else "OFF"}", Toast.LENGTH_SHORT).show()
    }

    private fun scheduleNotifications() {
        try {
            val constraints = androidx.work.Constraints.Builder()
                .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
                .build()
            val request = androidx.work.PeriodicWorkRequestBuilder<ScoreCheckWorker>(
                15, java.util.concurrent.TimeUnit.MINUTES
            )
                .setConstraints(constraints)
                .build()
            androidx.work.WorkManager.getInstance(this)
                .enqueueUniquePeriodicWork(
                    "nfl_score_check",
                    androidx.work.ExistingPeriodicWorkPolicy.KEEP,
                    request
                )
            AppLog.i("Score check scheduled every 15 min")
        } catch (e: Exception) {
            AppLog.w("scheduleNotifications failed: ${e.message}")
        }
    }

    private fun cancelNotifications() {
        try {
            androidx.work.WorkManager.getInstance(this).cancelUniqueWork("nfl_score_check")
            AppLog.i("Score check canceled")
        } catch (_: Throwable) {}
    }

    private fun autoDetectServer() {
        showLoading(true)
        resultText.text = "Searching for NFL server on local network...\n\nBroadcasting mDNS query. This takes 5-10 seconds."
        lifecycleScope.launch {
            val found = ServerDiscovery.discover(this@MainActivity, timeoutMs = 7000)
            showLoading(false)
            if (found != null) {
                val ip = found.substringBefore(":")
                cancelAllInFlight()
                serverIp = ip
                sharedPrefs.edit().putString("server_ip", ip).apply()
                setupRetrofit()
                resultText.text = "✅ Found server at $found\n\nSaved to preferences. All future requests will use this IP."
                Toast.makeText(this@MainActivity, "Server found: $found", Toast.LENGTH_LONG).show()
            } else {
                resultText.text = "❌ No NFL server found on local network.\n\nChecklist:\n- Flask server running?\n- Same Wi-Fi as the phone?\n- Server broadcasting mDNS? (see zeroconf setup)\n\nYou can still set the IP manually with HELP 12x → SERVER IP."
            }
        }
    }

    private fun showBacktest() {
        showLoading(true)
        resultText.text = "Running backtest..."
        apiService.getBacktest().enqueue(object : Callback<com.bestg.betting.models.BacktestResponse> {
            override fun onResponse(call: Call<com.bestg.betting.models.BacktestResponse>, response: Response<com.bestg.betting.models.BacktestResponse>) {
                showLoading(false)
                val d = response.body()
                if (d == null) {
                    resultText.text = "No backtest data"
                    return
                }
                val sb = StringBuilder()
                sb.append("\uD83D\uDCCA BACKTEST RESULTS\n")
                sb.append("\u2501".repeat(30) + "\n\n")

                // Overall
                d.overall?.let { o ->
                    sb.append("OVERALL\n")
                    sb.append("   ${o.correct}/${o.total} correct — ${o.accuracy}%\n\n")
                }

                // By confidence
                d.by_confidence?.let { bc ->
                    sb.append("BY CONFIDENCE\n")
                    for ((k, v) in bc) {
                        sb.append("   $k: ${v.correct}/${v.total} = ${v.accuracy}%\n")
                    }
                    sb.append("\n")
                }

                // By side (home/away pick)
                d.by_side?.let { bs ->
                    sb.append("BY PICK SIDE\n")
                    for ((k, v) in bs) {
                        sb.append("   $k: ${v.correct}/${v.total} = ${v.accuracy}%\n")
                    }
                    sb.append("\n")
                }

                // By edge
                d.by_edge?.let { be ->
                    sb.append("BY EDGE\n")
                    for ((k, v) in be) {
                        sb.append("   $k: ${v.correct}/${v.total} = ${v.accuracy}%\n")
                    }
                    sb.append("\n")
                }

                // By divisional
                d.by_divisional?.let { bd ->
                    sb.append("BY DIVISIONAL\n")
                    for ((k, v) in bd) {
                        sb.append("   $k: ${v.correct}/${v.total} = ${v.accuracy}%\n")
                    }
                    sb.append("\n")
                }

                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<com.bestg.betting.models.BacktestResponse>, t: Throwable) {
                showLoading(false)
                resultText.text = "Backtest failed: ${t.message}"
            }
        })
    }

    private fun toggleTheme() {
        val current = sharedPrefs.getString("theme_mode", "dark") ?: "dark"
        val next = if (current == "dark") "light" else "dark"
        sharedPrefs.edit().putString("theme_mode", next).apply()
        resultText.text = "Theme set to: $next\n\nRestart the app for the change to take effect.\n\nHelp cycle: THEME ($next) \u2192 SERVER IP"
        Toast.makeText(this, "Theme: $next (restart to apply)", Toast.LENGTH_LONG).show()
        // Apply immediately via AppCompatDelegate for instant effect
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(
            if (next == "dark") androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES
            else androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO
        )
    }

    private fun showHelp() {
        resultText.text = "HELP - $serverIp:5000\n\nTap HELP repeatedly to cycle:\n1. Accuracy\n2. Prediction Log\n3. Live Predictions\n4. Odds\n5. Player Props\n6. Preseason Stats\n7. Head-to-Head\n8. Theme toggle\n9. Server IP\n\nLong-press PREDICTION LOG to star entries."
    }

    private fun showLoading(show: Boolean) {
        loadingIndicator.visibility = if (show) View.VISIBLE else View.GONE
        if (!show) swipeRefresh.isRefreshing = false
    }
}
