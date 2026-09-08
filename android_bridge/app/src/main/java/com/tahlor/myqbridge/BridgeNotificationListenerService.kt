package com.tahlor.myqbridge

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification


class BridgeNotificationListenerService : NotificationListenerService() {
    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null || sbn.packageName != BridgeAccessibilityService.MYQ_PACKAGE) return
        val extras = sbn.notification?.extras ?: return
        val values = listOf(
            extras.getCharSequence(Notification.EXTRA_TITLE),
            extras.getCharSequence(Notification.EXTRA_TEXT),
            extras.getCharSequence(Notification.EXTRA_BIG_TEXT),
            extras.getCharSequence(Notification.EXTRA_SUB_TEXT),
        )
        val state = NotificationStateStore.normalize(values) ?: return
        NotificationStateStore.record(this, state)
    }
}
