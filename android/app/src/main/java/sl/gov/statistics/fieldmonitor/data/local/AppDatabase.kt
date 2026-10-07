package sl.gov.statistics.fieldmonitor.data.local

import androidx.room.AutoMigration
import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        RegionEntity::class, DistrictEntity::class, TeamEntity::class, SupervisorEntity::class,
        EnumeratorEntity::class, EaEntity::class, PickListEntity::class, SettingEntity::class,
        ErrorEntity::class, FollowUpEntity::class, ActivityEntity::class, SyncStateEntity::class,
        MefmDistrictEntity::class, MefmChiefdomEntity::class, MefmSectionEntity::class, MefmTeamEntity::class, MefmEaEntity::class,
        MefmFormEntity::class, MefmVisitEntity::class, MefmCheckinEntity::class, MefmSyncStateEntity::class,
    ],
    version = 2,
    exportSchema = true,
    autoMigrations = [AutoMigration(from = 1, to = 2)],
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun errorDao(): ErrorDao
    abstract fun followUpDao(): FollowUpDao
    abstract fun activityDao(): ActivityDao
    abstract fun referenceDao(): ReferenceDao
    abstract fun syncStateDao(): SyncStateDao
    abstract fun mefmDao(): MefmDao
}
