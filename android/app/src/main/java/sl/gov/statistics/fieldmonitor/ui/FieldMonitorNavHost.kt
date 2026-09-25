package sl.gov.statistics.fieldmonitor.ui

import android.util.Log
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.StateFlow
import sl.gov.statistics.fieldmonitor.data.SessionStore
import sl.gov.statistics.fieldmonitor.data.repo.AuthRepository
import sl.gov.statistics.fieldmonitor.ui.screens.ErrorDetailScreen
import sl.gov.statistics.fieldmonitor.ui.screens.ErrorFormScreen
import sl.gov.statistics.fieldmonitor.ui.screens.ErrorListScreen
import sl.gov.statistics.fieldmonitor.ui.screens.FollowUpsDueScreen
import sl.gov.statistics.fieldmonitor.ui.screens.HomeScreen
import sl.gov.statistics.fieldmonitor.ui.screens.LoginScreen
import sl.gov.statistics.fieldmonitor.ui.screens.PinScreen
import sl.gov.statistics.fieldmonitor.ui.screens.SettingsScreen
import sl.gov.statistics.fieldmonitor.ui.screens.SyncScreen
import javax.inject.Inject

object Routes {
    const val LOGIN = "login"
    const val PIN = "pin"
    const val HOME = "home"
    const val ERRORS = "errors"
    const val NEW_ERROR = "errors/new"
    const val ERROR_DETAIL = "errors/{id}"
    const val DUE = "due"
    const val SYNC = "sync"
    const val SETTINGS = "settings"
    fun detail(id: String) = "errors/$id"
}

@HiltViewModel
class AppViewModel @Inject constructor(private val auth: AuthRepository, session: SessionStore) : ViewModel() {
    val unlocked: StateFlow<Boolean> = session.unlocked
    val hasSession: Boolean get() = auth.hasSession
    val hasPin: Boolean get() = auth.hasPin
}

@Composable
fun FieldMonitorNavHost(startAtFollowUps: Boolean, vm: AppViewModel = hiltViewModel()) {
    val nav: NavHostController = rememberNavController()
    val unlocked by vm.unlocked.collectAsStateWithLifecycle()
    // The start destination must not change once the graph is set, otherwise the
    // NavHost is rebuilt around a back stack it no longer owns and renders nothing.
    // Later changes of session state are handled by navigating explicitly below.
    val start = rememberSaveable {
        when {
            !vm.hasSession -> Routes.LOGIN
            !unlocked -> Routes.PIN
            else -> Routes.HOME
        }
    }

    DisposableEffect(nav) {
        val listener = NavController.OnDestinationChangedListener { controller, destination, _ ->
            val stack = controller.visibleEntries.value.mapNotNull { it.destination.route }
            Log.i(TAG, "destination=${destination.route} backStack=$stack")
        }
        nav.addOnDestinationChangedListener(listener)
        onDispose { nav.removeOnDestinationChangedListener(listener) }
    }

    NavHost(navController = nav, startDestination = start) {
        composable(Routes.LOGIN) {
            LoginScreen(onLoggedIn = { nav.navigate(Routes.PIN) { popUpTo(nav.graph.id) { inclusive = true } } })
        }
        composable(Routes.PIN) {
            PinScreen(
                onUnlocked = { nav.navigate(Routes.HOME) { popUpTo(nav.graph.id) { inclusive = true } } },
                onWiped = { nav.navigate(Routes.LOGIN) { popUpTo(nav.graph.id) { inclusive = true } } },
            )
        }
        composable(Routes.HOME) {
            HomeScreen(
                onNewError = { nav.navigate(Routes.NEW_ERROR) },
                onErrors = { nav.navigate(Routes.ERRORS) },
                onDue = { nav.navigate(Routes.DUE) },
                onSync = { nav.navigate(Routes.SYNC) },
                onSettings = { nav.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.ERRORS) {
            ErrorListScreen(onOpen = { nav.navigate(Routes.detail(it)) }, onNew = { nav.navigate(Routes.NEW_ERROR) }, onBack = { nav.safeBack() })
        }
        composable(Routes.NEW_ERROR) {
            ErrorFormScreen(onSaved = { id -> nav.navigate(Routes.detail(id)) { popUpTo(Routes.NEW_ERROR) { inclusive = true } } }, onBack = { nav.safeBack() })
        }
        composable(Routes.ERROR_DETAIL) { entry ->
            ErrorDetailScreen(errorId = entry.arguments?.getString("id") ?: "", onBack = { nav.safeBack() })
        }
        composable(Routes.DUE) {
            FollowUpsDueScreen(onOpen = { nav.navigate(Routes.detail(it)) }, onBack = { nav.safeBack() })
        }
        composable(Routes.SYNC) {
            SyncScreen(onOpen = { nav.navigate(Routes.detail(it)) }, onBack = { nav.safeBack() })
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(onBack = { nav.safeBack() }, onLoggedOut = { nav.navigate(Routes.LOGIN) { popUpTo(nav.graph.id) { inclusive = true } } })
        }
    }

    LaunchedEffect(unlocked) {
        Log.i(TAG, "unlocked=$unlocked hasSession=${vm.hasSession} current=${nav.currentDestination?.route}")
        when {
            !unlocked && !vm.hasSession && nav.currentDestination?.route != Routes.LOGIN ->
                nav.navigate(Routes.LOGIN) { popUpTo(nav.graph.id) { inclusive = true } }
            !unlocked && vm.hasSession && nav.currentDestination?.route != Routes.PIN ->
                nav.navigate(Routes.PIN) { popUpTo(nav.graph.id) { inclusive = true } }
            unlocked && startAtFollowUps -> nav.navigate(Routes.DUE)
        }
    }
}

private const val TAG = "FMNav"

/**
 * Pops the current screen, or returns to Home when this is the last entry.
 * A programmatic popBackStack() on the last entry leaves the NavHost empty,
 * which shows as a blank white screen. That can happen when a Back button is
 * activated repeatedly, for example by a hardware keyboard.
 */
private fun NavHostController.safeBack() {
    if (previousBackStackEntry != null) {
        popBackStack()
    } else if (currentDestination?.route != Routes.HOME) {
        navigate(Routes.HOME) { popUpTo(graph.id) { inclusive = true } }
    }
}
