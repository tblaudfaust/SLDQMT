package sl.gov.statistics.fieldmonitor.data.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** Reference lists synced from the server. */
@Entity(tableName = "region")
data class RegionEntity(@PrimaryKey val id: Int, val code: String, val name: String)

@Entity(tableName = "district")
data class DistrictEntity(@PrimaryKey val id: Int, val regionId: Int, val code: String, val name: String)

@Entity(tableName = "team", indices = [Index("districtId")])
data class TeamEntity(
    @PrimaryKey val id: Int,
    val districtId: Int,
    val code: String,
    val name: String,
    val chiefdom: String?,
    val active: Boolean,
)

@Entity(tableName = "supervisor", indices = [Index("teamId")])
data class SupervisorEntity(
    @PrimaryKey val id: Int,
    val teamId: Int,
    val code: String?,
    val name: String,
    val phone: String?,
    val active: Boolean,
)

@Entity(tableName = "enumerator", indices = [Index("teamId")])
data class EnumeratorEntity(
    @PrimaryKey val id: Int,
    val teamId: Int,
    val code: String?,
    val name: String,
    val phone: String?,
    val active: Boolean,
)

@Entity(tableName = "ea", indices = [Index("teamId")])
data class EaEntity(
    @PrimaryKey val id: Int,
    val teamId: Int,
    val code: String,
    val name: String?,
    val locality: String?,
    val households: Int?,
    val active: Boolean,
)

@Entity(tableName = "pick_list")
data class PickListEntity(
    @PrimaryKey val key: String, // "category:12" or "source:3"
    val kind: String,
    val id: Int,
    val code: String,
    val name: String,
    val active: Boolean,
    val sortOrder: Int,
)

@Entity(tableName = "setting")
data class SettingEntity(@PrimaryKey val key: String, val value: String)

/** The Field Monitor's error record. Times are ISO-8601 UTC strings. */
@Entity(
    tableName = "error",
    indices = [Index("status"), Index("districtId"), Index("teamId"), Index("nextFollowUpAt"), Index("pending")],
)
data class ErrorEntity(
    @PrimaryKey val id: String,
    val displayId: String,
    val districtId: Int,
    val teamId: Int?,
    val supervisorId: Int?,
    val supervisorName: String?,
    val enumeratorId: Int?,
    val enumeratorName: String?,
    val eaId: Int?,
    val categoryId: Int,
    val sourceId: Int?,
    val description: String,
    val dateReceived: String, // yyyy-MM-dd
    val supportMethod: String, // REMOTE | ONSITE
    val actionTaken: String?,
    val comments: String?,
    val status: String, // UNRESOLVED | RESOLVED
    val resolvedAt: String?,
    val lastActionAt: String,
    val nextFollowUpAt: String?,
    val lat: Double?,
    val lng: Double?,
    val accuracyM: Double?,
    val gpsAt: String?,
    val clientCreatedAt: String,
    val clientUpdatedAt: String,
    val serverVersion: Int = 0,
    val pending: Boolean = true,
    val syncError: String? = null,
)

@Entity(tableName = "follow_up", indices = [Index("errorId"), Index("pending")])
data class FollowUpEntity(
    @PrimaryKey val id: String,
    val errorId: String,
    val at: String,
    val method: String,
    val contacted: String?,
    val outcome: String?,
    val comments: String?,
    val lat: Double?,
    val lng: Double?,
    val accuracyM: Double?,
    val gpsAt: String?,
    val clientCreatedAt: String,
    val pending: Boolean = true,
    val syncError: String? = null,
)

@Entity(tableName = "activity", indices = [Index("errorId"), Index("pending")])
data class ActivityEntity(
    @PrimaryKey val id: String,
    val errorId: String,
    val previousStatus: String?,
    val newStatus: String,
    val actionTaken: String?,
    val comments: String?,
    val clientAt: String,
    val pending: Boolean = true,
    val syncError: String? = null,
)

/** One row: sync bookkeeping. */
@Entity(tableName = "sync_state")
data class SyncStateEntity(
    @PrimaryKey val id: Int = 1,
    val cursor: String? = null,
    val referenceVersion: String? = null,
    val lastSyncAt: String? = null,
    val lastResult: String? = null,
    val lastError: String? = null,
    val displayCounter: Int = 0,
)
