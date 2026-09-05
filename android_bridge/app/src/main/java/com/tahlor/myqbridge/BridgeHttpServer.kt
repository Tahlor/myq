package com.tahlor.myqbridge

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.concurrent.Executors


class BridgeHttpServer(private val service: BridgeAccessibilityService) {
    @Volatile private var running = false
    private var serverSocket: ServerSocket? = null
    private val clients = Executors.newCachedThreadPool()
    private var acceptThread: Thread? = null

    fun start() {
        if (running) return
        running = true
        acceptThread = Thread({ acceptLoop() }, "myq-http-accept").also {
            it.isDaemon = true
            it.start()
        }
    }

    fun stop() {
        running = false
        try { serverSocket?.close() } catch (_: Exception) { }
        serverSocket = null
        clients.shutdownNow()
        acceptThread = null
    }

    private fun acceptLoop() {
        try {
            val socket = ServerSocket(PORT, 16, InetAddress.getByName("0.0.0.0"))
            serverSocket = socket
            Log.i(TAG, "myQ LAN bridge listening on port $PORT")
            while (running) {
                val client = try { socket.accept() } catch (e: Exception) {
                    if (running) Log.w(TAG, "accept failed", e)
                    break
                }
                clients.execute { handle(client) }
            }
        } catch (e: Exception) {
            if (running) Log.e(TAG, "HTTP server failed", e)
        } finally {
            running = false
        }
    }

    private fun handle(socket: Socket) {
        socket.use { client ->
            client.soTimeout = 5_000
            try {
                val reader = BufferedReader(InputStreamReader(client.getInputStream(), StandardCharsets.UTF_8))
                val requestLine = reader.readLine() ?: return
                val requestParts = requestLine.split(' ')
                if (requestParts.size < 2) {
                    respond(client, 400, errorJson("Malformed request"))
                    return
                }
                val method = requestParts[0].uppercase()
                val rawTarget = requestParts[1]
                val headers = mutableMapOf<String, String>()
                while (true) {
                    val line = reader.readLine() ?: break
                    if (line.isEmpty()) break
                    val separator = line.indexOf(':')
                    if (separator > 0) {
                        headers[line.substring(0, separator).trim().lowercase()] =
                            line.substring(separator + 1).trim()
                    }
                }

                val path = rawTarget.substringBefore('?')
                if (method == "GET" && path == "/health") {
                    respond(client, 200, JSONObject().put("status", "ok"))
                    return
                }
                if (!authorized(headers["x-api-key"])) {
                    respond(client, 401, errorJson("Invalid API key"))
                    return
                }

                when {
                    method == "GET" && path == "/status" ->
                        respond(client, 200, service.status())
                    method == "GET" && path == "/debug/nodes" ->
                        respond(client, 200, service.debugNodes())
                    method == "POST" && path.startsWith("/doors/") ->
                        handleDoorCommand(client, path)
                    else -> respond(client, 404, errorJson("Not found"))
                }
            } catch (e: Exception) {
                try { respond(client, 500, errorJson(e.message ?: e.javaClass.simpleName)) } catch (_: Exception) { }
            }
        }
    }

    private fun handleDoorCommand(client: Socket, path: String) {
        val pieces = path.removePrefix("/doors/").split('/')
        if (pieces.size != 2) {
            respond(client, 404, errorJson("Expected /doors/{name}/{open|close|toggle}"))
            return
        }
        val doorName = URLDecoder.decode(pieces[0], StandardCharsets.UTF_8.name())
        val action = pieces[1].lowercase()
        if (action !in setOf("open", "close", "toggle")) {
            respond(client, 400, errorJson("Unsupported door action"))
            return
        }
        try {
            respond(client, 200, service.command(doorName, action))
        } catch (e: NoSuchElementException) {
            respond(client, 404, errorJson(e.message ?: "Unknown door"))
        } catch (e: IllegalArgumentException) {
            respond(client, 400, errorJson(e.message ?: "Invalid request"))
        } catch (e: IllegalStateException) {
            respond(client, 409, errorJson(e.message ?: "Command cannot be issued safely"))
        }
    }

    private fun authorized(provided: String?): Boolean {
        val prefs = service.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val expected = prefs.getString(API_KEY, "").orEmpty()
        if (expected.length < 16 || provided.isNullOrEmpty()) return false
        return MessageDigest.isEqual(
            expected.toByteArray(StandardCharsets.UTF_8),
            provided.toByteArray(StandardCharsets.UTF_8),
        )
    }

    private fun respond(client: Socket, status: Int, payload: JSONObject) {
        val body = payload.toString().toByteArray(StandardCharsets.UTF_8)
        val reason = when (status) {
            200 -> "OK"
            400 -> "Bad Request"
            401 -> "Unauthorized"
            404 -> "Not Found"
            409 -> "Conflict"
            else -> "Internal Server Error"
        }
        val headers = buildString {
            append("HTTP/1.1 $status $reason\r\n")
            append("Content-Type: application/json; charset=utf-8\r\n")
            append("Content-Length: ${body.size}\r\n")
            append("Cache-Control: no-store\r\n")
            append("Connection: close\r\n\r\n")
        }.toByteArray(StandardCharsets.UTF_8)
        client.getOutputStream().apply {
            write(headers)
            write(body)
            flush()
        }
    }

    private fun errorJson(message: String): JSONObject = JSONObject().put("error", message)

    companion object {
        const val PORT = 8765
        const val PREFS = "bridge"
        const val API_KEY = "api_key"
        private const val TAG = "MyQLanBridge"
    }
}
