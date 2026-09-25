package sl.gov.statistics.fieldmonitor.util

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
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

/** One-shot high-accuracy fix through Fused Location; works without internet on a GPS tablet. */
@Singleton
class LocationHelper @Inject constructor(@ApplicationContext private val context: Context) {

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")
    suspend fun currentFix(timeoutMs: Long = 30_000): GpsFix? {
        if (!hasPermission()) return null
        val client = LocationServices.getFusedLocationProviderClient(context)
        val cts = CancellationTokenSource()
        return withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine { cont ->
                client.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, cts.token)
                    .addOnSuccessListener { loc ->
                        if (loc == null) cont.resume(null)
                        else cont.resume(GpsFix(loc.latitude, loc.longitude, loc.accuracy.toDouble(), Time.nowIso()))
                    }
                    .addOnFailureListener { cont.resume(null) }
                cont.invokeOnCancellation { cts.cancel() }
            }
        }
    }
}
