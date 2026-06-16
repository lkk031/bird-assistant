package com.assistantbird.network

import com.assistantbird.model.Conversation
import com.assistantbird.model.Message
import com.assistantbird.model.MessageRole
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ApiClient(private val baseUrl: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.MINUTES)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    suspend fun getConversations(): List<Conversation> = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$baseUrl/conversations").get().build()
        val response = client.newCall(request).execute()
        val body = response.body?.string() ?: "{}"
        val json = JSONObject(body)
        val arr = json.getJSONArray("conversations")
        (0 until arr.length()).map { i ->
            val obj = arr.getJSONObject(i)
            Conversation(
                id = obj.getString("id"),
                title = obj.optString("title", "未命名"),
                updatedAt = obj.optString("updated_at", ""),
                messageCount = obj.optInt("message_count", 0),
                archived = obj.optBoolean("archived", false),
            )
        }
    }

    suspend fun getActiveThreadId(): String? = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$baseUrl/conversations").get().build()
        val response = client.newCall(request).execute()
        val body = response.body?.string() ?: "{}"
        val json = JSONObject(body)
        json.optString("active_thread_id", null)
    }

    suspend fun newConversation(): String = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/conversations/new")
            .post("{}".toRequestBody(jsonMediaType))
            .build()
        val response = client.newCall(request).execute()
        val json = JSONObject(response.body?.string() ?: "{}")
        json.getString("thread_id")
    }

    suspend fun switchConversation(threadId: String): Conversation = withContext(Dispatchers.IO) {
        val body = JSONObject().put("thread_id", threadId).toString()
        val request = Request.Builder()
            .url("$baseUrl/conversations/switch")
            .post(body.toRequestBody(jsonMediaType))
            .build()
        val response = client.newCall(request).execute()
        val json = JSONObject(response.body?.string() ?: "{}")
        Conversation(
            id = json.getString("thread_id"),
            title = json.optString("title", "未命名"),
            updatedAt = "",
            messageCount = json.optInt("message_count", 0),
        )
    }

    suspend fun deleteConversation(threadId: String): Boolean = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url("$baseUrl/conversations/$threadId")
            .delete()
            .build()
        val response = client.newCall(request).execute()
        val json = JSONObject(response.body?.string() ?: "{}")
        json.optBoolean("deleted", false)
    }

    suspend fun getMessages(threadId: String): List<Message> = withContext(Dispatchers.IO) {
        val request = Request.Builder().url("$baseUrl/messages/$threadId").get().build()
        val response = client.newCall(request).execute()
        val body = response.body?.string() ?: "{}"
        val json = JSONObject(body)
        val arr = json.getJSONArray("messages")
        (0 until arr.length()).map { i ->
            val obj = arr.getJSONObject(i)
            Message(
                id = i.toString(),
                role = when (obj.getString("role")) {
                    "user" -> MessageRole.User
                    else -> MessageRole.Assistant
                },
                content = obj.getString("content"),
            )
        }
    }

    fun postChat(message: String): okhttp3.Response {
        val body = JSONObject().put("message", message).toString()
        val request = Request.Builder()
            .url("$baseUrl/chat")
            .post(body.toRequestBody(jsonMediaType))
            .header("Accept", "text/event-stream")
            .build()
        return client.newCall(request).execute()
    }
}
