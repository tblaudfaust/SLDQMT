package sl.gov.statistics.fieldmonitor.sync

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.hilt.work.HiltWorker
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import dagger.hilt.android.qualifiers.ApplicationContext
import sl.gov.statistics.fieldmonitor.FieldMonitorApp
import sl.gov.statistics.fieldmonitor.MainActivity
import sl.gov.statistics.fieldmonitor.R
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.util.Time
import java.time.LocalTime
import java.time.ZoneOffset
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@HiltWorker
class SyncWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val engine: SyncEngine,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result = when (engine.run()) {
        is SyncOutcome.Ok, SyncOutcome.DeviceBlocked, SyncOutcome.NotSignedIn -> Result.success()
        SyncOutcome.Offline -> Result.retry()
        is SyncOutcome.Failed -> if (runAttemptCount < 6) Result.retry() else Result.failure()
    }
}

/** Every 15 minutes: if unresolved errors are due, post one reminder, outside quiet hours. */
@HiltWorker
class ReminderWorker @AssistedInject constructor(
    @Assisted private val context: Context,
    @Assisted params: WorkerParameters,
    private val db: AppDatabase,
) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val qs = db.referenceDao().setting("quiet_hours_start") ?: "20:00"
        val qe = db.referenceDao().setting("quiet_hours_end") ?: "07:00"
        if (inQuietHours(qs, qe)) return Result.success()
        val due = db.errorDao().countOverdue(Time.nowIso())
        if (due <= 0) {
            NotificationManagerCompat.from(context).cancel(NOTIFICATION_ID)
            return Result.success()
        }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            return Result.success()
        }
        val intent = Intent(context, MainActivity::class.java).putExtra(MainActivity.EXTRA_OPEN_FOLLOW_UPS, true)
        val pending = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val text = if (due == 1) "1 error is due for follow-up" else "$due errors are due for follow-up"
        val notification = NotificationCompat.Builder(context, FieldMonitorApp.CHANNEL_REMINDERS)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Follow-up reminder")
            .setContentText(text)
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
        return Result.success()
    }

    private fun inQuietHours(start: String, end: String): Boolean {
        val now = LocalTime.now(ZoneOffset.UTC)
        val qs = runCatching { LocalTime.parse(start) }.getOrDefault(LocalTime.of(20, 0))
        val qe = runCatching { LocalTime.parse(end) }.getOrDefault(LocalTime.of(7, 0))
        return if (qs <= qe) !now.isBefore(qs) && now.isBefore(qe) else !now.isBefore(qs) || now.isBefore(qe)
    }

    companion object {
        const val NOTIFICATION_ID = 1001
    }
}

@Singleton
class SyncScheduler @Inject constructor(@ApplicationContext private val context: Context) {
    private val wm get() = WorkManager.getInstance(context)
    private val online = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    fun ensurePeriodicWork() {
        wm.enqueueUniquePeriodicWork(
            PERIODIC_SYNC,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(online)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build(),
        )
        wm.enqueueUniquePeriodicWork(
            PERIODIC_REMINDER,
            ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<ReminderWorker>(15, TimeUnit.MINUTES).build(),
        )
    }

    /** Debounced sync a few seconds after a local change. */
    fun syncSoon() {
        wm.enqueueUniqueWork(
            ONE_TIME_SYNC,
            ExistingWorkPolicy.REPLACE,
            OneTimeWorkRequestBuilder<SyncWorker>()
                .setConstraints(online)
                .setInitialDelay(5, TimeUnit.SECONDS)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build(),
        )
    }

    fun syncNow() {
        wm.enqueueUniqueWork(
            ONE_TIME_SYNC,
            ExistingWorkPolicy.REPLACE,
            OneTimeWorkRequestBuilder<SyncWorker>()
                .setConstraints(online)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build(),
        )
    }

    fun observeSyncRunning() = wm.getWorkInfosForUniqueWorkFlow(ONE_TIME_SYNC)

    companion object {
        const val PERIODIC_SYNC = "periodic-sync"
        const val PERIODIC_REMINDER = "periodic-reminder"
        const val ONE_TIME_SYNC = "sync-now"
    }
}
