package sl.gov.statistics.fieldmonitor.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Update
import androidx.room.Upsert
import kotlinx.coroutines.flow.Flow

data class Counts(val total: Int, val resolved: Int, val unresolved: Int, val overdue: Int)

@Dao
interface ErrorDao {
    @Upsert
    suspend fun upsert(error: ErrorEntity)

    @Upsert
    suspend fun upsertAll(errors: List<ErrorEntity>)

    @Query("SELECT * FROM error WHERE id = :id")
    suspend fun get(id: String): ErrorEntity?

    @Query("SELECT * FROM error WHERE id = :id")
    fun observe(id: String): Flow<ErrorEntity?>

    @Query("SELECT * FROM error ORDER BY lastActionAt DESC")
    fun observeAll(): Flow<List<ErrorEntity>>

    @Query(
        "SELECT * FROM error WHERE status = 'UNRESOLVED' AND nextFollowUpAt IS NOT NULL " +
            "ORDER BY nextFollowUpAt ASC"
    )
    fun observeDue(): Flow<List<ErrorEntity>>

    @Query(
        "SELECT COUNT(*) FROM error WHERE status = 'UNRESOLVED' AND nextFollowUpAt IS NOT NULL AND nextFollowUpAt < :nowIso"
    )
    suspend fun countOverdue(nowIso: String): Int

    @Query(
        "SELECT COUNT(*) AS total, " +
            "COALESCE(SUM(CASE WHEN status = 'RESOLVED' THEN 1 ELSE 0 END), 0) AS resolved, " +
            "COALESCE(SUM(CASE WHEN status = 'UNRESOLVED' THEN 1 ELSE 0 END), 0) AS unresolved, " +
            "COALESCE(SUM(CASE WHEN status = 'UNRESOLVED' AND nextFollowUpAt IS NOT NULL AND nextFollowUpAt < :nowIso THEN 1 ELSE 0 END), 0) AS overdue " +
            "FROM error"
    )
    fun observeCounts(nowIso: String): Flow<Counts>

    @Query("SELECT * FROM error WHERE pending = 1 ORDER BY clientUpdatedAt ASC LIMIT :limit")
    suspend fun pending(limit: Int): List<ErrorEntity>

    @Query("SELECT COUNT(*) FROM error WHERE pending = 1")
    fun observePendingCount(): Flow<Int>

    @Query("SELECT COUNT(*) FROM error WHERE pending = 1")
    suspend fun pendingCount(): Int

    @Query("UPDATE error SET pending = 0, syncError = NULL, serverVersion = :version, nextFollowUpAt = COALESCE(:nextFollowUpAt, nextFollowUpAt) WHERE id = :id AND clientUpdatedAt = :clientUpdatedAt")
    suspend fun markSynced(id: String, clientUpdatedAt: String, version: Int, nextFollowUpAt: String?)

    @Query("UPDATE error SET pending = 0, syncError = :reason WHERE id = :id")
    suspend fun markRejected(id: String, reason: String)

    @Query("SELECT * FROM error WHERE syncError IS NOT NULL")
    fun observeRejected(): Flow<List<ErrorEntity>>

    @Query("SELECT MAX(displayId) FROM error WHERE displayId LIKE :prefix || '%'")
    suspend fun maxDisplayId(prefix: String): String?

    /** Remove an error the dashboard deleted, with its follow-ups and history. */
    @Query("DELETE FROM error WHERE id = :id")
    suspend fun deleteById(id: String)
}

@Dao
interface FollowUpDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(item: FollowUpEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertAll(items: List<FollowUpEntity>)

    @Query("SELECT * FROM follow_up WHERE errorId = :errorId ORDER BY at DESC")
    fun observeForError(errorId: String): Flow<List<FollowUpEntity>>

    @Query("SELECT * FROM follow_up WHERE pending = 1 ORDER BY at ASC LIMIT :limit")
    suspend fun pending(limit: Int): List<FollowUpEntity>

    @Query("SELECT COUNT(*) FROM follow_up WHERE pending = 1")
    suspend fun pendingCount(): Int

    @Query("UPDATE follow_up SET pending = 0, syncError = NULL WHERE id = :id")
    suspend fun markSynced(id: String)

    @Query("UPDATE follow_up SET pending = 0, syncError = :reason WHERE id = :id")
    suspend fun markRejected(id: String, reason: String)

    @Query("DELETE FROM follow_up WHERE errorId = :errorId")
    suspend fun deleteForError(errorId: String)
}

