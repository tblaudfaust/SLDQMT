package sl.gov.statistics.fieldmonitor.sync

import androidx.room.withTransaction
import sl.gov.statistics.fieldmonitor.BuildConfig
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.local.ActivityEntity
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.ErrorEntity
import sl.gov.statistics.fieldmonitor.data.local.FollowUpEntity
import sl.gov.statistics.fieldmonitor.data.local.SyncStateEntity
import sl.gov.statistics.fieldmonitor.data.remote.ActivityDto
import sl.gov.statistics.fieldmonitor.data.remote.ApiService
import sl.gov.statistics.fieldmonitor.data.remote.ErrorDto
import sl.gov.statistics.fieldmonitor.data.remote.FollowUpDto
import sl.gov.statistics.fieldmonitor.data.remote.PushRequest
import sl.gov.statistics.fieldmonitor.data.repo.ReferenceRepository
import sl.gov.statistics.fieldmonitor.util.Time
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

sealed interface SyncOutcome {
    data class Ok(val pushed: Int, val pulled: Int, val rejected: Int) : SyncOutcome
    data object Offline : SyncOutcome
    data object NotSignedIn : SyncOutcome
    data object DeviceBlocked : SyncOutcome
    data class Failed(val message: String) : SyncOutcome
}

/**
 * Push pending records in batches, then pull the monitor's own records and
 * reference lists since the stored cursor. Local rows are only marked synced
 * when the server's receipt says applied or duplicate.
 */
@Singleton
class SyncEngine @Inject constructor(
    private val api: ApiService,
    private val db: AppDatabase,
    private val session: SessionStore,
    private val reference: ReferenceRepository,
    private val mefm: MefmSyncEngine,
) {
    private val errors = db.errorDao()
    private val followUps = db.followUpDao()
    private val activity = db.activityDao()
    private val state = db.syncStateDao()

    suspend fun run(): SyncOutcome {
        val current = session.session
        if (current == null || session.accessToken == null) return SyncOutcome.NotSignedIn
        if (current.isMe) return mefm.run()
        val deviceId = session.deviceId
        var pushed = 0
        var rejected = 0
        try {
            // ---- Push, in batches of up to 200 records -------------------------
            while (true) {
                val pendingErrors = errors.pending(100)
                val pendingFollowUps = followUps.pending(50)
                val pendingActivity = activity.pending(50)
                if (pendingErrors.isEmpty() && pendingFollowUps.isEmpty() && pendingActivity.isEmpty()) break
                val pendingTotal = errors.pendingCount() + followUps.pendingCount() + activity.pendingCount()
                val response = api.push(
                    PushRequest(
                        deviceId = deviceId,
                        appVersion = BuildConfig.VERSION_NAME,
                        pendingCount = pendingTotal,
                        errors = pendingErrors.map { it.toDto() },
                        followUps = pendingFollowUps.map { it.toDto() },
                        activity = pendingActivity.map { it.toDto() },
                    )
                )
                val byId = pendingErrors.associateBy { it.id }
                db.withTransaction {
                    for (r in response.receipts) {
                        val ok = r.result == "applied" || r.result == "duplicate"
                        when (r.kind) {
                            "error" -> if (ok) {
                                val local = byId[r.id]
                                if (local != null) errors.markSynced(r.id, local.clientUpdatedAt, r.version ?: local.serverVersion, r.nextFollowUpAt)
                            } else if (r.reason == "DELETED") {
                                followUps.deleteForError(r.id); activity.deleteForError(r.id); errors.deleteById(r.id)
                            } else errors.markRejected(r.id, r.reason ?: "rejected")
                            "follow_up" -> if (ok) followUps.markSynced(r.id) else followUps.markRejected(r.id, r.reason ?: "rejected")
                            "activity" -> if (ok) activity.markSynced(r.id) else activity.markRejected(r.id, r.reason ?: "rejected")
                        }
                    }
                }
                pushed += response.applied
                rejected += response.rejected
                if (response.receipts.isEmpty()) break
            }

            // ---- Pull ------------------------------------------------------------
            var current = state.get() ?: SyncStateEntity()
            var pulled = 0
            var more = true
            while (more) {
                val res = api.pull(deviceId, current.cursor, current.referenceVersion)
                if (res.pinReset) {
                    // An administrator reset this tablet's PIN: forget the PIN and the session, keep the
                    // records, and send the monitor back to the online sign-in (which clears the flag).
                    state.upsert(current.copy(lastSyncAt = Time.nowIso(), lastResult = "PIN_RESET", lastError = "The tablet PIN was reset by an administrator. Sign in again and choose a new PIN."))
                    session.clearSession()
                    return SyncOutcome.NotSignedIn
                }
                res.reference?.let { reference.apply(it) }
                reference.applySettings(res.settings)
                db.withTransaction {
                    for (dto in res.errors) {
                        if (dto.deletedAt != null) {
                            // Deleted on the dashboard: drop the local copy, even if it had unsynced edits
                            // (the server would reject them with DELETED anyway).
                            followUps.deleteForError(dto.id)
                            activity.deleteForError(dto.id)
                            errors.deleteById(dto.id)
                            continue
                        }
                        val local = errors.get(dto.id)
                        // Never overwrite a local change that has not been pushed yet.
                        if (local == null || (!local.pending && local.clientUpdatedAt <= dto.clientUpdatedAt)) {
                            errors.upsert(dto.toEntity(local))
                        }
                        followUps.insertAll(dto.followUps.map { it.toEntity() })
                        activity.insertAll(dto.activity.map { it.toEntity() })
                    }
                }
                pulled += res.errors.size
                more = res.more
                current = current.copy(cursor = res.cursor, referenceVersion = res.referenceVersion)
                state.upsert(current)
            }
            state.upsert(current.copy(lastSyncAt = Time.nowIso(), lastResult = "OK", lastError = null))
            return SyncOutcome.Ok(pushed, pulled, rejected)
        } catch (e: IOException) {
            recordFailure("offline")
            return SyncOutcome.Offline
        } catch (e: retrofit2.HttpException) {
            val body = runCatching { e.response()?.errorBody()?.string() }.getOrNull() ?: ""
            if (e.code() == 403 && body.contains("DEVICE_BLOCKED")) {
                wipeLocalData()
                return SyncOutcome.DeviceBlocked
            }
            if (e.code() == 401) {
                recordFailure("Sign in again")
                return SyncOutcome.NotSignedIn
            }
            recordFailure("HTTP ${e.code()}")
            return SyncOutcome.Failed("Server error ${e.code()}")
        } catch (e: Exception) {
            recordFailure(e.message ?: e.javaClass.simpleName)
            return SyncOutcome.Failed(e.message ?: "Unexpected error")
        }
    }

    private suspend fun recordFailure(message: String) {
        val current = state.get() ?: SyncStateEntity()
        state.upsert(current.copy(lastResult = "FAILED", lastError = message))
    }

    private suspend fun wipeLocalData() {
        db.clearAllTables()
        session.clearSession()
    }
}

