package sl.gov.statistics.fieldmonitor.data.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** M&E Field Monitoring: the district frame (pulled), the questionnaire (pulled) and the officer's forms (pushed). */

@Entity(tableName = "mefm_district")
data class MefmDistrictEntity(@PrimaryKey val id: Int, val code: String, val name: String, val region: String)

@Entity(tableName = "mefm_chiefdom", indices = [Index("districtId")])
data class MefmChiefdomEntity(@PrimaryKey val id: Int, val districtId: Int, val code: String, val name: String)

@Entity(tableName = "mefm_section", indices = [Index("chiefdomId")])
data class MefmSectionEntity(@PrimaryKey val id: Int, val districtId: Int, val chiefdomId: Int, val code: String, val name: String)

@Entity(tableName = "mefm_team", indices = [Index("districtId")])
data class MefmTeamEntity(
    @PrimaryKey val id: Int,
    val districtId: Int,
    val code: String,
    val name: String,
    val chiefdom: String?,
    val supervisor: String?,
    val enumerators: String, // names joined with " | "
)

@Entity(tableName = "mefm_ea", indices = [Index("popEaCode"), Index("teamId")])
data class MefmEaEntity(
    @PrimaryKey val id: Int,
    val teamId: Int,
    val code: String,
    val name: String?,
    val locality: String?,
    val popEaCode: String?,
    val chiefdomCode: String?,
    val sectionCode: String?,
    val locStatus: String?, // 1 rural, 2 urban
    val expectedHouseholds: Int?,
    val lat: Double?,
    val lng: Double?,
)

/** The questionnaire specification as the server sent it (one row). */
@Entity(tableName = "mefm_form")
data class MefmFormEntity(@PrimaryKey val id: Int = 1, val version: String, val json: String)

/**
 * One visit form. `answers` is the JSON object the server validates; `complete` is false while it is a draft.
 * `pending` means it waits for upload; `syncError` holds the server's rejection (one message per line).
 */
@Entity(tableName = "mefm_visit", indices = [Index("pending"), Index("visitDate"), Index("complete")])
data class MefmVisitEntity(
    @PrimaryKey val id: String,
    val popEaCode: String,
    val eaLabel: String,
    val phase: String,
    val visitDate: String,
    val answers: String,
    val lat: Double?,
    val lng: Double?,
    val accuracyM: Double?,
    val gpsAt: String?,
    val complete: Boolean = false,
    val pending: Boolean = false,
    val syncError: String? = null,
    val serverVersion: Int = 0,
    val serverStatus: String? = null, // SUBMITTED | REVIEWED once the server has it
    val flags: String = "", // comma separated, from the server
    val openIssues: Int = 0,
    val reviewNote: String? = null,
    val clientCreatedAt: String,
    val clientUpdatedAt: String,
)

@Entity(tableName = "mefm_checkin", indices = [Index("pending")])
data class MefmCheckinEntity(
    @PrimaryKey val id: String,
    val chiefdomCode: String?,
    val sectionCode: String?,
    val label: String,
    val note: String?,
    val lat: Double,
    val lng: Double,
    val accuracyM: Double?,
    val at: String,
    val pending: Boolean = true,
    val syncError: String? = null,
    val flags: String = "",
)

@Entity(tableName = "mefm_sync_state")
data class MefmSyncStateEntity(
    @PrimaryKey val id: Int = 1,
    val cursor: String? = null,
    val frameVersion: String? = null,
    val formVersion: String? = null,
)
