package sl.gov.statistics.fieldmonitor.util

import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneOffset
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/** All timestamps are ISO-8601 in UTC; Sierra Leone is on UTC so display needs no conversion. */
object Time {
    private val display = DateTimeFormatter.ofPattern("dd MMM yyyy HH:mm")
    private val displayDate = DateTimeFormatter.ofPattern("dd MMM yyyy")

    fun nowIso(): String = Instant.now().toString()
    fun today(): String = LocalDate.now(ZoneOffset.UTC).toString()

    fun parse(iso: String?): Instant? = iso?.let { runCatching { Instant.parse(it) }.getOrNull() }

    fun format(iso: String?): String = parse(iso)?.atZone(ZoneOffset.UTC)?.format(display) ?: ""
    fun formatDate(date: String?): String = date?.let { runCatching { LocalDate.parse(it).format(displayDate) }.getOrNull() } ?: ""

    fun isOverdue(nextFollowUpIso: String?, status: String): Boolean {
        if (status != "UNRESOLVED") return false
        val due = parse(nextFollowUpIso) ?: return false
        return due.isBefore(Instant.now())
    }

    fun hoursUntil(iso: String?): Double? = parse(iso)?.let { (it.toEpochMilli() - System.currentTimeMillis()) / 3_600_000.0 }

    /**
     * Same rule as the server: last action plus `intervalHours`, moved to the
     * end of the quiet window when it would land inside it.
     */
    fun nextFollowUp(lastActionIso: String, intervalHours: Double, quietStart: String, quietEnd: String): String {
        val last = parse(lastActionIso) ?: Instant.now()
        var due = last.atZone(ZoneOffset.UTC).plusSeconds((intervalHours * 3600).toLong())
        val qs = runCatching { LocalTime.parse(quietStart) }.getOrDefault(LocalTime.of(20, 0))
        val qe = runCatching { LocalTime.parse(quietEnd) }.getOrDefault(LocalTime.of(7, 0))
        if (inQuiet(due, qs, qe)) {
            var end = due.withHour(qe.hour).withMinute(qe.minute).withSecond(0).withNano(0)
            if (!end.isAfter(due)) end = end.plusDays(1)
            due = end
        }
        return due.toInstant().toString()
    }

    private fun inQuiet(at: ZonedDateTime, qs: LocalTime, qe: LocalTime): Boolean {
        val t = at.toLocalTime()
        return if (qs <= qe) !t.isBefore(qs) && t.isBefore(qe) else !t.isBefore(qs) || t.isBefore(qe)
    }
}
