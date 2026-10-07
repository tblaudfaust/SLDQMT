package sl.gov.statistics.fieldmonitor.mefm

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.time.LocalDate

/**
 * The 2026 SLPHC M&E Field Monitoring Questionnaire as the server sends it (app/core/mefm_form.py).
 * The phone renders every section from this and applies the same skip rules and checks, so a form
 * that passes here is accepted by the server.
 */
@Serializable
data class FormSpec(
    val phases: List<Opt> = emptyList(),
    val sections: List<Section> = emptyList(),
    val severities: List<String> = emptyList(),
    @SerialName("referred_to") val referredTo: List<String> = emptyList(),
)

@Serializable
data class Opt(val value: String, val label: String)

@Serializable
data class Section(
    val code: String,
    val title: String,
    val phases: List<String> = emptyList(),
    val `when`: List<JsonArray> = emptyList(),
    val intro: String? = null,
    val items: List<Item> = emptyList(),
    val repeat: String? = null, // "household" (G) or "respondent" (I)
    @SerialName("min_repeat") val minRepeat: Int = 1,
    val respondents: List<String> = emptyList(),
)

@Serializable
data class Item(
    val code: String,
    val text: String,
    val type: String, // code rating multi int text time date ea gps issues
    val required: Boolean = true,
    val options: List<Opt> = emptyList(),
    val flag: Boolean = false,
    @SerialName("flag_value") val flagValue: String = "2",
    val phases: List<String> = emptyList(),
    val `when`: List<JsonArray> = emptyList(),
    val help: String? = null,
    val minimum: Int? = null,
    val maximum: Int? = null,
    val other: String? = null,
    val exclusive: String? = null,
    val respondents: List<Int>? = null,
)

/** Answers are a JSON object keyed by item code; G and I hold arrays of objects. */
typealias Answers = Map<String, JsonElement>

fun Answers.str(code: String): String? = (this[code] as? JsonPrimitive)?.contentOrNull
fun Answers.int(code: String): Int? = (this[code] as? JsonPrimitive)?.let { it.intOrNull ?: it.contentOrNull?.toIntOrNull() }
fun Answers.list(code: String): List<String> = (this[code] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull } ?: emptyList()
fun Answers.rows(code: String): List<JsonObject> = (this[code] as? JsonArray)?.mapNotNull { it as? JsonObject } ?: emptyList()

private fun holds(cond: JsonArray, scope: Answers): Boolean {
    if (cond.size < 3) return false
    val code = cond[0].jsonPrimitive.content
    val op = cond[1].jsonPrimitive.content
    val actual = scope.str(code)
    val values: List<String> = when (val value = cond[2]) {
        is JsonArray -> value.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
        is JsonPrimitive -> listOf(value.content)
        else -> emptyList()
    }
    return when (op) {
        "eq" -> actual == values.firstOrNull()
        "ne" -> actual != null && actual != values.firstOrNull()
        "in" -> actual in values
        "nin" -> actual != null && actual !in values
        else -> false
    }
}

object Routing {
    fun sectionAsked(s: Section, answers: Answers): Boolean {
        val phase = answers.str("A12") ?: ""
        if (s.phases.isNotEmpty() && phase.isEmpty() && s.code != "A") return false
        if (s.phases.isNotEmpty() && phase.isNotEmpty() && phase !in s.phases) return false
        return s.`when`.all { holds(it, answers) }
    }

    fun itemAsked(it: Item, scope: Answers, respondentIndex: Int? = null): Boolean {
        if (it.respondents != null && respondentIndex != null && respondentIndex !in it.respondents) return false
        return it.`when`.all { c -> holds(c, scope) }
    }

    /** Every section the officer must go through for the current answers, in order. */
    fun askedSections(spec: FormSpec, answers: Answers): List<Section> = spec.sections.filter { sectionAsked(it, answers) }
}

data class Problem(val section: String, val code: String, val message: String)

object Validation {
    private val time = Regex("^([01]\\d|2[0-3]):[0-5]\\d$")

    private fun checkValue(it: Item, v: JsonElement, prefix: String, out: MutableList<Problem>, section: String) {
        val code = prefix + it.code
        fun bad(msg: String) = out.add(Problem(section, it.code, "$code: $msg"))
        when (it.type) {
            "code", "rating" -> {
                val s = (v as? JsonPrimitive)?.contentOrNull
                if (s == null || it.options.none { o -> o.value == s }) bad("not one of the options")
            }
            "multi" -> {
                val values = (v as? JsonArray)?.mapNotNull { e -> (e as? JsonPrimitive)?.contentOrNull } ?: emptyList()
                if (values.any { x -> it.options.none { o -> o.value == x } }) bad("not one of the options")
                else if (it.exclusive != null && it.exclusive in values && values.size > 1) bad("'None' cannot be combined with other options")
            }
            "int" -> {
                val p = v as? JsonPrimitive
                val n = p?.intOrNull ?: p?.contentOrNull?.toIntOrNull()
                if (n == null) bad("enter a whole number")
                else if (n < (it.minimum ?: 0)) bad("cannot be negative")
                else if (it.maximum != null && n > it.maximum) bad("at most ${it.maximum}")
            }
            "time" -> if (!time.matches((v as? JsonPrimitive)?.contentOrNull ?: "")) bad("time must be HH:MM")
            "date" -> if (runCatching { LocalDate.parse((v as? JsonPrimitive)?.contentOrNull ?: "") }.isFailure) bad("date must be YYYY-MM-DD")
            "ea" -> if (((v as? JsonPrimitive)?.contentOrNull ?: "").filter(Char::isDigit).length != 10) bad("the EA code has 10 digits")
            "gps" -> {
                val o = v as? JsonObject
                if (o == null || o["lat"] == null || o["lng"] == null) bad("a GPS fix is required; wait for the device to capture one")
            }
            "issues" -> (v as? JsonArray)?.forEachIndexed { i, row ->
                val o = row as? JsonObject
                val sev = o?.str("severity") ?: ""
                if (sev !in listOf("Critical", "Major", "Minor")) out.add(Problem(section, it.code, "Issue ${i + 1}: choose Critical, Major or Minor"))
                if ((o?.str("description") ?: "").isBlank()) out.add(Problem(section, it.code, "Issue ${i + 1}: describe the issue"))
            }
        }
    }

