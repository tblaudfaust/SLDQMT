package sl.gov.statistics.fieldmonitor.data.repo

import androidx.room.withTransaction
import kotlinx.coroutines.flow.Flow
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.local.ActivityEntity
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.Counts
import sl.gov.statistics.fieldmonitor.data.local.ErrorEntity
import sl.gov.statistics.fieldmonitor.data.local.FollowUpEntity
import sl.gov.statistics.fieldmonitor.sync.SyncScheduler
import sl.gov.statistics.fieldmonitor.util.GpsFix
import sl.gov.statistics.fieldmonitor.util.Time
import java.time.LocalDate
import java.time.ZoneOffset
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

data class NewError(
    val districtId: Int,
    val districtCode: String,
    val teamId: Int?,
    val supervisorId: Int?,
    val supervisorName: String?,
    val enumeratorId: Int?,
    val enumeratorName: String?,
    val eaId: Int?,
    val categoryId: Int,
    val sourceId: Int?,
    val description: String,
    val dateReceived: String,
    val supportMethod: String,
    val actionTaken: String,
    val comments: String?,
    val gps: GpsFix?,
)

data class StatusUpdate(
    val newStatus: String,
    val actionTaken: String,
    val comments: String?,
    val method: String,
    val contacted: String?,
    val gps: GpsFix?,
)

