package com.assistantbird.network

import com.assistantbird.model.SseEvent
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import okhttp3.Response
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader

object SseClient {

    /**
     * Parse SSE stream from a chat POST response.
     *
     * Implements the same line-by-line buffering logic as
     * desktop/js/stream.js:processBuffer().
     */
    fun parse(response: Response): Flow<SseEvent> = flow {
        val body = response.body ?: return@flow
        val reader = BufferedReader(InputStreamReader(body.byteStream(), Charsets.UTF_8))

        var eventType = ""
        var data = ""

        try {
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                val currentLine = line!!

                when {
                    currentLine.startsWith("event: ") -> {
                        eventType = currentLine.removePrefix("event: ").trim()
                    }
                    currentLine.startsWith("data: ") -> {
                        data = currentLine.removePrefix("data: ").trim()
                    }
                    currentLine.isEmpty() && data.isNotEmpty() -> {
                        val parsed = parseEvent(eventType, data)
                        if (parsed != null) {
                            emit(parsed)
                        }
                        eventType = ""
                        data = ""
                    }
                }
            }

            emit(SseEvent.Done())
        } finally {
            reader.close()
            response.close()
        }
    }

    private fun parseEvent(type: String, data: String): SseEvent? {
        val json = try {
            JSONObject(data)
        } catch (e: Exception) {
            null
        }

        return when (type) {
            "token" -> {
                val text = json?.optString("text", "") ?: data
                SseEvent.Token(text)
            }
            "agent_switch" -> {
                SseEvent.AgentSwitch(
                    agent = json?.optString("agent", "") ?: "",
                    display = json?.optString("display", "") ?: "",
                )
            }
            "tool_start" -> {
                val name = json?.optString("name", "unknown") ?: "unknown"
                val input = json?.optJSONObject("input")
                val inputMap = mutableMapOf<String, String>()
                input?.keys()?.forEach { key ->
                    inputMap[key] = input.opt(key)?.toString() ?: ""
                }
                SseEvent.ToolStart(name, inputMap)
            }
            "tool_end" -> {
                SseEvent.ToolEnd(
                    name = json?.optString("name", "unknown") ?: "unknown",
                    output = json?.optString("output", "") ?: "",
                )
            }
            "thinking" -> {
                SseEvent.Thinking(json?.optString("text", "") ?: "")
            }
            "system" -> {
                SseEvent.System(json?.optString("message", "") ?: "")
            }
            "done" -> {
                val aborted = json?.optBoolean("aborted", false) ?: false
                SseEvent.Done(aborted)
            }
            "error" -> {
                SseEvent.Error(
                    type = json?.optString("type", "unknown") ?: "unknown",
                    message = json?.optString("message", "") ?: "",
                )
            }
            else -> null
        }
    }
}
