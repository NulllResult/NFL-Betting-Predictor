@file:Suppress("UnnecessarySafeCall", "RedundantElvisOperator", "NAME_SHADOWING", "DEPRECATION")

package com.bestg.betting

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.ViewGroup
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
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import androidx.core.content.ContextCompat
import com.google.gson.Gson
import com.bestg.betting.models.*

class MainActivity : AppCompatActivity() {

    private lateinit var resultText: TextView
    private lateinit var scoreBannerFlipper: android.widget.ViewFlipper
    private lateinit var loadingIndicator: ProgressBar
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var gamesScroll: ScrollView
    private lateinit var gamesList: LinearLayout
    private lateinit var apiService: ApiService
    private lateinit var sharedPrefs: SharedPreferences

    private var currentMode = "STATS"
    private var helpCycle = 0
    private var logFilter = "ALL"
    private var latestScores: List<LiveScore> = emptyList()
    private var scorePage = 0
    private var currentTeam = ""
    private var currentPlayer = ""
    private var opponentTeam = ""
    private var serverIp = "10.0.0.60"
    private var allNFLTeams = listOf(
        "Buffalo Bills", "Miami Dolphins", "New England Patriots", "New York Jets", "Baltimore Ravens", "Cincinnati Bengals", "Cleveland Browns", "Pittsburgh Steelers",
        "Houston Texans", "Indianapolis Colts", "Jacksonville Jaguars", "Tennessee Titans", "Denver Broncos", "Kansas City Chiefs", "Las Vegas Raiders", "Los Angeles Chargers",
        "Dallas Cowboys", "New York Giants", "Philadelphia Eagles", "Washington Commanders", "Chicago Bears", "Detroit Lions", "Green Bay Packers", "Minnesota Vikings",
        "Atlanta Falcons", "Carolina Panthers", "New Orleans Saints", "Tampa Bay Buccaneers", "Arizona Cardinals", "Los Angeles Rams", "San Francisco 49ers", "Seattle Seahawks"
    )
    private val scoreHandler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        sharedPrefs = getSharedPreferences("NFL_Betting_Prefs", Context.MODE_PRIVATE)
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES)
        serverIp = sharedPrefs.getString("server_ip", "10.0.0.60") ?: "10.0.0.60"

        resultText = findViewById(R.id.resultText)
        scoreBannerFlipper = findViewById(R.id.scoreBannerFlipper)
        loadingIndicator = findViewById(R.id.loadingIndicator)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        gamesScroll = findViewById(R.id.gamesScroll)
        gamesList = findViewById(R.id.gamesList)

        resultText.movementMethod = ScrollingMovementMethod()

        // Swipe Right to go back
        val rootView = findViewById<View>(android.R.id.content)
        rootView.setOnTouchListener(object : View.OnTouchListener {
            private var downX = 0f
            override fun onTouch(v: View, event: android.view.MotionEvent): Boolean {
                when (event.action) {
                    android.view.MotionEvent.ACTION_DOWN -> downX = event.x
                    android.view.MotionEvent.ACTION_UP -> {
                        val upX = event.x
                        if (currentMode == "PLAYER" && (upX - downX) > 250) {
                            setStatsMode()
                            return true
                        }
                    }
                }
                return false
            }
        })

        setupRetrofit()
        testConnection()

        swipeRefresh.setOnRefreshListener { 
            when (currentMode) {
                "STATS" -> getTeamStats()
                "PLAYER" -> getPlayerStats()
                "PREDICT" -> fetchPrediction(currentTeam, opponentTeam)
            }
            fetchLiveScores() 
        }

        findViewById<MaterialButton>(R.id.testButton).setOnClickListener { testConnection() }
        findViewById<MaterialButton>(R.id.loadStatsButton).setOnClickListener { setStatsMode() }
        findViewById<MaterialButton>(R.id.predictButton).setOnClickListener { setPredictMode() }
        findViewById<MaterialButton>(R.id.clearButton).setOnClickListener { resultText.text = "" }
        findViewById<MaterialButton>(R.id.refreshAllButton).setOnClickListener {
            if (currentMode == "PREDICT") setPredictMode() else fetchLiveScores()
        }
        // HIDDEN: Long-press the gold button to change the IP
        findViewById<MaterialButton>(R.id.helpButton).setOnLongClickListener {
            showServerIpDialog()
            true
        }

        findViewById<MaterialButton>(R.id.helpButton).setOnClickListener {
            if (currentMode == "PLAYER") {
                setStatsMode()
                helpCycle = 0
                updateHelpButtonLabel()
                return@setOnClickListener
            }
            gamesScroll.visibility = View.GONE
            swipeRefresh.visibility = View.VISIBLE
            resultText.visibility = View.VISIBLE
            helpCycle = (helpCycle + 1) % 9
            when (helpCycle) {
                0 -> setPlayerMode()
                1 -> showHelp()
                2 -> showAccuracy()
                3 -> showPredictionLog()
                4 -> showLivePredictions()
                5 -> showOdds()
                6 -> showHeadToHead()
                7 -> showAccuracyByWeek()
                8 -> showBacktest()
            }
            updateHelpButtonLabel()
        }

        testConnection() // Trigger an immediate check
        setPredictMode()
        fetchLiveScores()
        startScoreUpdates()
        updateHelpButtonLabel()
    }

    private fun updateHelpButtonLabel() {
        val helpBtn = findViewById<MaterialButton>(R.id.helpButton)
        if (currentMode == "PLAYER") {
            helpBtn.text = "← BACK"
            return
        }
        val labels = listOf("PLAYER", "HELP", "ACCURACY", "PRED LOG", "LIVE PICKS", "ODDS", "H2H", "WK CHART", "BACKTEST")
        helpBtn.text = "${labels[(helpCycle + 1) % labels.size]} →"
    }

    private fun setupRetrofit() {
        apiService = Retrofit.Builder().baseUrl("http://$serverIp:5000/").addConverterFactory(GsonConverterFactory.create()).build().create(ApiService::class.java)
    }

    private fun startScoreUpdates() {
        scoreHandler.postDelayed(object : Runnable {
            override fun run() { fetchLiveScores(); scoreHandler.postDelayed(this, 30000) }
        }, 30000)
    }

    private fun fetchLiveScores() {
        apiService.getLiveScores().enqueue(object : Callback<LiveScoresResponse> {
            override fun onResponse(call: Call<LiveScoresResponse>, response: Response<LiveScoresResponse>) {
                if (response.isSuccessful) {
                    latestScores = response.body()?.scores ?: emptyList()
                    renderScorePage()
                }
            }
            override fun onFailure(call: Call<LiveScoresResponse>, t: Throwable) {}
        })
    }

    private fun renderScorePage() {
        scoreBannerFlipper.removeAllViews()
        if (latestScores.isEmpty()) {
            val tv = TextView(this); tv.text = " No live games"; tv.setTextColor(0xFFFFB612.toInt()); tv.textSize = 13f
            scoreBannerFlipper.addView(tv); return
        }
        val sizePx = (22 * resources.displayMetrics.density).toInt()
        for (game in latestScores) {
            val row = LinearLayout(this)
            row.orientation = LinearLayout.HORIZONTAL; row.gravity = android.view.Gravity.CENTER_VERTICAL
            row.layoutParams = android.widget.FrameLayout.LayoutParams(android.widget.FrameLayout.LayoutParams.WRAP_CONTENT, android.widget.FrameLayout.LayoutParams.WRAP_CONTENT)
            
            val awayLogo = ImageView(this); awayLogo.layoutParams = LinearLayout.LayoutParams(sizePx, sizePx); awayLogo.setImageResource(getTeamLogo(game.away)); awayLogo.scaleType = ImageView.ScaleType.FIT_CENTER
            row.addView(awayLogo)
            
            val tv = TextView(this); tv.text = " ${game.away} ${game.away_score}-${game.home_score} ${game.home} (${game.detail.ifBlank { game.status }}) "
            tv.setTextColor(0xFFFFB612.toInt()); tv.textSize = 13f; tv.maxLines = 1; tv.setPadding(8, 0, 8, 0)
            row.addView(tv)
            
            val homeLogo = ImageView(this); homeLogo.layoutParams = LinearLayout.LayoutParams(sizePx, sizePx); homeLogo.setImageResource(getTeamLogo(game.home)); homeLogo.scaleType = ImageView.ScaleType.FIT_CENTER
            row.addView(homeLogo)
            scoreBannerFlipper.addView(row)
        }
        if (latestScores.size > 1) scoreBannerFlipper.startFlipping()
    }

    private fun getTeamLogo(teamName: String): Int {
        val map = mapOf("BUF" to "buf", "MIA" to "mia", "NE" to "ne", "NYJ" to "nyj", "BAL" to "bal", "CIN" to "cin", "CLE" to "cle", "PIT" to "pit", "HOU" to "hou", "IND" to "ind", "JAX" to "jax", "TEN" to "ten", "DEN" to "den", "KC" to "kc", "LV" to "lv", "LAC" to "lac", "DAL" to "dal", "NYG" to "nyg", "PHI" to "phi", "WAS" to "wsh", "CHI" to "chi", "DET" to "det", "GB" to "gb", "MIN" to "min", "ATL" to "atl", "CAR" to "car", "NO" to "no", "TB" to "tb", "ARI" to "ari", "LA" to "lar", "SF" to "sf", "SEA" to "sea")
        val upper = teamName.uppercase().trim()
        val abbr = map[upper] ?: "pit"
        val id = resources.getIdentifier("logo_$abbr", "drawable", packageName)
        return if (id != 0) id else R.drawable.logo_pit
    }

    private fun setStatsMode() {
        currentMode = "STATS"
        swipeRefresh.visibility = View.VISIBLE
        gamesScroll.visibility = View.GONE
        resultText.visibility = View.VISIBLE
        if (resultText.text.isEmpty() || currentTeam.isEmpty()) resultText.text = "Select a team via PREDICT mode."
        updateHelpButtonLabel()
    }

    private fun setPlayerMode() {
        currentMode = "PLAYER"
        swipeRefresh.visibility = View.VISIBLE
        gamesScroll.visibility = View.GONE
        resultText.text = "PLAYER MODE\n\nSwipe right to go back."
        updateHelpButtonLabel()
    }

    private fun setPredictMode() {
        currentMode = "PREDICT"
        swipeRefresh.visibility = View.GONE
        gamesScroll.visibility = View.VISIBLE
        gamesList.removeAllViews()
        updateHelpButtonLabel()
        
        apiService.getUpcomingGames().enqueue(object : Callback<UpcomingGamesResponse> {
            override fun onResponse(call: Call<UpcomingGamesResponse>, response: Response<UpcomingGamesResponse>) {
                val games = response.body()?.games ?: emptyList()
                gamesList.removeAllViews()
                for (g in games) {
                    val tv = TextView(this@MainActivity)
                    tv.text = "${g.away_full} @ ${g.home_full}"
                    tv.setTextColor(0xFFFFFFFF.toInt()); tv.textSize = 18f; tv.setPadding(16, 16, 16, 16)
                    tv.setOnClickListener {
                        currentTeam = g.home_full; opponentTeam = g.away_full
                        gamesScroll.visibility = View.GONE; swipeRefresh.visibility = View.VISIBLE; resultText.visibility = View.VISIBLE
                        fetchPrediction(g.home_full, g.away_full)
                    }
                    gamesList.addView(tv)
                }
            }
            override fun onFailure(call: Call<UpcomingGamesResponse>, t: Throwable) {}
        })
    }

    private fun getTeamStats() {
        apiService.getTeamStats(currentTeam).enqueue(object : Callback<TeamStatsResponse> {
            override fun onResponse(call: Call<TeamStatsResponse>, response: Response<TeamStatsResponse>) {
                val s = response.body() ?: return
                resultText.text = "TEAM STATS: ${s.team}\nRecord: ${s.record}\nPF: ${s.points_for} PA: ${s.points_against}"
            }
            override fun onFailure(call: Call<TeamStatsResponse>, t: Throwable) { resultText.text = "Error: ${t.message}" }
        })
    }

    private fun getPlayerStats() {
        apiService.getPlayerStats(currentPlayer, currentTeam).enqueue(object : Callback<PlayerStatsResponse> {
            override fun onResponse(call: Call<PlayerStatsResponse>, response: Response<PlayerStatsResponse>) {
                val p = response.body() ?: return
                resultText.text = "${p.name}\n${p.position} | #${p.jersey}\n\nYards: ${p.stats?.passing_yards ?: p.stats?.rushing_yards ?: p.stats?.receiving_yards ?: 0}"
            }
            override fun onFailure(call: Call<PlayerStatsResponse>, t: Throwable) { resultText.text = "Error: ${t.message}" }
        })
    }

    private fun fetchPrediction(team1: String, team2: String) {
        showLoading(true)
        apiService.getMlPrediction(team1, team2).enqueue(object : Callback<MlPredictionResponse> {
            override fun onResponse(call: Call<MlPredictionResponse>, response: Response<MlPredictionResponse>) {
                showLoading(false)
                val p = response.body() ?: return
                val sb = StringBuilder()
                sb.append("${p.team1} vs ${p.team2}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n")
                sb.append("WINNER: ${p.predicted_winner}\n")
                sb.append("Score: ${p.predicted_score}\n")
                sb.append("Spread: ${p.predicted_spread}\n")
                sb.append("Total: ${p.predicted_total}\n\n")
                sb.append("CONFIDENCE: ${p.confidence}% (${p.confidence_level})\n")
                if (p.key_factors != null) for (f in p.key_factors) sb.append("• $f\n")
                resultText.text = sb.toString()
            }
            override fun onFailure(call: Call<MlPredictionResponse>, t: Throwable) {
                showLoading(false); resultText.text = "Error: ${t.message}"
            }
        })
    }

    private fun showHeadToHead() {
        if (currentTeam.isEmpty() || opponentTeam.isEmpty()) { resultText.text = "Select a matchup in PREDICT mode first."; return }
        resultText.text = "H2H: $currentTeam vs $opponentTeam\n(Loading stats...)"
        // Simplified H2H to avoid crashes
        apiService.getTeamStats(currentTeam).enqueue(object : Callback<TeamStatsResponse> {
            override fun onResponse(call: Call<TeamStatsResponse>, response: Response<TeamStatsResponse>) {
                val s = response.body()
                resultText.text = "H2H: $currentTeam\nPF: ${s?.points_for}\nPA: ${s?.points_against}\n\nUse PREDICT for full matchup."
            }
            override fun onFailure(call: Call<TeamStatsResponse>, t: Throwable) { resultText.text = "Error loading H2H" }
        })
    }

    private fun showHelp() { resultText.text = "HELP\n\nTap the gold button to cycle through menus. Swipe right in PLAYER mode to go back." }
    private fun showAccuracy() { resultText.text = "Accuracy stats loading..." }
    private fun showPredictionLog() { resultText.text = "Prediction log loading..." }
    private fun showLivePredictions() { resultText.text = "Live predictions loading..." }
    private fun showOdds() { resultText.text = "Odds loading..." }
    private fun showAccuracyByWeek() { resultText.text = "Weekly chart loading..." }
    private fun showBacktest() { resultText.text = "Backtest loading..." }
    
    private fun showServerIpDialog() {
        val input = EditText(this); input.setText(serverIp)
        AlertDialog.Builder(this).setTitle("Server IP").setView(input).setPositiveButton("Save") { _, _ ->
            serverIp = input.text.toString(); sharedPrefs.edit().putString("server_ip", serverIp).apply(); setupRetrofit()
        }.setNegativeButton("Cancel", null).show()
    }

    private fun testConnection() {
        showLoading(true)
        resultText.text = "Connecting to http://$serverIp:5000...\n\nIf this stays here, the app cannot reach your PC.\n\nLong-press the big gold button to change the IP."
        
        apiService.testConnection().enqueue(object : Callback<TestResponse> {
            override fun onResponse(call: Call<TestResponse>, response: Response<TestResponse>) {
                showLoading(false)
                resultText.text = "✅ SERVER CONNECTED\nIP: $serverIp\n\nLoading games..."
            }
            override fun onFailure(call: Call<TestResponse>, t: Throwable) {
                showLoading(false)
                resultText.text = "❌ CONNECTION FAILED\nIP: $serverIp\n\nError: ${t.message}\n\nLong-press the big gold button to change IP."
            }
        })
    }

    private fun showLoading(show: Boolean) {
        loadingIndicator.visibility = if (show) View.VISIBLE else View.GONE
        if (!show) swipeRefresh.isRefreshing = false
    }

    private fun showPreseasonStats() {
        resultText.text = "PRESEASON STATS\n\nSelect a player first."
    }
    private fun showPlayerProps() {
        resultText.text = "PLAYER PROPS\n\nSelect a player first."
    }
}