@Singleton
class ErrorRepository @Inject constructor(
    private val db: AppDatabase,
    private val session: SessionStore,
    private val syncScheduler: SyncScheduler,
) {
    private val errors = db.errorDao()
    private val followUps = db.followUpDao()
    private val activity = db.activityDao()
    private val reference = db.referenceDao()

    fun observeAll(): Flow<List<ErrorEntity>> = errors.observeAll()
    fun observe(id: String): Flow<ErrorEntity?> = errors.observe(id)
    fun observeDue(): Flow<List<ErrorEntity>> = errors.observeDue()
    fun observeCounts(): Flow<Counts> = errors.observeCounts(Time.nowIso())
    fun observeFollowUps(errorId: String): Flow<List<FollowUpEntity>> = followUps.observeForError(errorId)
    fun observeActivity(errorId: String): Flow<List<ActivityEntity>> = activity.observeForError(errorId)
    fun observePendingCount(): Flow<Int> = errors.observePendingCount()
    fun observeRejected(): Flow<List<ErrorEntity>> = errors.observeRejected()

    private suspend fun nextFollowUpFor(lastActionIso: String): String {
        val interval = reference.setting("follow_up_interval_hours")?.toDoubleOrNull() ?: 4.0
        val qs = reference.setting("quiet_hours_start") ?: "20:00"
        val qe = reference.setting("quiet_hours_end") ?: "07:00"
        return Time.nextFollowUp(lastActionIso, interval, qs, qe)
    }

    private suspend fun nextDisplayId(districtCode: String): String {
        val yymm = LocalDate.now(ZoneOffset.UTC).let { String.format("%02d%02d", it.year % 100, it.monthValue) }
        val prefix = "FM-$districtCode-$yymm-"
        val last = errors.maxDisplayId(prefix)?.removePrefix(prefix)?.toIntOrNull() ?: 0
        return "$prefix${String.format("%04d", last + 1)}"
    }

    suspend fun create(input: NewError): String {
        val now = Time.nowIso()
        val id = UUID.randomUUID().toString()
        db.withTransaction {
            val entity = ErrorEntity(
                id = id,
                displayId = nextDisplayId(input.districtCode),
                districtId = input.districtId,
                teamId = input.teamId,
                supervisorId = input.supervisorId,
                supervisorName = input.supervisorName,
                enumeratorId = input.enumeratorId,
                enumeratorName = input.enumeratorName,
                eaId = input.eaId,
                categoryId = input.categoryId,
                sourceId = input.sourceId,
                description = input.description.trim(),
                dateReceived = input.dateReceived,
                supportMethod = input.supportMethod,
                actionTaken = input.actionTaken.trim(),
                comments = input.comments?.trim()?.ifBlank { null },
                status = "UNRESOLVED",
                resolvedAt = null,
                lastActionAt = now,
                nextFollowUpAt = nextFollowUpFor(now),
                lat = input.gps?.lat,
                lng = input.gps?.lng,
                accuracyM = input.gps?.accuracyM,
                gpsAt = input.gps?.atIso,
                clientCreatedAt = now,
                clientUpdatedAt = now,
                pending = true,
            )
            errors.upsert(entity)
            activity.insert(
                ActivityEntity(
                    id = UUID.randomUUID().toString(),
                    errorId = id,
                    previousStatus = null,
                    newStatus = "UNRESOLVED",
                    actionTaken = entity.actionTaken,
                    comments = entity.comments,
                    clientAt = now,
                )
            )
        }
        syncScheduler.syncSoon()
        return id
    }

    /** Record a follow-up and, optionally, a status change. Always appends history. */
    suspend fun update(errorId: String, u: StatusUpdate) {
        val now = Time.nowIso()
        db.withTransaction {
            val current = errors.get(errorId) ?: return@withTransaction
            val resolved = u.newStatus == "RESOLVED"
            errors.upsert(
                current.copy(
                    status = u.newStatus,
                    resolvedAt = if (resolved) now else null,
                    actionTaken = u.actionTaken.trim(),
                    comments = u.comments?.trim()?.ifBlank { null } ?: current.comments,
                    lastActionAt = now,
                    nextFollowUpAt = if (resolved) null else nextFollowUpFor(now),
                    lat = u.gps?.lat ?: current.lat,
                    lng = u.gps?.lng ?: current.lng,
                    accuracyM = u.gps?.accuracyM ?: current.accuracyM,
                    gpsAt = u.gps?.atIso ?: current.gpsAt,
                    clientUpdatedAt = now,
                    pending = true,
                    syncError = null,
                )
            )
            followUps.insert(
                FollowUpEntity(
                    id = UUID.randomUUID().toString(),
                    errorId = errorId,
                    at = now,
                    method = u.method,
                    contacted = u.contacted?.ifBlank { null } ?: current.supervisorName,
                    outcome = u.actionTaken.trim(),
                    comments = u.comments?.trim()?.ifBlank { null },
                    lat = u.gps?.lat,
                    lng = u.gps?.lng,
                    accuracyM = u.gps?.accuracyM,
                    gpsAt = u.gps?.atIso,
                    clientCreatedAt = now,
                )
            )
            activity.insert(
                ActivityEntity(
                    id = UUID.randomUUID().toString(),
                    errorId = errorId,
                    previousStatus = current.status,
                    newStatus = u.newStatus,
                    actionTaken = u.actionTaken.trim(),
                    comments = u.comments?.trim()?.ifBlank { null },
                    clientAt = now,
                )
            )
        }
        syncScheduler.syncSoon()
    }

    suspend fun editDetails(errorId: String, description: String, comments: String?, supervisorName: String?, enumeratorName: String?) {
        val now = Time.nowIso()
        db.withTransaction {
            val current = errors.get(errorId) ?: return@withTransaction
            errors.upsert(
                current.copy(
                    description = description.trim(),
                    comments = comments?.trim()?.ifBlank { null },
                    supervisorName = supervisorName ?: current.supervisorName,
                    enumeratorName = enumeratorName ?: current.enumeratorName,
                    clientUpdatedAt = now,
                    pending = true,
                    syncError = null,
                )
            )
            activity.insert(
                ActivityEntity(
                    id = UUID.randomUUID().toString(),
                    errorId = errorId,
                    previousStatus = current.status,
                    newStatus = current.status,
                    actionTaken = "Details edited",
                    comments = null,
                    clientAt = now,
                )
            )
        }
        syncScheduler.syncSoon()
    }

    suspend fun retry(errorId: String) {
        val current = errors.get(errorId) ?: return
        errors.upsert(current.copy(pending = true, syncError = null, clientUpdatedAt = Time.nowIso()))
        syncScheduler.syncNow()
    }
}
