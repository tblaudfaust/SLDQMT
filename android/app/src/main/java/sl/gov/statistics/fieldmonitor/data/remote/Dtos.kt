package sl.gov.statistics.fieldmonitor.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(val username: String, val password: String, @SerialName("device_id") val deviceId: String?)

@Serializable
data class RefreshRequest(@SerialName("refresh_token") val refreshToken: String)

@Serializable
data class UserDto(
    val id: Int,
    val username: String,
    @SerialName("full_name") val fullName: String,
    val phone: String? = null,
    val role: String,
    val active: Boolean,
    @SerialName("district_ids") val districtIds: List<Int>? = null,
)

@Serializable
data class TokenPair(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("expires_in") val expiresIn: Int,
    val user: UserDto,
    val settings: Map<String, String> = emptyMap(),
)

@Serializable
data class DeviceRegister(
    @SerialName("device_id") val deviceId: String,
    val model: String?,
    @SerialName("android_version") val androidVersion: String?,
    @SerialName("app_version") val appVersion: String?,
)

@Serializable
data class DeviceDto(val id: String, val status: String)

@Serializable
data class ErrorDto(
    val id: String,
    @SerialName("display_id") val displayId: String,
    @SerialName("district_id") val districtId: Int,
    @SerialName("team_id") val teamId: Int? = null,
    @SerialName("supervisor_id") val supervisorId: Int? = null,
    @SerialName("supervisor_name") val supervisorName: String? = null,
    @SerialName("enumerator_id") val enumeratorId: Int? = null,
    @SerialName("enumerator_name") val enumeratorName: String? = null,
    @SerialName("ea_id") val eaId: Int? = null,
    @SerialName("category_id") val categoryId: Int,
    @SerialName("source_id") val sourceId: Int? = null,
    val description: String,
    @SerialName("date_received") val dateReceived: String,
    @SerialName("support_method") val supportMethod: String,
    @SerialName("action_taken") val actionTaken: String? = null,
    val comments: String? = null,
    val status: String,
    @SerialName("resolved_at") val resolvedAt: String? = null,
    @SerialName("last_action_at") val lastActionAt: String,
    @SerialName("next_follow_up_at") val nextFollowUpAt: String? = null,
    val lat: Double? = null,
    val lng: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("gps_at") val gpsAt: String? = null,
    @SerialName("client_created_at") val clientCreatedAt: String,
    @SerialName("client_updated_at") val clientUpdatedAt: String,
    val version: Int = 0,
    @SerialName("deleted_at") val deletedAt: String? = null,
    @SerialName("follow_ups") val followUps: List<FollowUpDto> = emptyList(),
    val activity: List<ActivityDto> = emptyList(),
)

@Serializable
data class FollowUpDto(
    val id: String,
    @SerialName("error_id") val errorId: String,
    val at: String,
    val method: String,
    val contacted: String? = null,
    val outcome: String? = null,
    val comments: String? = null,
    val lat: Double? = null,
    val lng: Double? = null,
    @SerialName("accuracy_m") val accuracyM: Double? = null,
    @SerialName("gps_at") val gpsAt: String? = null,
    @SerialName("client_created_at") val clientCreatedAt: String,
)

@Serializable
data class ActivityDto(
    val id: String,
    @SerialName("error_id") val errorId: String,
    @SerialName("previous_status") val previousStatus: String? = null,
    @SerialName("new_status") val newStatus: String,
    @SerialName("action_taken") val actionTaken: String? = null,
    val comments: String? = null,
    @SerialName("client_at") val clientAt: String,
)

@Serializable
data class PushRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("app_version") val appVersion: String,
    @SerialName("pending_count") val pendingCount: Int,
    val errors: List<ErrorDto>,
    @SerialName("follow_ups") val followUps: List<FollowUpDto>,
    val activity: List<ActivityDto>,
)

@Serializable
data class Receipt(
    val kind: String,
    val id: String,
    val result: String,
    val reason: String? = null,
    val version: Int? = null,
    @SerialName("next_follow_up_at") val nextFollowUpAt: String? = null,
)

@Serializable
data class PushResponse(val receipts: List<Receipt>, val applied: Int, val duplicates: Int, val rejected: Int)

@Serializable
data class NamedDto(val id: Int, val code: String, val name: String)

@Serializable
data class DistrictDto(val id: Int, @SerialName("region_id") val regionId: Int, val code: String, val name: String)

@Serializable
data class TeamDto(val id: Int, @SerialName("district_id") val districtId: Int, val code: String, val name: String, val chiefdom: String? = null, val active: Boolean)

@Serializable
data class PersonDto(val id: Int, @SerialName("team_id") val teamId: Int, val code: String? = null, val name: String, val phone: String? = null, val active: Boolean)

@Serializable
data class EaDto(val id: Int, @SerialName("team_id") val teamId: Int, val code: String, val name: String? = null, val locality: String? = null, val households: Int? = null, val active: Boolean)

@Serializable
data class PickListDto(val id: Int, val code: String, val name: String, val active: Boolean, @SerialName("sort_order") val sortOrder: Int)

@Serializable
data class ReferenceBundle(
    val version: String,
    val regions: List<NamedDto>,
    val districts: List<DistrictDto>,
    val teams: List<TeamDto>,
    val supervisors: List<PersonDto>,
    val enumerators: List<PersonDto>,
    val eas: List<EaDto>,
    val categories: List<PickListDto>,
    val sources: List<PickListDto>,
    val settings: Map<String, String> = emptyMap(),
)

@Serializable
data class PullResponse(
    val cursor: String,
    val errors: List<ErrorDto>,
    val reference: ReferenceBundle? = null,
    @SerialName("reference_version") val referenceVersion: String,
    val settings: Map<String, String> = emptyMap(),
    val more: Boolean = false,
)
