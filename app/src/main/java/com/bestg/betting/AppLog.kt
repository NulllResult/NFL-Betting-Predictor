package com.bestg.betting

/**
 * AppLog — Centralized logging wrapper.
 * Filter device logs with: adb logcat -s NFLPredict
 */

import android.util.Log

/**
 * Simple wrapper around android.util.Log with a consistent tag
 * so we can diagnose field issues without hunting for scattered Log calls.
 */
object AppLog {
    private const val TAG = "NFLPredict"

    fun d(msg: String) = Log.d(TAG, msg)
    fun i(msg: String) = Log.i(TAG, msg)
    fun w(msg: String) = Log.w(TAG, msg)

    fun e(msg: String, t: Throwable? = null) {
        if (t != null) Log.e(TAG, msg, t) else Log.e(TAG, msg)
    }
}
