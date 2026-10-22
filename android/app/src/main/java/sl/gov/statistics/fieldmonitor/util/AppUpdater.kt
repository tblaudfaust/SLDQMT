package sl.gov.statistics.fieldmonitor.util

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import sl.gov.statistics.fieldmonitor.BuildConfig
import sl.gov.statistics.fieldmonitor.data.remote.ApiService
import java.io.File
import java.net.URI
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Keeps the tablet on the latest app: asks the server (public endpoint, no sign-in needed) for the
 * version it serves, and when it is newer than this build downloads the APK with the system
 * DownloadManager and opens the package installer. Checked when the home screen opens and when the
 * monitor taps "Sync now"; nothing happens without network.
 */
data class UpdateInfo(val versionCode: Int, val versionName: String, val notes: String, val url: String, val sizeBytes: Long?)

sealed class UpdateState {
    data object Idle : UpdateState()
    data class Available(val info: UpdateInfo) : UpdateState()
    data class Downloading(val info: UpdateInfo, val downloaded: Long, val total: Long) : UpdateState()
    data class Ready(val info: UpdateInfo, val file: File) : UpdateState()
    data class NeedPermission(val info: UpdateInfo, val file: File) : UpdateState()
    data class Failed(val info: UpdateInfo, val message: String) : UpdateState()
}

@Singleton
class AppUpdater @Inject constructor(
    @ApplicationContext private val context: Context,
    private val api: ApiService,
) {
    private val _state = MutableStateFlow<UpdateState>(UpdateState.Idle)
    val state: StateFlow<UpdateState> = _state
    private var lastCheckAt = 0L

    /** Ask the server; keeps the current state when offline or when already downloading. */
    suspend fun check(force: Boolean = false) {
        val now = System.currentTimeMillis()
        if (!force && now - lastCheckAt < 10 * 60 * 1000) return
        val current = _state.value
        if (current is UpdateState.Downloading) return
        lastCheckAt = now
        val latest = runCatching { api.appVersion()["fieldmonitor"] }.getOrNull() ?: return
        if (!latest.available || latest.versionCode <= BuildConfig.VERSION_CODE) {
            if (current !is UpdateState.Idle) _state.value = UpdateState.Idle
            return
        }
        val url = absolute(latest.downloadUrl)
        val info = UpdateInfo(latest.versionCode, latest.versionName, latest.notes ?: "", url, latest.sizeBytes)
        // a finished download of this very version is still ready to install
        val ready = current as? UpdateState.Ready
        _state.value = if (ready != null && ready.info.versionCode == info.versionCode && ready.file.exists()) ready else UpdateState.Available(info)
    }

    /** Download the APK into the app's own files folder and hand it to the installer when complete. */
    suspend fun download(info: UpdateInfo) {
        val dir = context.getExternalFilesDir("updates") ?: context.filesDir
        val file = File(dir, "SLPHC-FieldMonitor.apk")
        file.delete()
        val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val request = DownloadManager.Request(Uri.parse(info.url))
            .setTitle("SLPHC Field Monitor ${info.versionName}")
            .setDescription("Downloading the update")
            .setMimeType("application/vnd.android.package-archive")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE)
            .setDestinationInExternalFilesDir(context, "updates", "SLPHC-FieldMonitor.apk")
        val id = runCatching { dm.enqueue(request) }.getOrElse { _state.value = UpdateState.Failed(info, "Could not start the download: ${it.message}"); return }
        _state.value = UpdateState.Downloading(info, 0, info.sizeBytes ?: -1)
        withContext(Dispatchers.IO) {
            while (true) {
                delay(500)
                val c = dm.query(DownloadManager.Query().setFilterById(id)) ?: break
                c.use {
                    if (!it.moveToFirst()) { _state.value = UpdateState.Failed(info, "The download was cancelled"); return@withContext }
                    val status = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    val done = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                    val total = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                    when (status) {
                        DownloadManager.STATUS_SUCCESSFUL -> { _state.value = UpdateState.Ready(info, file); return@withContext }
                        DownloadManager.STATUS_FAILED -> {
                            val reason = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
                            _state.value = UpdateState.Failed(info, "Download failed (code $reason). Check the connection and try again."); return@withContext
                        }
                        else -> _state.value = UpdateState.Downloading(info, done, total)
                    }
                }
            }
        }
    }

    /** Open the package installer; on first use Android asks to allow installs from this app. */
    fun install(info: UpdateInfo, file: File) {
        if (!file.exists()) { _state.value = UpdateState.Available(info); return }
        if (Build.VERSION.SDK_INT >= 26 && !context.packageManager.canRequestPackageInstalls()) {
            _state.value = UpdateState.NeedPermission(info, file)
            val settings = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            runCatching { context.startActivity(settings) }
            return
        }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        runCatching { context.startActivity(intent) }.onFailure { _state.value = UpdateState.Failed(info, "Could not open the installer: ${it.message}") }
    }

    fun dismiss() { _state.value = UpdateState.Idle }

    /** "/api/v1/public/app/x.apk" -> "https://host/api/v1/public/app/x.apk" using the server the app talks to. */
    private fun absolute(path: String): String {
        if (path.startsWith("http")) return path
        val base = URI(BuildConfig.API_BASE_URL)
        val port = if (base.port == -1) "" else ":${base.port}"
        return "${base.scheme}://${base.host}$port$path"
    }
}
