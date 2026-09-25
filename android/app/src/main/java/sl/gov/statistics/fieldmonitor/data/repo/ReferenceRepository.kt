package sl.gov.statistics.fieldmonitor.data.repo

import kotlinx.coroutines.flow.Flow
import sl.gov.statistics.fieldmonitor.data.local.AppDatabase
import sl.gov.statistics.fieldmonitor.data.local.DistrictEntity
import sl.gov.statistics.fieldmonitor.data.local.EaEntity
import sl.gov.statistics.fieldmonitor.data.local.EnumeratorEntity
import sl.gov.statistics.fieldmonitor.data.local.PickListEntity
import sl.gov.statistics.fieldmonitor.data.local.RegionEntity
import sl.gov.statistics.fieldmonitor.data.local.SettingEntity
import sl.gov.statistics.fieldmonitor.data.local.SupervisorEntity
import sl.gov.statistics.fieldmonitor.data.local.TeamEntity
import sl.gov.statistics.fieldmonitor.data.remote.ReferenceBundle
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class ReferenceRepository @Inject constructor(private val db: AppDatabase) {
    private val dao = db.referenceDao()

    fun districts(): Flow<List<DistrictEntity>> = dao.observeDistricts()
    fun teams(districtId: Int): Flow<List<TeamEntity>> = dao.observeTeams(districtId)
    fun allTeams(): Flow<List<TeamEntity>> = dao.observeAllTeams()
    fun supervisors(teamId: Int): Flow<List<SupervisorEntity>> = dao.observeSupervisors(teamId)
    fun enumerators(teamId: Int): Flow<List<EnumeratorEntity>> = dao.observeEnumerators(teamId)
    fun eas(teamId: Int): Flow<List<EaEntity>> = dao.observeEas(teamId)
    fun allEas(): Flow<List<EaEntity>> = dao.observeAllEas()
    fun categories(): Flow<List<PickListEntity>> = dao.observePickList("category")
    fun sources(): Flow<List<PickListEntity>> = dao.observePickList("source")

    suspend fun apply(bundle: ReferenceBundle) {
        dao.replaceAll(
            regions = bundle.regions.map { RegionEntity(it.id, it.code, it.name) },
            districts = bundle.districts.map { DistrictEntity(it.id, it.regionId, it.code, it.name) },
            teams = bundle.teams.map { TeamEntity(it.id, it.districtId, it.code, it.name, it.chiefdom, it.active) },
            supervisors = bundle.supervisors.map { SupervisorEntity(it.id, it.teamId, it.code, it.name, it.phone, it.active) },
            enumerators = bundle.enumerators.map { EnumeratorEntity(it.id, it.teamId, it.code, it.name, it.phone, it.active) },
            eas = bundle.eas.map { EaEntity(it.id, it.teamId, it.code, it.name, it.locality, it.households, it.active) },
            pickLists = bundle.categories.map { PickListEntity("category:${it.id}", "category", it.id, it.code, it.name, it.active, it.sortOrder) } +
                bundle.sources.map { PickListEntity("source:${it.id}", "source", it.id, it.code, it.name, it.active, it.sortOrder) },
            settings = bundle.settings.map { SettingEntity(it.key, it.value) },
        )
    }

    suspend fun applySettings(settings: Map<String, String>) {
        dao.upsertSettings(settings.map { SettingEntity(it.key, it.value) })
    }
}
