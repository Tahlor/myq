package com.tahlor.myqbridge

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.graphics.Rect
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import org.json.JSONArray
import org.json.JSONObject
import java.io.File


class BridgeAccessibilityService : AccessibilityService() {
    private val commandLock = Any()
    private var server: BridgeHttpServer? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        server?.stop()
        server = BridgeHttpServer(this).also { it.start() }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        server?.stop()
        server = null
        super.onDestroy()
    }

    fun status(): JSONObject = synchronized(commandLock) {
        val root = ensureMyQForeground()
        val result = JSONObject()
        val doorStates = JSONObject()
        for (door in loadDoors()) {
            doorStates.put(door.name, JSONObject().put("state", stateFor(root, door)))
        }
        result.put("status", "online")
        result.put("package", MYQ_PACKAGE)
        result.put("configured_doors", doorStates.length())
        result.put("doors", doorStates)
        result.put("inferred_state_tokens", inferStateTokens(root))
        result
    }

    fun debugNodes(): JSONObject = synchronized(commandLock) {
        val root = ensureMyQForeground()
        JSONObject().put("nodes", collectNodes(root))
    }

    fun command(doorName: String, action: String): JSONObject = synchronized(commandLock) {
        require(action in setOf("open", "close", "toggle")) { "Unsupported action: $action" }
        var root = ensureMyQForeground()
        val door = loadDoors().firstOrNull { it.name == doorName }
            ?: throw NoSuchElementException("Unknown door: $doorName")
        val before = stateFor(root, door)
        val desired = when (action) {
            "open" -> "open"
            "close" -> "closed"
            else -> null
        }
        if (desired != null && before == desired) {
            return@synchronized JSONObject()
                .put("ok", true)
                .put("changed", false)
                .put("before", before)
                .put("after", before)
        }

        val directSelector = when (action) {
            "open" -> door.openSelector
            "close" -> door.closeSelector
            else -> null
        }
        val selector = directSelector ?: door.toggleSelector
            ?: throw IllegalStateException("No selector configured for ${door.name} -> $action")

        if (desired != null && directSelector == null && before !in setOf("open", "closed")) {
            throw IllegalStateException(
                "Refusing blind toggle for ${door.name}: current state is $before"
            )
        }

        val node = findNode(root, selector)
            ?: throw IllegalStateException("Configured action selector is not visible")
        if (!clickNode(node)) {
            throw IllegalStateException("Configured action selector is not clickable")
        }

        val deadline = System.currentTimeMillis() + 12_000L
        var after = before
        while (System.currentTimeMillis() < deadline) {
            Thread.sleep(750L)
            root = rootInActiveWindow ?: continue
            after = stateFor(root, door)
            if (desired != null && after == desired) break
            if (desired == null && after != before && after != "unknown") break
        }

        JSONObject()
            .put("ok", true)
            .put("changed", true)
            .put("before", before)
            .put("after", after)
    }

    private fun loadDoors(): List<DoorConfig> = DoorConfig.load(configFile())

    private fun configFile(): File {
        val base = getExternalFilesDir(null) ?: filesDir
        return File(base, "doors.json")
    }

    private fun ensureMyQForeground(): AccessibilityNodeInfo {
        currentMyQRoot()?.let { return it }
        val intent = packageManager.getLaunchIntentForPackage(MYQ_PACKAGE)
            ?: throw IllegalStateException("Official myQ app is not installed")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
        startActivity(intent)
        val deadline = System.currentTimeMillis() + 6_000L
        while (System.currentTimeMillis() < deadline) {
            Thread.sleep(250L)
            currentMyQRoot()?.let { return it }
        }
        throw IllegalStateException("myQ did not become the active accessibility window")
    }

    private fun currentMyQRoot(): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        return root.takeIf { it.packageName?.toString() == MYQ_PACKAGE }
    }

    private fun stateFor(root: AccessibilityNodeInfo, door: DoorConfig): String {
        val node = findNode(root, door.state) ?: return "unknown"
        val value = node.text?.toString()?.takeIf { it.isNotBlank() }
            ?: node.contentDescription?.toString()
        return normalizeState(value)
    }

    private fun normalizeState(value: String?): String {
        if (value.isNullOrBlank()) return "unknown"
        val cleaned = value.trim().lowercase().replace('_', ' ').split(Regex("\\s+")).joinToString(" ")
        for ((token, normalized) in STATE_MAP) {
            if (cleaned == token || cleaned.startsWith("$token ") || cleaned.endsWith(" $token")) {
                return normalized
            }
        }
        return cleaned
    }

    private fun inferStateTokens(root: AccessibilityNodeInfo): JSONArray {
        val result = JSONArray()
        val seen = linkedSetOf<String>()
        walk(root) { node ->
            for (value in listOf(node.text?.toString(), node.contentDescription?.toString())) {
                val cleaned = value?.trim()?.lowercase()?.replace('_', ' ')
                    ?.split(Regex("\\s+"))?.joinToString(" ") ?: continue
                STATE_MAP[cleaned]?.let { seen.add(it) }
            }
        }
        seen.forEach { result.put(it) }
        return result
    }

    private fun findNode(root: AccessibilityNodeInfo, selector: NodeSelector): AccessibilityNodeInfo? {
        var match: AccessibilityNodeInfo? = null
        walk(root) { node ->
            if (match == null && selector.matches(node)) match = node
        }
        return match
    }

    private fun clickNode(node: AccessibilityNodeInfo): Boolean {
        var current: AccessibilityNodeInfo? = node
        repeat(5) {
            val candidate = current ?: return false
            if (candidate.isClickable) {
                return candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            }
            current = candidate.parent
        }
        return false
    }

    private fun collectNodes(root: AccessibilityNodeInfo): JSONArray {
        val result = JSONArray()
        var count = 0
        walk(root) { node ->
            if (count >= MAX_DEBUG_NODES) return@walk
            val text = node.text?.toString().orEmpty()
            val description = node.contentDescription?.toString().orEmpty()
            val resourceId = node.viewIdResourceName.orEmpty()
            if (text.isBlank() && description.isBlank() && resourceId.isBlank()) return@walk
            val bounds = Rect().also { node.getBoundsInScreen(it) }
            result.put(
                JSONObject()
                    .put("text", text)
                    .put("description", description)
                    .put("resource_id", resourceId)
                    .put("class", node.className?.toString().orEmpty())
                    .put("clickable", node.isClickable)
                    .put("bounds", bounds.toShortString())
            )
            count += 1
        }
        return result
    }

    private fun walk(root: AccessibilityNodeInfo, visit: (AccessibilityNodeInfo) -> Unit) {
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(root)
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            visit(node)
            for (index in 0 until node.childCount) {
                node.getChild(index)?.let { queue.add(it) }
            }
        }
    }

    companion object {
        const val MYQ_PACKAGE = "com.chamberlain.android.liftmaster.myq"
        private const val MAX_DEBUG_NODES = 500
        private val STATE_MAP = linkedMapOf(
            "opening" to "opening",
            "closing" to "closing",
            "opened" to "open",
            "open" to "open",
            "closed" to "closed",
            "close" to "closed",
            "stopped" to "stopped",
            "offline" to "offline",
        )
    }
}