@Dao
interface ActivityDao {
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(item: ActivityEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertAll(items: List<ActivityEntity>)

    @Query("SELECT * FROM activity WHERE errorId = :errorId ORDER BY clientAt DESC")
    fun observeForError(errorId: String): Flow<List<ActivityEntity>>

    @Query("SELECT * FROM activity WHERE pending = 1 ORDER BY clientAt ASC LIMIT :limit")
    suspend fun pending(limit: Int): List<ActivityEntity>

    @Query("SELECT COUNT(*) FROM activity WHERE pending = 1")
    suspend fun pendingCount(): Int

    @Query("UPDATE activity SET pending = 0, syncError = NULL WHERE id = :id")
    suspend fun markSynced(id: String)

    @Query("UPDATE activity SET pending = 0, syncError = :reason WHERE id = :id")
    suspend fun markRejected(id: String, reason: String)

    @Query("DELETE FROM activity WHERE errorId = :errorId")
    suspend fun deleteForError(errorId: String)
}

@Dao
interface ReferenceDao {
    @Query("SELECT * FROM district ORDER BY name") fun observeDistricts(): Flow<List<DistrictEntity>>
    @Query("SELECT * FROM team WHERE districtId = :districtId AND active = 1 ORDER BY code") fun observeTeams(districtId: Int): Flow<List<TeamEntity>>
    @Query("SELECT * FROM team ORDER BY code") fun observeAllTeams(): Flow<List<TeamEntity>>
    @Query("SELECT * FROM supervisor WHERE teamId = :teamId AND active = 1 ORDER BY name") fun observeSupervisors(teamId: Int): Flow<List<SupervisorEntity>>
    @Query("SELECT * FROM enumerator WHERE teamId = :teamId AND active = 1 ORDER BY name") fun observeEnumerators(teamId: Int): Flow<List<EnumeratorEntity>>
    @Query("SELECT * FROM ea WHERE teamId = :teamId AND active = 1 ORDER BY code") fun observeEas(teamId: Int): Flow<List<EaEntity>>
    @Query("SELECT * FROM ea ORDER BY code") fun observeAllEas(): Flow<List<EaEntity>>
    @Query("SELECT * FROM pick_list WHERE kind = :kind AND active = 1 ORDER BY sortOrder, name") fun observePickList(kind: String): Flow<List<PickListEntity>>
    @Query("SELECT * FROM pick_list WHERE kind = :kind ORDER BY sortOrder, name") suspend fun pickList(kind: String): List<PickListEntity>
    @Query("SELECT * FROM district WHERE id = :id") suspend fun district(id: Int): DistrictEntity?
    @Query("SELECT value FROM setting WHERE `key` = :key") suspend fun setting(key: String): String?

    @Upsert suspend fun upsertRegions(items: List<RegionEntity>)
    @Upsert suspend fun upsertDistricts(items: List<DistrictEntity>)
    @Upsert suspend fun upsertTeams(items: List<TeamEntity>)
    @Upsert suspend fun upsertSupervisors(items: List<SupervisorEntity>)
    @Upsert suspend fun upsertEnumerators(items: List<EnumeratorEntity>)
    @Upsert suspend fun upsertEas(items: List<EaEntity>)
    @Upsert suspend fun upsertPickList(items: List<PickListEntity>)
    @Upsert suspend fun upsertSettings(items: List<SettingEntity>)

    @Query("DELETE FROM region") suspend fun clearRegions()
    @Query("DELETE FROM district") suspend fun clearDistricts()
    @Query("DELETE FROM team") suspend fun clearTeams()
    @Query("DELETE FROM supervisor") suspend fun clearSupervisors()
    @Query("DELETE FROM enumerator") suspend fun clearEnumerators()
    @Query("DELETE FROM ea") suspend fun clearEas()
    @Query("DELETE FROM pick_list") suspend fun clearPickLists()

    @Transaction
    suspend fun replaceAll(
        regions: List<RegionEntity>,
        districts: List<DistrictEntity>,
        teams: List<TeamEntity>,
        supervisors: List<SupervisorEntity>,
        enumerators: List<EnumeratorEntity>,
        eas: List<EaEntity>,
        pickLists: List<PickListEntity>,
        settings: List<SettingEntity>,
    ) {
        clearRegions(); clearDistricts(); clearTeams(); clearSupervisors(); clearEnumerators(); clearEas(); clearPickLists()
        upsertRegions(regions); upsertDistricts(districts); upsertTeams(teams); upsertSupervisors(supervisors)
        upsertEnumerators(enumerators); upsertEas(eas); upsertPickList(pickLists); upsertSettings(settings)
    }
}

@Dao
interface SyncStateDao {
    @Query("SELECT * FROM sync_state WHERE id = 1") suspend fun get(): SyncStateEntity?
    @Query("SELECT * FROM sync_state WHERE id = 1") fun observe(): Flow<SyncStateEntity?>
    @Upsert suspend fun upsert(state: SyncStateEntity)
    @Update suspend fun update(state: SyncStateEntity)
    @Query("DELETE FROM sync_state") suspend fun clear()
}
