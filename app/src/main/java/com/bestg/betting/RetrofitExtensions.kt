package com.bestg.betting

/**
 * RetrofitExtensions — Converts Retrofit Call<T> into suspend-friendly await().
 * Used by MainActivity for parallel API calls in lifecycleScope.launch.
 */

import kotlinx.coroutines.suspendCancellableCoroutine
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Converts a Retrofit Call<T> into a suspend function so it can be used
 * inside coroutines (async/await).
 */
suspend fun <T : Any> Call<T>.await(): T = suspendCancellableCoroutine { cont ->
    enqueue(object : Callback<T> {
        override fun onResponse(call: Call<T>, response: Response<T>) {
            if (response.isSuccessful) {
                val body = response.body()
                if (body != null) {
                    cont.resume(body)
                } else {
                    cont.resumeWithException(IllegalStateException("Empty body from ${call.request().url}"))
                }
            } else {
                cont.resumeWithException(IllegalStateException("HTTP ${response.code()} from ${call.request().url}"))
            }
        }

        override fun onFailure(call: Call<T>, t: Throwable) {
            if (cont.isActive) cont.resumeWithException(t)
        }
    })

    cont.invokeOnCancellation {
        try { cancel() } catch (_: Throwable) {}
    }
}
