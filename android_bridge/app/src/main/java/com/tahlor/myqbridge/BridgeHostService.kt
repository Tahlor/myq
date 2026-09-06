package com.tahlor.myqbridge

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import org.json.JSONObject


class BridgeHostService : Service(), BridgeRequestTarget {
    private var server: BridgeHttpServer? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        startForeground(NOTIFICATION_ID, notification())
        server = BridgeHttpServer(this, this).also { it.start() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int = START_STICKY

    override fun onDestroy() {
        server?.stop()
        server = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun status(): JSONObject = BridgeRuntime.requireAccessibilityService().status()

    override fun debugNodes(): JSONObject = BridgeRuntime.requireAccessibilityService().debugNodes()

    override fun command(doorName: String, action: String): JSONObject =
        BridgeRuntime.requireAccessibilityService().command(doorName, action)

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "myQ LAN Bridge", NotificationManager.IMPORTANCE_LOW),
        )
    }

    @Suppress("DEPRECATION")
    private fun notification(): Notification = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
        Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("myQ LAN Bridge")
            .setContentText("Authenticated local bridge is running")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .build()
    } else {
        Notification.Builder(this)
            .setContentTitle("myQ LAN Bridge")
            .setContentText("Authenticated local bridge is running")
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "myq_bridge"
        private const val NOTIFICATION_ID = 8765
    }
}
