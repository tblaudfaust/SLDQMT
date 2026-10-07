package sl.gov.statistics.fieldmonitor.sync

import androidx.room.withTransaction
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import sl.gov.statistics.fieldmonitor.BuildConfig
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.MefmChiefdomEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmDistrictEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmEaEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmFormEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmSectionEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmSyncStateEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmTeamEntity
import sl.gov.statistics.fieldmonitor.data.local.SettingEntity
import sl.gov.statistics.fieldmonitor.data.local.SyncStateEntity
import sl.gov.statistics.fieldmonitor.data.remote.ApiService
import sl.gov.statistics.fieldmonitor.data.remote.GpsDto
import sl.gov.statistics.fieldmonitor.data.remote.MefmCheckinDto
import sl.gov.statistics.fieldmonitor.data.remote.MefmPushRequest
import sl.gov.statistics.fieldmonitor.data.remote.MefmVisitDto
import sl.gov.statistics.fieldmonitor.util.Time
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Sync for District M&E Officers: push finished forms and check-ins, then pull the questionnaire,
 * the district frame and the state of the forms the server holds. A form is marked uploaded only
 * when the receipt says applied or duplicate; a rejected form keeps the server's messages so the
 * officer can correct and resend it.
 */
@Singleton
class MefmSyncEngine @Inject constructor(
    private val api: ApiService,
    private val db: AppDatabase,
    private val session: SessionStore,
    private val json: Json,
) {
    private val dao = db.mefmDao()
    private val state = db.syncStateDao()

    suspend fun run(): SyncOutcome {
        if (session.session == null || session.accessToken == null) return SyncOutcome.NotSignedIn
        val deviceId = session.deviceId
        var pushed = 0
        var rejected = 0
        try {
            while (true) {
                val visits = dao.pendingVisits(50)
                val checkins = dao.pendingCheckins(100)
                if (visits.isEmpty() && checkins.isEmpty()) break
                val res = api.mefmPush(
                    MefmPushRequest(
                        deviceId = deviceId, appVersion = BuildConfig.VERSION_NAME, pendingCount = dao.pendingVisitCount() + dao.pendingCheckinCount(),
                        visits = visits.map { v ->
                            MefmVisitDto(
                                id = v.id, popEaCode = v.popEaCode, answers = runCatching { json.decodeFromString(JsonObject.serializer(), v.answers) }.getOrDefault(JsonObject(emptyMap())),
                                gps = GpsDto(v.lat ?: 0.0, v.lng ?: 0.0, v.accuracyM, v.gpsAt), clientCreatedAt = v.clientCreatedAt, clientUpdatedAt = v.clientUpdatedAt,
                            )
                        },
                        checkins = checkins.map { c -> MefmCheckinDto(c.id, c.chiefdomCode, c.sectionCode, c.note, GpsDto(c.lat, c.lng, c.accuracyM, c.at), c.at) },
                    )
                )
                val byId = visits.associateBy { it.id }
                db.withTransaction {
                    for (r in res.receipts) {
                        val ok = r.result == "applied" || r.result == "duplicate"
                        val flags = r.flags.joinToString(",")
                        when (r.kind) {
                            "visit" -> if (ok) {
                                byId[r.id]?.let { dao.markVisitSynced(r.id, it.clientUpdatedAt, r.version ?: it.serverVersion, flags) }
                            } else {
                                val message = when (r.reason) {
                                    "INVALID" -> r.errors.joinToString("\n")
                                    "UNKNOWN_EA" -> "No EA with this 10-digit code in the frame"
                                    "NOT_IN_SCOPE" -> "This EA is outside your district"
                                    "DELETED" -> "This form was deleted on the dashboard"
                                    else -> r.reason ?: "Rejected by the server"
                                }
                                dao.markVisitRejected(r.id, message)
                            }
                            "checkin" -> if (ok) dao.markCheckinSynced(r.id, flags) else dao.markCheckinRejected(r.id, r.reason ?: "rejected")
                        }
                    }
                }
                pushed += res.applied
                rejected += res.rejected
                if (res.receipts.isEmpty()) break
            }

            var mine = dao.syncState() ?: MefmSyncStateEntity()
            var pulled = 0
            var more = true
            while (more) {
                val res = api.mefmPull(deviceId, mine.cursor, mine.frameVersion, mine.formVersion)
                if (res.pinReset) {
                    val shared = state.get() ?: SyncStateEntity()
                    state.upsert(shared.copy(lastSyncAt = Time.nowIso(), lastResult = "PIN_RESET", lastError = "The PIN was reset by an administrator. Sign in again and choose a new PIN."))
                    session.clearSession()
                    return SyncOutcome.NotSignedIn
                }
                res.form?.let { dao.upsertForm(MefmFormEntity(version = res.formVersion, json = json.encodeToString(JsonObject.serializer(), it))) }
                res.frame?.let { f ->
                    dao.replaceFrame(
                        districts = f.districts.map { MefmDistrictEntity(it.id, it.code, it.name, it.region) },
                        chiefdoms = f.chiefdoms.map { MefmChiefdomEntity(it.id, it.districtId, it.code, it.name) },
                        sections = f.sections.map { MefmSectionEntity(it.id, it.districtId, it.chiefdomId, it.code, it.name) },
                        teams = f.teams.map { MefmTeamEntity(it.id, it.districtId, it.code, it.name, it.chiefdom, it.supervisor, it.enumerators.joinToString(" | ")) },
                        eas = f.eas.map { MefmEaEntity(it.id, it.teamId, it.code, it.name, it.locality, it.popEaCode, it.chiefdomCode, it.sectionCode, it.locStatus, it.expectedHouseholds, it.lat, it.lng) },
                    )
                }
                db.referenceDao().upsertSettings(res.settings.map { SettingEntity(it.key, it.value) })
                db.withTransaction {
                    for (v in res.visits) {
                        if (v.deleted) dao.markVisitRejected(v.id, "This form was deleted on the dashboard")
                        else dao.applyServerState(v.id, v.status, v.version, v.flags.joinToString(","), v.openIssues, v.reviewNote)
                    }
                }
                pulled += res.visits.size
                more = res.more
                mine = mine.copy(cursor = res.cursor, frameVersion = res.frameVersion, formVersion = res.formVersion)
                dao.upsertSyncState(mine)
            }
            val shared = state.get() ?: SyncStateEntity()
            state.upsert(shared.copy(lastSyncAt = Time.nowIso(), lastResult = "OK", lastError = null))
            return SyncOutcome.Ok(pushed, pulled, rejected)
        } catch (e: IOException) {
            recordFailure("offline")
            return SyncOutcome.Offline
        } catch (e: retrofit2.HttpException) {
            val body = runCatching { e.response()?.errorBody()?.string() }.getOrNull() ?: ""
            if (e.code() == 403 && body.contains("DEVICE_BLOCKED")) {
                db.clearAllTables()
                session.clearSession()
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
}
