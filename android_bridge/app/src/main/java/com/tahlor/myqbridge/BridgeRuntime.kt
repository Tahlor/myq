package com.tahlor.myqbridge

import android.os.SystemClock


object BridgeRuntime {
    @Volatile
    private var accessibilityService: BridgeAccessibilityService? = null

    fun attach(service: BridgeAccessibilityService) {
        accessibilityService = service
    }

    fun detach(service: BridgeAccessibilityService) {
        if (accessibilityService === service) accessibilityService = null
    }

    fun requireAccessibilityService(): BridgeAccessibilityService {
        accessibilityService?.let { return it }

        // Do not launch myQ from the HTTP foreground service. Android may reject
        // that background activity start, and the attempted focus handoff can
        // leave LoginActivity stuck handling a focus-loss event. The companion
        // activity / user is responsible for bringing myQ to the foreground.
        val deadline = SystemClock.uptimeMillis() + 2_000L
        while (SystemClock.uptimeMillis() < deadline) {
            accessibilityService?.let { return it }
            SystemClock.sleep(100L)
        }
        throw IllegalStateException("myQ LAN accessibility service is not connected")
    }
}
