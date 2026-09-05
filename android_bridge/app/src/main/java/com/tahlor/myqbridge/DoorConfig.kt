package com.tahlor.myqbridge

import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONObject
import java.io.File


data class NodeSelector(
    val resourceId: String? = null,
    val text: String? = null,
    val description: String? = null,
    val textContains: String? = null,
) {
    fun matches(node: AccessibilityNodeInfo): Boolean {
        if (resourceId != null && node.viewIdResourceName != resourceId) return false
        if (text != null && node.text?.toString() != text) return false
        if (description != null && node.contentDescription?.toString() != description) return false
        if (textContains != null && node.text?.toString()?.contains(textContains, ignoreCase = true) != true) return false
        return listOf(resourceId, text, description, textContains).any { !it.isNullOrBlank() }
    }

    companion object {
        fun fromJson(raw: JSONObject?): NodeSelector? {
            if (raw == null) return null
            fun value(key: String): String? = raw.optString(key).trim().takeIf { it.isNotEmpty() }
            val selector = NodeSelector(
                resourceId = value("resource_id"),
                text = value("text"),
                description = value("description"),
                textContains = value("text_contains"),
            )
            return selector.takeIf {
                listOf(it.resourceId, it.text, it.description, it.textContains).any { value -> !value.isNullOrBlank() }
            }
        }
    }
}


data class DoorConfig(
    val name: String,
    val state: NodeSelector,
    val openSelector: NodeSelector? = null,
    val closeSelector: NodeSelector? = null,
    val toggleSelector: NodeSelector? = null,
) {
    companion object {
        fun load(file: File): List<DoorConfig> {
            if (!file.exists()) return emptyList()
            val root = JSONObject(file.readText(Charsets.UTF_8))
            val doors = root.optJSONArray("doors") ?: return emptyList()
            return buildList {
                for (index in 0 until doors.length()) {
                    val raw = doors.optJSONObject(index) ?: continue
                    val name = raw.optString("name").trim()
                    val state = NodeSelector.fromJson(raw.optJSONObject("state"))
                    if (name.isEmpty() || state == null) continue
                    add(
                        DoorConfig(
                            name = name,
                            state = state,
                            openSelector = NodeSelector.fromJson(raw.optJSONObject("open")),
                            closeSelector = NodeSelector.fromJson(raw.optJSONObject("close")),
                            toggleSelector = NodeSelector.fromJson(raw.optJSONObject("toggle")),
                        )
                    )
                }
            }
        }
    }
}
