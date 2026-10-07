package sl.gov.statistics.fieldmonitor.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/** M&E Field Monitoring sync: what the phone sends and receives (see server app/schemas/mefm.py). */

@Serializable
data class GpsDto(val lat: Double, val lng: Double, @SerialName("accuracy_m") val accuracyM: Double? = null, val at: String? = null)

@Serializable
data class MefmVisitDto(
    val id: String,
    @SerialName("pop_ea_code") val popEaCode: String,
    val answers: JsonObject,
    val gps: GpsDto,
    @SerialName("client_created_at") val clientCreatedAt: String,
    @SerialName("client_updated_at") val clientUpdatedAt: String,
)

@Serializable
data class MefmCheckinDto(
    val id: String,
    @SerialName("chiefdom_code") val chiefdomCode: String? = null,
    @SerialName("section_code") val sectionCode: String? = null,
    val note: String? = null,
    val gps: GpsDto,
    val at: String,
)

@Serializable
data class MefmPushRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("app_version") val appVersion: String,
    @SerialName("pending_count") val pendingCount: Int,
    val visits: List<MefmVisitDto>,
    val checkins: List<MefmCheckinDto>,
)

@Serializable
data class MefmReceipt(
    val kind: String,
    val id: String,
    val result: String,
    val reason: String? = null,
    val errors: List<String> = emptyList(),
    val flags: List<String> = emptyList(),
    val version: Int? = null,
)

@Serializable
data class MefmPushResponse(val receipts: List<MefmReceipt>, val applied: Int, val duplicates: Int, val rejected: Int)

@Serializable
data class FrameDistrictDto(val id: Int, val code: String, val name: String, val region: String)

@Serializable
data class FrameChiefdomDto(val id: Int, @SerialName("district_id") val districtId: Int, val code: String, val name: String)

@Serializable
data class FrameSectionDto(val id: Int, @SerialName("district_id") val districtId: Int, @SerialName("chiefdom_id") val chiefdomId: Int, val code: String, val name: String)

@Serializable
data class FrameTeamDto(
    val id: Int,
    @SerialName("district_id") val districtId: Int,
    val code: String,
    val name: String,
    val chiefdom: String? = null,
    val supervisor: String? = null,
    val enumerators: List<String> = emptyList(),
)

@Serializable
data class FrameEaDto(
    val id: Int,
    @SerialName("team_id") val teamId: Int,
    val code: String,
    val name: String? = null,
    val locality: String? = null,
    @SerialName("pop_ea_code") val popEaCode: String? = null,
    @SerialName("chiefdom_code") val chiefdomCode: String? = null,
    @SerialName("section_code") val sectionCode: String? = null,
    @SerialName("loc_status") val locStatus: String? = null,
    @SerialName("expected_households") val expectedHouseholds: Int? = null,
    val lat: Double? = null,
    val lng: Double? = null,
)

@Serializable
data class MefmFrameDto(
    val version: String,
    val districts: List<FrameDistrictDto>,
    val chiefdoms: List<FrameChiefdomDto>,
    val sections: List<FrameSectionDto>,
    val teams: List<FrameTeamDto>,
    val eas: List<FrameEaDto>,
)

@Serializable
data class VisitStateDto(
    val id: String,
    val status: String,
    val version: Int,
    val flags: List<String> = emptyList(),
    @SerialName("review_note") val reviewNote: String? = null,
    @SerialName("open_issues") val openIssues: Int = 0,
    @SerialName("server_updated_at") val serverUpdatedAt: String,
    val deleted: Boolean = false,
)

@Serializable
data class MefmPullResponse(
    val cursor: String,
    val form: JsonObject? = null,
    @SerialName("form_version") val formVersion: String,
    val frame: MefmFrameDto? = null,
    @SerialName("frame_version") val frameVersion: String,
    val settings: Map<String, String> = emptyMap(),
    val visits: List<VisitStateDto> = emptyList(),
    val more: Boolean = false,
    @SerialName("pin_reset") val pinReset: Boolean = false,
)
