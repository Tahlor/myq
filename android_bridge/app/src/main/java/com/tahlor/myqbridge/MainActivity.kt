package com.tahlor.myqbridge

import android.app.Activity
import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.provider.Settings
import android.util.Base64
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.security.SecureRandom


class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val prefs = getSharedPreferences(BridgeHttpServer.PREFS, MODE_PRIVATE)
        val supplied = intent.getStringExtra(BridgeHttpServer.API_KEY)?.trim()
        if (!supplied.isNullOrEmpty()) {
            require(supplied.length >= 16) { "api_key must be at least 16 characters" }
            prefs.edit().putString(BridgeHttpServer.API_KEY, supplied).apply()
        }
        var apiKey = prefs.getString(BridgeHttpServer.API_KEY, "").orEmpty()
        if (apiKey.length < 16) {
            apiKey = generateKey()
            prefs.edit().putString(BridgeHttpServer.API_KEY, apiKey).apply()
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(36, 36, 36, 36)
            gravity = Gravity.CENTER_HORIZONTAL
        }
        container.addView(TextView(this).apply {
            text = "myQ LAN Bridge"
            textSize = 26f
            setTypeface(typeface, Typeface.BOLD)
        })
        container.addView(TextView(this).apply {
            text = buildString {
                append("The bridge listens on TCP ${BridgeHttpServer.PORT} only while its accessibility service is enabled.\n\n")
                append("API key configured: …${apiKey.takeLast(6)}\n")
                append("Door selectors: Android/data/com.tahlor.myqbridge/files/doors.json\n\n")
                append("Enable the accessibility service, then open myQ and verify the dashboard before sending commands.")
            }
            textSize = 17f
        }, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        container.addView(Button(this).apply {
            text = "Accessibility settings"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        })
        container.addView(Button(this).apply {
            text = "Open myQ"
            setOnClickListener {
                val launch = packageManager.getLaunchIntentForPackage(BridgeAccessibilityService.MYQ_PACKAGE)
                if (launch != null) startActivity(launch)
            }
        })
        setContentView(container)
    }

    private fun generateKey(): String {
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        return Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_WRAP or Base64.NO_PADDING)
    }
}
