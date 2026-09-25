package sl.gov.statistics.fieldmonitor.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        RegionEntity::class, DistrictEntity::class, TeamEntity::class, SupervisorEntity::class,
        EnumeratorEntity::class, EaEntity::class, PickListEntity::class, SettingEntity::class,
        ErrorEntity::class, FollowUpEntity::class, ActivityEntity::class, SyncStateEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun errorDao(): ErrorDao
    abstract fun followUpDao(): FollowUpDao
    abstract fun activityDao(): ActivityDao
    abstract fun referenceDao(): ReferenceDao
    abstract fun syncStateDao(): SyncStateDao
}
