package sl.gov.statistics.fieldmonitor.data.remote

import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import sl.gov.statistics.fieldmonitor.data.SessionStore
import javax.inject.Inject
import javax.inject.Provider
import javax.inject.Singleton

/** Adds the bearer token to every request except login and refresh. */
@Singleton
class AuthInterceptor @Inject constructor(private val session: SessionStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val path = request.url.encodedPath
        if (path.endsWith("/auth/login") || path.endsWith("/auth/refresh")) return chain.proceed(request)
        val token = session.accessToken ?: return chain.proceed(request)
        return chain.proceed(request.newBuilder().header("Authorization", "Bearer $token").build())
    }
}

/**
 * On 401, exchanges the refresh token once and retries. Uses a Provider so
 * the ApiService can depend on the OkHttp client that this authenticator
 * belongs to without a dependency cycle.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val session: SessionStore,
    private val api: Provider<ApiService>,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        if (response.request.header("X-Retried") != null) return null
        val refresh = session.refreshToken ?: return null
        val pair = synchronized(this) {
            val current = session.accessToken
            // Another call may already have refreshed.
            val sentToken = response.request.header("Authorization")?.removePrefix("Bearer ")
            if (current != null && current != sentToken) {
                return@synchronized null
            }
            val result = runCatching { kotlinx.coroutines.runBlocking { api.get().refresh(RefreshRequest(refresh)) } }
            // A revoked refresh token (password or PIN reset by an administrator) ends the offline session:
            // the monitor must sign in again online. Network failures keep the session.
            if ((result.exceptionOrNull() as? retrofit2.HttpException)?.code() == 401) session.clearSession()
            result.getOrNull()
        }
        if (pair != null) session.saveTokens(pair.accessToken, pair.refreshToken)
        val token = session.accessToken ?: return null
        return response.request.newBuilder()
            .header("Authorization", "Bearer $token")
            .header("X-Retried", "1")
            .build()
    }
}
