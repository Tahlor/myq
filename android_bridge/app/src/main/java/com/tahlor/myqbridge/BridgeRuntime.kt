package com.tahlor.myqbridge

import android.content.Context
import android.content.Intent
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

    fun requireAccessibilityService(context: Context): BridgeAccessibilityService {
        accessibilityService?.let { return it }

        val launch = context.packageManager.getLaunchIntentForPackage(BridgeAccessibilityService.MYQ_PACKAGE)
            ?: throw IllegalStateException("Official myQ app is not installed")
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)
        context.startActivity(launch)

        val deadline = SystemClock.uptimeMillis() + 6_000L
        while (SystemClock.uptimeMillis() < deadline) {
            accessibilityService?.let { return it }
            SystemClock.sleep(250L)
        }
        throw IllegalStateException("myQ accessibility service is not connected")
    }
}