    private fun isEmpty(v: JsonElement?): Boolean = when (v) {
        null -> true
        is JsonPrimitive -> v.contentOrNull.isNullOrBlank()
        is JsonArray -> v.isEmpty()
        else -> false
    }

    private fun checkItems(items: List<Item>, scope: Answers, prefix: String, respondentIndex: Int?, out: MutableList<Problem>, section: String) {
        for (it in items) {
            if (!Routing.itemAsked(it, scope, respondentIndex)) continue
            val v = scope[it.code]
            if (isEmpty(v)) {
                if (it.required) out.add(Problem(section, it.code, "$prefix${it.code}: an answer is required"))
                continue
            }
            checkValue(it, v!!, prefix, out, section)
            if (it.other != null && (v as? JsonPrimitive)?.contentOrNull == it.other && scope.str("${it.code}_other").isNullOrBlank()) {
                out.add(Problem(section, it.code, "$prefix${it.code}: please specify"))
            }
        }
    }

    /** The same checks as the server; an empty list means the form will be accepted. */
    fun validate(spec: FormSpec, answers: Answers): List<Problem> {
        val out = mutableListOf<Problem>()
        val phase = answers.str("A12")
        if (phase.isNullOrEmpty() || spec.phases.none { it.value == phase }) return listOf(Problem("A", "A12", "A12: choose the census phase at visit"))
        for (s in spec.sections) {
            if (!Routing.sectionAsked(s, answers)) continue
            when (s.repeat) {
                "household" -> {
                    val rows = answers.rows("G")
                    rows.forEachIndexed { i, row -> checkItems(s.items, row, "Household ${i + 1} ", null, out, s.code) }
                    if (rows.size < s.minRepeat) out.add(Problem(s.code, "G", "G: at least ${s.minRepeat} households must be verified in this phase"))
                }
                "respondent" -> {
                    val rows = answers.rows("I")
                    s.respondents.forEachIndexed { idx, label -> checkItems(s.items, rows.getOrNull(idx) ?: emptyMap(), "$label ", idx, out, s.code) }
                }
                else -> checkItems(s.items, answers, "", null, out, s.code)
            }
        }
        val arrived = answers.str("A3_arrived"); val left = answers.str("A3_left")
        if (!arrived.isNullOrEmpty() && !left.isNullOrEmpty() && left <= arrived) out.add(Problem("A", "A3_left", "A3_left: time left must be after time arrived"))
        val fs = answers.str("F8_start"); val fe = answers.str("F8_end")
        if (!fs.isNullOrEmpty() && !fe.isNullOrEmpty() && fe <= fs) out.add(Problem("F", "F8_end", "F8_end: interview end must be after its start"))
        val h2 = answers.int("H2_enumerators"); val h2v = answers.int("H2_visited")
        if (h2 != null && h2v != null && h2v > h2) out.add(Problem("H", "H2_visited", "H2_visited: cannot exceed the enumerators in the SA"))
        val c8 = answers.str("C8"); val a2 = answers.str("A2")
        if (!c8.isNullOrEmpty() && !a2.isNullOrEmpty() && c8 > a2) out.add(Problem("C", "C8", "C8: the last sync cannot be after the visit date"))
        return out
    }

    /** Flagged items answered with the problem value: these become Critical rows of the issues log on the server. */
    fun criticalItems(spec: FormSpec, answers: Answers): List<String> {
        val out = mutableListOf<String>()
        for (s in spec.sections) {
            if (!Routing.sectionAsked(s, answers)) continue
            when (s.repeat) {
                "household" -> answers.rows("G").forEachIndexed { i, row -> s.items.filter { it.flag && row.str(it.code) == it.flagValue }.forEach { out.add("Household ${i + 1}: ${it.text}") } }
                "respondent" -> answers.rows("I").forEachIndexed { i, row -> s.items.filter { it.flag && row.str(it.code) == it.flagValue }.forEach { out.add("${s.respondents.getOrNull(i) ?: ""}: ${it.text}") } }
                else -> s.items.filter { it.flag && answers.str(it.code) == it.flagValue }.forEach { out.add(it.text) }
            }
        }
        return out.map { it.replace(" ⚑", "") }
    }
}
