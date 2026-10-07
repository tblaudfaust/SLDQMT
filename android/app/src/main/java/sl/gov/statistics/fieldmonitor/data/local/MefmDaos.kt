package sl.gov.statistics.fieldmonitor.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

data class MefmCounts(val drafts: Int, val waiting: Int, val rejected: Int, val synced: Int)

@Dao
interface MefmDao {
    // ---- frame ----
    @Query("SELECT * FROM mefm_district ORDER BY name") fun observeDistricts(): Flow<List<MefmDistrictEntity>>
    @Query("SELECT * FROM mefm_chiefdom ORDER BY name") fun observeChiefdoms(): Flow<List<MefmChiefdomEntity>>
    @Query("SELECT * FROM mefm_section WHERE chiefdomId = :chiefdomId ORDER BY name") fun observeSections(chiefdomId: Int): Flow<List<MefmSectionEntity>>
    @Query("SELECT * FROM mefm_ea WHERE popEaCode = :code LIMIT 1") suspend fun eaByCode(code: String): MefmEaEntity?
    @Query("SELECT * FROM mefm_ea WHERE popEaCode LIKE :prefix || '%' ORDER BY popEaCode LIMIT :limit") suspend fun easStartingWith(prefix: String, limit: Int = 8): List<MefmEaEntity>
    @Query("SELECT * FROM mefm_team WHERE id = :id") suspend fun team(id: Int): MefmTeamEntity?
    @Query("SELECT * FROM mefm_chiefdom WHERE code = :code") suspend fun chiefdomByCode(code: String): MefmChiefdomEntity?
    @Query("SELECT * FROM mefm_section WHERE code = :code") suspend fun sectionByCode(code: String): MefmSectionEntity?
    @Query("SELECT COUNT(*) FROM mefm_ea") fun observeEaCount(): Flow<Int>

    @Upsert suspend fun upsertDistricts(items: List<MefmDistrictEntity>)
    @Upsert suspend fun upsertChiefdoms(items: List<MefmChiefdomEntity>)
    @Upsert suspend fun upsertSections(items: List<MefmSectionEntity>)
    @Upsert suspend fun upsertTeams(items: List<MefmTeamEntity>)
    @Upsert suspend fun upsertEas(items: List<MefmEaEntity>)
    @Query("DELETE FROM mefm_district") suspend fun clearDistricts()
    @Query("DELETE FROM mefm_chiefdom") suspend fun clearChiefdoms()
    @Query("DELETE FROM mefm_section") suspend fun clearSections()
    @Query("DELETE FROM mefm_team") suspend fun clearTeams()
    @Query("DELETE FROM mefm_ea") suspend fun clearEas()

    @Transaction
    suspend fun replaceFrame(
        districts: List<MefmDistrictEntity>, chiefdoms: List<MefmChiefdomEntity>, sections: List<MefmSectionEntity>,
        teams: List<MefmTeamEntity>, eas: List<MefmEaEntity>,
    ) {
        clearDistricts(); clearChiefdoms(); clearSections(); clearTeams(); clearEas()
        upsertDistricts(districts); upsertChiefdoms(chiefdoms); upsertSections(sections); upsertTeams(teams); upsertEas(eas)
    }

    // ---- form spec ----
    @Query("SELECT * FROM mefm_form WHERE id = 1") suspend fun form(): MefmFormEntity?
    @Query("SELECT * FROM mefm_form WHERE id = 1") fun observeForm(): Flow<MefmFormEntity?>
    @Upsert suspend fun upsertForm(form: MefmFormEntity)

    // ---- visits ----
    @Upsert suspend fun upsertVisit(v: MefmVisitEntity)
    @Query("SELECT * FROM mefm_visit WHERE id = :id") suspend fun visit(id: String): MefmVisitEntity?
    @Query("SELECT * FROM mefm_visit WHERE id = :id") fun observeVisit(id: String): Flow<MefmVisitEntity?>
    @Query("SELECT * FROM mefm_visit ORDER BY visitDate DESC, clientUpdatedAt DESC") fun observeVisits(): Flow<List<MefmVisitEntity>>
    @Query("SELECT * FROM mefm_visit WHERE pending = 1 AND complete = 1 ORDER BY clientUpdatedAt ASC LIMIT :limit") suspend fun pendingVisits(limit: Int): List<MefmVisitEntity>
    @Query("SELECT COUNT(*) FROM mefm_visit WHERE pending = 1 AND complete = 1") suspend fun pendingVisitCount(): Int
    @Query("SELECT COUNT(*) FROM mefm_visit WHERE pending = 1 AND complete = 1") fun observePendingVisitCount(): Flow<Int>
    @Query(
        "SELECT COALESCE(SUM(CASE WHEN complete = 0 THEN 1 ELSE 0 END), 0) AS drafts, " +
            "COALESCE(SUM(CASE WHEN complete = 1 AND pending = 1 THEN 1 ELSE 0 END), 0) AS waiting, " +
            "COALESCE(SUM(CASE WHEN syncError IS NOT NULL THEN 1 ELSE 0 END), 0) AS rejected, " +
            "COALESCE(SUM(CASE WHEN complete = 1 AND pending = 0 AND syncError IS NULL THEN 1 ELSE 0 END), 0) AS synced FROM mefm_visit"
    )
    fun observeCounts(): Flow<MefmCounts>
    @Query("UPDATE mefm_visit SET pending = 0, syncError = NULL, serverVersion = :version, serverStatus = 'SUBMITTED', flags = :flags WHERE id = :id AND clientUpdatedAt = :clientUpdatedAt")
    suspend fun markVisitSynced(id: String, clientUpdatedAt: String, version: Int, flags: String)
    @Query("UPDATE mefm_visit SET pending = 0, syncError = :error WHERE id = :id") suspend fun markVisitRejected(id: String, error: String)
    @Query("UPDATE mefm_visit SET serverStatus = :status, serverVersion = :version, flags = :flags, openIssues = :openIssues, reviewNote = :note WHERE id = :id AND pending = 0")
    suspend fun applyServerState(id: String, status: String, version: Int, flags: String, openIssues: Int, note: String?)
    @Query("DELETE FROM mefm_visit WHERE id = :id") suspend fun deleteVisit(id: String)

    // ---- check-ins ----
    @Insert(onConflict = OnConflictStrategy.IGNORE) suspend fun insertCheckin(c: MefmCheckinEntity)
    @Query("SELECT * FROM mefm_checkin ORDER BY at DESC LIMIT 50") fun observeCheckins(): Flow<List<MefmCheckinEntity>>
    @Query("SELECT * FROM mefm_checkin WHERE pending = 1 ORDER BY at ASC LIMIT :limit") suspend fun pendingCheckins(limit: Int): List<MefmCheckinEntity>
    @Query("SELECT COUNT(*) FROM mefm_checkin WHERE pending = 1") suspend fun pendingCheckinCount(): Int
    @Query("SELECT COUNT(*) FROM mefm_checkin WHERE pending = 1") fun observePendingCheckinCount(): Flow<Int>
    @Query("UPDATE mefm_checkin SET pending = 0, syncError = NULL, flags = :flags WHERE id = :id") suspend fun markCheckinSynced(id: String, flags: String)
    @Query("UPDATE mefm_checkin SET pending = 0, syncError = :error WHERE id = :id") suspend fun markCheckinRejected(id: String, error: String)

    // ---- sync state ----
    @Query("SELECT * FROM mefm_sync_state WHERE id = 1") suspend fun syncState(): MefmSyncStateEntity?
    @Upsert suspend fun upsertSyncState(s: MefmSyncStateEntity)
}
