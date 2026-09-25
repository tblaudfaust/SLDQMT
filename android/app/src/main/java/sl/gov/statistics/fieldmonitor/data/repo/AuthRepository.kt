package sl.gov.statistics.fieldmonitor.data.repo

import android.os.Build
import sl.gov.statistics.fieldmonitor.BuildConfig
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.SettingEntity
import sl.gov.statistics.fieldmonitor.data.remote.ApiService
import sl.gov.statistics.fieldmonitor.data.remote.DeviceRegister
import sl.gov.statistics.fieldmonitor.data.remote.LoginRequest
import sl.gov.statistics.fieldmonitor.sync.SyncScheduler
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

sealed interface LoginResult {
    data object Ok : LoginResult
    data class Failed(val message: String) : LoginResult
    data object Offline : LoginResult
}

@Singleton
class AuthRepository @Inject constructor(
    private val api: ApiService,
    private val session: SessionStore,
    private val db: AppDatabase,
    private val syncScheduler: SyncScheduler,
) {
    val hasSession: Boolean get() = session.session != null
    val hasPin: Boolean get() = session.hasPin
    val fullName: String get() = session.session?.fullName ?: ""

    suspend fun login(username: String, password: String): LoginResult {
        val deviceId = session.deviceId
        val pair = try {
            api.login(LoginRequest(username.trim().lowercase(), password, deviceId))
        } catch (e: IOException) {
            return LoginResult.Offline
        } catch (e: retrofit2.HttpException) {
            return LoginResult.Failed(
                when (e.code()) {
                    401 -> "Invalid username or password"
                    423 -> "Account locked after too many attempts. Try again in 15 minutes."
                    else -> "Login failed (${e.code()})"
                }
            )
        }
        if (pair.user.role != "FIELD_MONITOR") {
            return LoginResult.Failed("Only Field Monitor accounts can use the tablet app")
        }
        session.saveTokens(pair.accessToken, pair.refreshToken)
        session.saveSession(pair.user.id, pair.user.username, pair.user.fullName, pair.user.districtIds ?: emptyList())
        db.referenceDao().upsertSettings(pair.settings.map { SettingEntity(it.key, it.value) })
        try {
            api.registerDevice(DeviceRegister(deviceId, "${Build.MANUFACTURER} ${Build.MODEL}", Build.VERSION.RELEASE, BuildConfig.VERSION_NAME))
        } catch (e: retrofit2.HttpException) {
            if (e.code() == 403) {
                session.clearSession()
                return LoginResult.Failed("This tablet has been blocked by an administrator")
            }
        } catch (_: IOException) {
            // Registration is retried at the next sync.
        }
        syncScheduler.syncNow()
        return LoginResult.Ok
    }

    fun setPin(pin: String) = session.setPin(pin)
    fun unlockWithPin(pin: String) = session.verifyPin(pin)
    fun lock() = session.lock()

    suspend fun logout() {
        session.clearSession()
    }

    /** Offline sessions expire after `offline_days` (server setting, default 14). */
    suspend fun offlineSessionExpired(): Boolean {
        val s = session.session ?: return true
        val days = db.referenceDao().setting("offline_days")?.toIntOrNull() ?: 14
        return System.currentTimeMillis() - s.lastOnlineLoginAt > days * 86_400_000L
    }
}
