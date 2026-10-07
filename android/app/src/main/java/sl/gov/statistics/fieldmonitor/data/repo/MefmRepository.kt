package sl.gov.statistics.fieldmonitor.data.repo

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.MefmCheckinEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmChiefdomEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmCounts
import sl.gov.statistics.fieldmonitor.data.local.MefmDistrictEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmEaEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmSectionEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmTeamEntity
import sl.gov.statistics.fieldmonitor.data.local.MefmVisitEntity
import sl.gov.statistics.fieldmonitor.mefm.FormSpec
import sl.gov.statistics.fieldmonitor.sync.SyncScheduler
import sl.gov.statistics.fieldmonitor.util.GpsFix
import sl.gov.statistics.fieldmonitor.util.Time
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/** An EA found by its 10-digit code, with what the frame knows about it (shown on the form, used to pre-fill). */
data class EaLookup(val ea: MefmEaEntity, val team: MefmTeamEntity?, val chiefdom: MefmChiefdomEntity?, val section: MefmSectionEntity?) {
    val label: String get() = "${ea.popEaCode} · ${ea.name ?: ea.code}${ea.locality?.let { " ($it)" } ?: ""}"
}

@Singleton
class MefmRepository @Inject constructor(private val db: AppDatabase, private val json: Json, private val scheduler: SyncScheduler) {
    private val dao = db.mefmDao()

    fun districts(): Flow<List<MefmDistrictEntity>> = dao.observeDistricts()
    fun chiefdoms(): Flow<List<MefmChiefdomEntity>> = dao.observeChiefdoms()
    fun sections(chiefdomId: Int): Flow<List<MefmSectionEntity>> = dao.observeSections(chiefdomId)
    fun eaCount(): Flow<Int> = dao.observeEaCount()
    fun visits(): Flow<List<MefmVisitEntity>> = dao.observeVisits()
    fun visit(id: String): Flow<MefmVisitEntity?> = dao.observeVisit(id)
    fun counts(): Flow<MefmCounts> = dao.observeCounts()
    fun checkins(): Flow<List<MefmCheckinEntity>> = dao.observeCheckins()
    fun pendingCheckins(): Flow<Int> = dao.observePendingCheckinCount()
    fun pendingVisits(): Flow<Int> = dao.observePendingVisitCount()

    /** The questionnaire, parsed; null until the first sync has brought it. */
    fun form(): Flow<FormSpec?> = dao.observeForm().map { row -> row?.let { runCatching { json.decodeFromString<FormSpec>(it.json) }.getOrNull() } }
    suspend fun formNow(): FormSpec? = dao.form()?.let { runCatching { json.decodeFromString<FormSpec>(it.json) }.getOrNull() }

    suspend fun lookupEa(code: String): EaLookup? {
        val digits = code.filter(Char::isDigit)
        if (digits.length != 10) return null
        val ea = dao.eaByCode(digits) ?: return null
        return EaLookup(ea, dao.team(ea.teamId), ea.chiefdomCode?.let { dao.chiefdomByCode(it) }, ea.sectionCode?.let { dao.sectionByCode(it) })
    }

    suspend fun suggestEas(prefix: String): List<MefmEaEntity> {
        val digits = prefix.filter(Char::isDigit)
        return if (digits.length < 3) emptyList() else dao.easStartingWith(digits)
    }

    suspend fun get(id: String): MefmVisitEntity? = dao.visit(id)

    suspend fun newDraft(): String {
        val id = UUID.randomUUID().toString()
        val now = Time.nowIso()
        dao.upsertVisit(MefmVisitEntity(id = id, popEaCode = "", eaLabel = "", phase = "", visitDate = Time.today(), answers = "{}", lat = null, lng = null, accuracyM = null, gpsAt = null, clientCreatedAt = now, clientUpdatedAt = now))
        return id
    }

    /** Save the current answers (draft or finished). A finished form is queued for upload. */
    suspend fun save(id: String, answers: JsonObject, eaLabel: String, gps: GpsFix?, complete: Boolean) {
        val existing = dao.visit(id) ?: return
        val now = Time.nowIso()
        val a = answers as Map<String, kotlinx.serialization.json.JsonElement>
        val phase = (a["A12"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: ""
        val date = (a["A2"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: existing.visitDate
        val code = (a["A8"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: ""
        dao.upsertVisit(
            existing.copy(
                popEaCode = code.filter(Char::isDigit), eaLabel = eaLabel, phase = phase, visitDate = date, answers = json.encodeToString(JsonObject.serializer(), answers),
                lat = gps?.lat ?: existing.lat, lng = gps?.lng ?: existing.lng, accuracyM = gps?.accuracyM ?: existing.accuracyM, gpsAt = gps?.atIso ?: existing.gpsAt,
                complete = complete, pending = complete, syncError = if (complete) null else existing.syncError, clientUpdatedAt = now,
            )
        )
        if (complete) scheduler.syncSoon()
    }

    suspend fun delete(id: String) = dao.deleteVisit(id)

    suspend fun checkin(chiefdom: MefmChiefdomEntity, section: MefmSectionEntity?, note: String?, gps: GpsFix) {
        dao.insertCheckin(
            MefmCheckinEntity(
                id = UUID.randomUUID().toString(), chiefdomCode = chiefdom.code, sectionCode = section?.code,
                label = if (section != null) "${section.name}, ${chiefdom.name}" else chiefdom.name, note = note?.ifBlank { null },
                lat = gps.lat, lng = gps.lng, accuracyM = gps.accuracyM, at = gps.atIso,
            )
        )
        scheduler.syncSoon()
    }
}
