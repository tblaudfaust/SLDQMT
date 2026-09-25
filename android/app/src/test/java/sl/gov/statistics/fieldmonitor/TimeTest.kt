package sl.gov.statistics.fieldmonitor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import sl.gov.statistics.fieldmonitor.util.Time

class TimeTest {
    @Test
    fun daytimeActionIsDueFourHoursLater() {
        assertEquals("2026-09-24T13:00:00Z", Time.nextFollowUp("2026-09-24T09:00:00Z", 4.0, "20:00", "07:00"))
    }

    @Test
    fun eveningActionMovesToNextMorning() {
        assertEquals("2026-09-25T07:00:00Z", Time.nextFollowUp("2026-09-24T18:30:00Z", 4.0, "20:00", "07:00"))
    }

    @Test
    fun lateNightActionMovesToSameMorning() {
        assertEquals("2026-09-25T07:00:00Z", Time.nextFollowUp("2026-09-25T01:00:00Z", 4.0, "20:00", "07:00"))
    }

    @Test
    fun overdueOnlyWhenUnresolvedAndPast() {
        assertTrue(Time.isOverdue("2020-01-01T00:00:00Z", "UNRESOLVED"))
        assertFalse(Time.isOverdue("2020-01-01T00:00:00Z", "RESOLVED"))
        assertFalse(Time.isOverdue("2999-01-01T00:00:00Z", "UNRESOLVED"))
        assertFalse(Time.isOverdue(null, "UNRESOLVED"))
    }
}
