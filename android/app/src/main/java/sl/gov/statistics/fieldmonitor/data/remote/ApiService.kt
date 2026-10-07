package sl.gov.statistics.fieldmonitor.data.remote

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface ApiService {
    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenPair

    @POST("auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenPair

    @POST("devices/register")
    suspend fun registerDevice(@Body body: DeviceRegister): DeviceDto

    @POST("sync/push")
    suspend fun push(@Body body: PushRequest): PushResponse

    @GET("sync/pull")
    suspend fun pull(
        @Query("device_id") deviceId: String,
        @Query("cursor") cursor: String?,
        @Query("reference_version") referenceVersion: String?,
        @Query("limit") limit: Int = 500,
    ): PullResponse

    // ---- M&E Field Monitoring (District M&E Officers) ----
    @POST("mefm/sync/push")
    suspend fun mefmPush(@Body body: MefmPushRequest): MefmPushResponse

    @GET("mefm/sync/pull")
    suspend fun mefmPull(
        @Query("device_id") deviceId: String,
        @Query("cursor") cursor: String?,
        @Query("frame_version") frameVersion: String?,
        @Query("form_version") formVersion: String?,
        @Query("limit") limit: Int = 500,
    ): MefmPullResponse
}
