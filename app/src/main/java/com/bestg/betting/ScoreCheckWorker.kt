package com.bestg.betting

/**
 * ScoreCheckWorker — Background worker that polls /live_scores every 15 minutes
 * and fires a notification when a game transitions from scheduled to LIVE.
 * Enabled/disabled via HELP 12x → NOTIFS.
 */

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Worker
import androidx.work.WorkerParameters
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

/**
 * Background worker: polls /live_scores every ~15 minutes.
 * Fires a notification when:
 *   - A game transitions to LIVE for the first time (tracked in prefs)
 *   - The leader in a live game changes (optional toggle)
 *
 * Uses Retrofit directly (no Activity dependency).
 */
class ScoreCheckWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {

    companion object {
        const val CHANNEL_ID = "nfl_live_scores"
        const val CHANNEL_NAME = "NFL Live Scores"
        const val NOTIF_ID_BASE = 1000
        const val PREFS = "NFL_Betting_Prefs"
        const val KEY_SEEN_LIVE = "notif_seen_live_games"
        const val KEY_NOTIF_ENABLED = "notif_enabled"
    }

    override fun doWork(): Result {
        val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val enabled = prefs.getBoolean(KEY_NOTIF_ENABLED, true)
        if (!enabled) return Result.success()

        val serverIp = prefs.getString("server_ip", "10.0.0.60") ?: "10.0.0.60"
        val seenLive = prefs.getStringSet(KEY_SEEN_LIVE, emptySet()) ?: emptySet()
        val newSeen = seenLive.toMutableSet()

        createChannel()

        val api = Retrofit.Builder()
            .baseUrl("http://$serverIp:5000/")
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)

        // Synchronous call inside the worker thread (allowed)
        try {
            val response = api.getLiveScores().execute()
            if (response.isSuccessful) {
                val scores = response.body()?.scores ?: emptyList()
                for (game in scores) {
                    val key = "${game.away}|${game.home}"
                    // Detect newly-live game
                    if (!seenLive.contains(key) && game.status == "in") {
                        notify(
                            id = NOTIF_ID_BASE + key.hashCode(),
                            title = "🏈 ${game.away} @ ${game.home} is LIVE",
                            body = "${game.away} ${game.away_score} - ${game.home_score} ${game.home}  (${game.detail.ifBlank { game.status }})"
                        )
                        newSeen.add(key)
                    }
                }
                // Save updated seen set
                prefs.edit().putStringSet(KEY_SEEN_LIVE, newSeen).apply()
            }
            return Result.success()
        } catch (e: Exception) {
            AppLog.w("ScoreCheckWorker failed: ${e.message}")
            return Result.retry()
        }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (mgr.getNotificationChannel(CHANNEL_ID) == null) {
                val ch = NotificationChannel(
                    CHANNEL_ID,
                    CHANNEL_NAME,
                    NotificationManager.IMPORTANCE_DEFAULT
                ).apply {
                    description = "Alerts when NFL games go live"
                }
                mgr.createNotificationChannel(ch)
            }
        }
    }

    private fun notify(id: Int, title: String, body: String) {
        val nm = NotificationManagerCompat.from(applicationContext)
        if (!nm.areNotificationsEnabled()) return

        val builder = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)

        try {
            nm.notify(id, builder.build())
            AppLog.i("Notification fired: $title")
        } catch (se: SecurityException) {
            AppLog.w("Notification permission missing: ${se.message}")
        }
    }
}
