package com.bestg.betting

/**
 * MainViewModel — Holds cross-configuration state for MainActivity.
 * State is snapshotted in onPause and restored in onCreate.
 * All fields are LiveData-wrapped for observer-driven updates.
 */

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import com.bestg.betting.models.PredictionLogEntry
import com.bestg.betting.models.LiveScore

/**
 * Holds all cross-configuration state for MainActivity.
 * Survives rotation, process death, and configuration changes.
 *
 * State is exposed via LiveData so MainActivity can observe changes.
 * All setters are simple assignment; observers handle UI updates.
 */
class MainViewModel(app: Application) : AndroidViewModel(app) {

    // ───── Current mode ─────
    private val _mode = MutableLiveData("STATS")
    val mode: LiveData<String> = _mode
    fun setMode(m: String) { _mode.value = m }

    // ───── Current selections ─────
    private val _currentTeam = MutableLiveData("")
    val currentTeam: LiveData<String> = _currentTeam
    fun setCurrentTeam(t: String) { _currentTeam.value = t }

    private val _currentPlayer = MutableLiveData("")
    val currentPlayer: LiveData<String> = _currentPlayer
    fun setCurrentPlayer(p: String) { _currentPlayer.value = p }

    private val _opponentTeam = MutableLiveData("")
    val opponentTeam: LiveData<String> = _opponentTeam
    fun setOpponentTeam(t: String) { _opponentTeam.value = t }

    // ───── Help cycle + log filter ─────
    private val _helpCycle = MutableLiveData(0)
    val helpCycle: LiveData<Int> = _helpCycle
    fun bumpHelpCycle(modulo: Int) {
        val current = _helpCycle.value ?: 0
        _helpCycle.value = (current + 1) % modulo
    }

    private val _logFilter = MutableLiveData("ALL")
    val logFilter: LiveData<String> = _logFilter
    fun setLogFilter(f: String) { _logFilter.value = f }

    // ───── Server config ─────
    private val _serverIp = MutableLiveData("10.0.0.60")
    val serverIp: LiveData<String> = _serverIp
    fun setServerIp(ip: String) { _serverIp.value = ip }

    // ───── Latest scores (for banner rotation) ─────
    private val _latestScores = MutableLiveData<List<LiveScore>>(emptyList())
    val latestScores: LiveData<List<LiveScore>> = _latestScores
    fun setLatestScores(s: List<LiveScore>) { _latestScores.value = s }

    private val _scorePage = MutableLiveData(0)
    val scorePage: LiveData<Int> = _scorePage
    fun nextScorePage(totalPages: Int) {
        val current = _scorePage.value ?: 0
        _scorePage.value = (current + 1) % totalPages.coerceAtLeast(1)
    }

    // ───── Latest prediction output (survives rotation) ─────
    private val _lastPredictionText = MutableLiveData("")
    val lastPredictionText: LiveData<String> = _lastPredictionText
    fun setLastPredictionText(t: String) { _lastPredictionText.value = t }

    // ───── Log cache ─────
    private val _lastLogEntries = MutableLiveData<List<PredictionLogEntry>>(emptyList())
    val lastLogEntries: LiveData<List<PredictionLogEntry>> = _lastLogEntries
    fun setLastLogEntries(l: List<PredictionLogEntry>) { _lastLogEntries.value = l }
}
