package sl.gov.statistics.fieldmonitor.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.security.SecureRandom
import java.util.UUID
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec
import javax.inject.Inject
import javax.inject.Singleton

data class Session(
    val userId: Int,
    val username: String,
    val fullName: String,
    val districtIds: List<Int>,
    val lastOnlineLoginAt: Long,
)

/**
 * Keystore-backed storage for tokens, the offline PIN and the database
 * passphrase. Nothing here is readable without the device unlocked.
 */
@Singleton
class SessionStore @Inject constructor(@ApplicationContext context: Context) {

    private val prefs: SharedPreferences = EncryptedSharedPreferences.create(
        context,
        "fm_secure",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
    )

    private val _unlocked = MutableStateFlow(false)
    val unlocked: StateFlow<Boolean> = _unlocked

    val deviceId: String
        get() = prefs.getString(KEY_DEVICE_ID, null) ?: UUID.randomUUID().toString().also {
            prefs.edit { putString(KEY_DEVICE_ID, it) }
        }

    val accessToken: String? get() = prefs.getString(KEY_ACCESS, null)
    val refreshToken: String? get() = prefs.getString(KEY_REFRESH, null)

    val session: Session?
        get() {
            val userId = prefs.getInt(KEY_USER_ID, -1)
            if (userId < 0) return null
            return Session(
                userId = userId,
                username = prefs.getString(KEY_USERNAME, "") ?: "",
                fullName = prefs.getString(KEY_FULL_NAME, "") ?: "",
                districtIds = prefs.getString(KEY_DISTRICTS, "")!!.split(",").filter { it.isNotBlank() }.map { it.toInt() },
                lastOnlineLoginAt = prefs.getLong(KEY_LAST_LOGIN, 0L),
            )
        }

    val hasPin: Boolean get() = prefs.contains(KEY_PIN_HASH)

    /** Random passphrase for SQLCipher, generated once per install. */
    val databasePassphrase: ByteArray
        get() {
            val existing = prefs.getString(KEY_DB_PASS, null)
            if (existing != null) return existing.toByteArray()
            val bytes = ByteArray(32).also { SecureRandom().nextBytes(it) }
            val encoded = android.util.Base64.encodeToString(bytes, android.util.Base64.NO_WRAP)
            prefs.edit { putString(KEY_DB_PASS, encoded) }
            return encoded.toByteArray()
        }

    fun saveTokens(access: String, refresh: String) {
        prefs.edit { putString(KEY_ACCESS, access); putString(KEY_REFRESH, refresh) }
    }

    fun saveSession(userId: Int, username: String, fullName: String, districtIds: List<Int>) {
        prefs.edit {
            putInt(KEY_USER_ID, userId)
            putString(KEY_USERNAME, username)
            putString(KEY_FULL_NAME, fullName)
            putString(KEY_DISTRICTS, districtIds.joinToString(","))
            putLong(KEY_LAST_LOGIN, System.currentTimeMillis())
        }
        _unlocked.value = true
    }

    fun setPin(pin: String) {
        val salt = ByteArray(16).also { SecureRandom().nextBytes(it) }
        prefs.edit {
            putString(KEY_PIN_SALT, android.util.Base64.encodeToString(salt, android.util.Base64.NO_WRAP))
            putString(KEY_PIN_HASH, hashPin(pin, salt))
            putInt(KEY_PIN_FAILURES, 0)
        }
    }

    /** Returns true when the PIN matches; wipes the session after 5 failures. */
    fun verifyPin(pin: String): PinResult {
        val salt = android.util.Base64.decode(prefs.getString(KEY_PIN_SALT, "") ?: "", android.util.Base64.NO_WRAP)
        val expected = prefs.getString(KEY_PIN_HASH, null) ?: return PinResult.NoPin
        if (hashPin(pin, salt) == expected) {
            prefs.edit { putInt(KEY_PIN_FAILURES, 0) }
            _unlocked.value = true
            return PinResult.Ok
        }
        val failures = prefs.getInt(KEY_PIN_FAILURES, 0) + 1
        prefs.edit { putInt(KEY_PIN_FAILURES, failures) }
        return if (failures >= MAX_PIN_FAILURES) {
            clearSession()
            PinResult.Wiped
        } else {
            PinResult.Wrong(MAX_PIN_FAILURES - failures)
        }
    }

    fun lock() {
        _unlocked.value = false
    }

    /** Forget tokens and identity but keep the device id and DB passphrase. */
    fun clearSession() {
        prefs.edit {
            remove(KEY_ACCESS); remove(KEY_REFRESH); remove(KEY_USER_ID); remove(KEY_USERNAME)
            remove(KEY_FULL_NAME); remove(KEY_DISTRICTS); remove(KEY_PIN_HASH); remove(KEY_PIN_SALT)
            remove(KEY_PIN_FAILURES); remove(KEY_LAST_LOGIN)
        }
        _unlocked.value = false
    }

    private fun hashPin(pin: String, salt: ByteArray): String {
        val spec = PBEKeySpec(pin.toCharArray(), salt, 120_000, 256)
        val key = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        return android.util.Base64.encodeToString(key, android.util.Base64.NO_WRAP)
    }

    sealed interface PinResult {
        data object Ok : PinResult
        data object NoPin : PinResult
        data object Wiped : PinResult
        data class Wrong(val attemptsLeft: Int) : PinResult
    }

    companion object {
        private const val MAX_PIN_FAILURES = 5
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_ACCESS = "access_token"
        private const val KEY_REFRESH = "refresh_token"
        private const val KEY_USER_ID = "user_id"
        private const val KEY_USERNAME = "username"
        private const val KEY_FULL_NAME = "full_name"
        private const val KEY_DISTRICTS = "district_ids"
        private const val KEY_LAST_LOGIN = "last_online_login"
        private const val KEY_PIN_HASH = "pin_hash"
        private const val KEY_PIN_SALT = "pin_salt"
        private const val KEY_PIN_FAILURES = "pin_failures"
        private const val KEY_DB_PASS = "db_passphrase"
    }
}