// ---- Mapping --------------------------------------------------------------

fun ErrorEntity.toDto() = ErrorDto(
    id = id, displayId = displayId, districtId = districtId, teamId = teamId, supervisorId = supervisorId,
    supervisorName = supervisorName, enumeratorId = enumeratorId, enumeratorName = enumeratorName, eaId = eaId,
    categoryId = categoryId, sourceId = sourceId, description = description, dateReceived = dateReceived,
    supportMethod = supportMethod, actionTaken = actionTaken, comments = comments, status = status,
    resolvedAt = resolvedAt, lastActionAt = lastActionAt, nextFollowUpAt = nextFollowUpAt, lat = lat, lng = lng,
    accuracyM = accuracyM, gpsAt = gpsAt, clientCreatedAt = clientCreatedAt, clientUpdatedAt = clientUpdatedAt,
    version = serverVersion,
)

fun ErrorDto.toEntity(local: ErrorEntity?) = ErrorEntity(
    id = id, displayId = displayId, districtId = districtId, teamId = teamId, supervisorId = supervisorId,
    supervisorName = supervisorName, enumeratorId = enumeratorId, enumeratorName = enumeratorName, eaId = eaId,
    categoryId = categoryId, sourceId = sourceId, description = description, dateReceived = dateReceived,
    supportMethod = supportMethod, actionTaken = actionTaken, comments = comments, status = status,
    resolvedAt = resolvedAt, lastActionAt = lastActionAt, nextFollowUpAt = nextFollowUpAt, lat = lat, lng = lng,
    accuracyM = accuracyM, gpsAt = gpsAt, clientCreatedAt = clientCreatedAt, clientUpdatedAt = clientUpdatedAt,
    serverVersion = version, pending = false, syncError = local?.syncError,
)

fun FollowUpEntity.toDto() = FollowUpDto(id, errorId, at, method, contacted, outcome, comments, lat, lng, accuracyM, gpsAt, clientCreatedAt)
fun FollowUpDto.toEntity() = FollowUpEntity(id, errorId, at, method, contacted, outcome, comments, lat, lng, accuracyM, gpsAt, clientCreatedAt, pending = false)
fun ActivityEntity.toDto() = ActivityDto(id, errorId, previousStatus, newStatus, actionTaken, comments, clientAt)
fun ActivityDto.toEntity() = ActivityEntity(id, errorId, previousStatus, newStatus, actionTaken, comments, clientAt, pending = false)
