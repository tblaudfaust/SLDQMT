package sl.gov.statistics.fieldmonitor.util

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Looper
import androidx.core.content.ContextCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.tasks.CancellationTokenSource
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import javax.inject.Inject
import javax.inject.Singleton
import kotlin.coroutines.resume

data class GpsFix(val lat: Double, val lng: Double, val accuracyM: Double, val atIso: String) {
    val good: Boolean get() = accuracyM <= 30.0
}

/**
 * One-shot fix: Fused Location first (fast, works without internet on a GPS tablet), then the plain
 * GPS provider for devices without Google services or whose fused provider has no location yet.
 */
@Singleton
class LocationHelper @Inject constructor(@ApplicationContext private val context: Context) {

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    suspend fun currentFix(timeoutMs: Long = 30_000): GpsFix? {
        if (!hasPermission()) return null
        return fused(timeoutMs / 2) ?: gpsProvider(timeoutMs / 2)
    }

    @SuppressLint("MissingPermission")
    private suspend fun fused(timeoutMs: Long): GpsFix? {
        val client = runCatching { LocationServices.getFusedLocationProviderClient(context) }.getOrNull() ?: return null
        val cts = CancellationTokenSource()
        return withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine { cont ->
                client.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, cts.token)
                    .addOnSuccessListener { loc -> cont.resume(loc?.toFix()) }
                    .addOnFailureListener { cont.resume(null) }
                cont.invokeOnCancellation { cts.cancel() }
            }
        }
    }

    @SuppressLint("MissingPermission")
    private suspend fun gpsProvider(timeoutMs: Long): GpsFix? {
        val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return null
        val provider = when {
            lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
            lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
            else -> return null
        }
        var listener: LocationListener? = null
        val fix = withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine { cont ->
                val l = object : LocationListener {
                    override fun onLocationChanged(location: Location) { if (cont.isActive) cont.resume(location.toFix()) }
                    @Deprecated("Deprecated in Java") override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
                    override fun onProviderEnabled(provider: String) {}
                    override fun onProviderDisabled(provider: String) { if (cont.isActive) cont.resume(null) }
                }
                listener = l
                lm.requestLocationUpdates(provider, 1000L, 0f, l, Looper.getMainLooper())
                cont.invokeOnCancellation { lm.removeUpdates(l) }
            }
        }
        listener?.let { lm.removeUpdates(it) }
        return fix
    }

    private fun Location.toFix() = GpsFix(latitude, longitude, if (hasAccuracy()) accuracy.toDouble() else 999.0, Time.nowIso())
}
