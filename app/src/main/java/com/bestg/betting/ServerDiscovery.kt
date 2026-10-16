package com.bestg.betting

/**
 * ServerDiscovery — mDNS discovery of the Flask backend on the local network.
 * Uses jmDNS to resolve _nflpredict._tcp.local.
 * Falls back to the saved server_ip if discovery times out.
 */

import android.content.Context
import android.net.wifi.WifiManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.InetAddress
import javax.jmdns.JmDNS
import javax.jmdns.ServiceEvent
import javax.jmdns.ServiceInfo
import javax.jmdns.ServiceListener

/**
 * Discovers the NFL Flask server on the local network via mDNS.
 * The server advertises itself as "_nflpredict._tcp.local." with a port.
 * Falls back to null if discovery fails (caller should use saved IP).
 */
object ServerDiscovery {

    private const val SERVICE_TYPE = "_nflpredict._tcp.local."

    /**
     * Attempts to discover the server. Returns "ip:port" or null on failure.
     * Runs on a background thread; do not call from UI thread.
     */
    suspend fun discover(context: Context, timeoutMs: Long = 5000): String? = withContext(Dispatchers.IO) {
        var resolved: String? = null
        var jmDNS: JmDNS? = null

        try {
            val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            val wifiLock = wifi?.createMulticastLock("nflpredict-mdns")?.apply {
                setReferenceCounted(true)
                acquire()
            }

            val inet = getLocalIpAddress(wifi)
            jmDNS = JmDNS.create(inet ?: InetAddress.getByName("0.0.0.0"))

            val listener = object : ServiceListener {
                override fun serviceAdded(event: ServiceEvent) {
                    jmDNS?.requestServiceInfo(event.type, event.name, 2000)
                }
                override fun serviceRemoved(event: ServiceEvent) {}
                override fun serviceResolved(event: ServiceEvent) {
                    val info: ServiceInfo = event.info
                    // jmDNS hostAddresses is already a List<String> of IPs
                    val host: String? = info.hostAddresses?.firstOrNull()
                    if (!host.isNullOrBlank()) {
                        resolved = "$host:${info.port}"
                        AppLog.i("mDNS resolved: $resolved")
                    }
                }
            }

            jmDNS.addServiceListener(SERVICE_TYPE, listener)

            val start = System.currentTimeMillis()
            while (resolved == null && System.currentTimeMillis() - start < timeoutMs) {
                Thread.sleep(150)
            }

            jmDNS.removeServiceListener(SERVICE_TYPE, listener)
            jmDNS.close()
            wifiLock?.release()
        } catch (e: Exception) {
            AppLog.w("mDNS discovery failed: ${e.message}")
            try { jmDNS?.close() } catch (_: Throwable) {}
        }

        resolved
    }

    private fun getLocalIpAddress(wifi: WifiManager?): InetAddress? {
        return try {
            val ipInt = wifi?.connectionInfo?.ipAddress ?: return null
            if (ipInt == 0) return null
            val ip = String.format(
                "%d.%d.%d.%d",
                ipInt and 0xff,
                ipInt shr 8 and 0xff,
                ipInt shr 16 and 0xff,
                ipInt shr 24 and 0xff
            )
            InetAddress.getByName(ip)
        } catch (e: Exception) {
            null
        }
    }
}
