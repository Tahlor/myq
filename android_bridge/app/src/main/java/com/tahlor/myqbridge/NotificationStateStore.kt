package com.tahlor.myqbridge

import android.content.Context
import org.json.JSONObject


object NotificationStateStore {
    private const val PREFS = "notification_state"
    private const val STATE = "state"
    private const val OBSERVED_AT_MS = "observed_at_ms"
    private const val STALE_AFTER_MS = 5 * 60 * 1000L

    private val statePatterns = listOf(
        Regex("\\bopening\\b") to "opening",
        Regex("\\bclosing\\b") to "closing",
        Regex("\\b(?:opened|open)\\b") to "open",
        Regex("\\b(?:closed|close)\\b") to "closed",
        Regex("\\boffline\\b") to "offline",
    )

    fun normalize(values: Iterable<CharSequence?>): String? {
        val text = values
            .filterNotNull()
            .map { it.toString().trim().lowercase() }
            .filter { it.isNotEmpty() }
            .joinToString(" ")
            .replace(Regex("\\s+"), " ")
        if (text.isEmpty() || Regex("\\b(?:tap|click|press)\\s+to\\s+(?:open|close)\\b").containsMatchIn(text)) {
            return null
        }
        return statePatterns.firstOrNull { (pattern, _) -> pattern.containsMatchIn(text) }?.second
    }

    fun record(context: Context, state: String, observedAtMs: Long = System.currentTimeMillis()) {
        if (state !in setOf("open", "closed", "opening", "closing", "offline")) return
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(STATE, state)
            .putLong(OBSERVED_AT_MS, observedAtMs)
            .apply()
    }

    fun read(context: Context): JSONObject? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val state = prefs.getString(STATE, null) ?: return null
        val observedAtMs = prefs.getLong(OBSERVED_AT_MS, 0L)
        if (observedAtMs <= 0L) return null
        val ageMs = (System.currentTimeMillis() - observedAtMs).coerceAtLeast(0L)
        return JSONObject()
            .put("state", state)
            .put("observed_at_ms", observedAtMs)
            .put("age_ms", ageMs)
            .put("stale", ageMs > STALE_AFTER_MS)
    }
}
