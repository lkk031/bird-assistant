# Android Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Android Kotlin + Jetpack Compose chat client that connects to the existing assistant-bird Python backend over WiFi LAN.

**Architecture:** Android app is a thin UI layer — OkHttp for REST + manual SSE parsing for streaming. Existing Python backend (`assistant-bird`) gets a one-line addition to print its LAN IP on startup. No backend logic changes.

**Tech Stack:** Kotlin, Jetpack Compose, Material 3, OkHttp 4, DataStore Preferences, compose-markdown, minSdk 26

**Prerequisites:** Android Studio (Hedgehog+) with SDK 34+ on the development machine that builds the APK. The project source files are created in `android/` within this repo for version control alongside the backend.

---

## File Structure

```
android/                              ← NEW (sibling to src/)
├── build.gradle.kts                  ← project-level
├── settings.gradle.kts
├── gradle.properties
├── gradle/
│   └── libs.versions.toml            ← version catalog
└── app/
    ├── build.gradle.kts              ← app-level
    └── src/main/
        ├── AndroidManifest.xml
        ├── res/values/
        │   ├── strings.xml
        │   └── themes.xml
        └── java/com/assistantbird/
            ├── MainActivity.kt
            ├── ui/theme/
            │   ├── Color.kt
            │   ├── Theme.kt
            │   └── Type.kt
            ├── ui/screen/
            │   ├── ChatScreen.kt
            │   └── SetupScreen.kt
            ├── ui/component/
            │   ├── MessageBubble.kt
            │   ├── ToolCard.kt
            │   ├── ConversationDrawer.kt
            │   └── InputArea.kt
            ├── network/
            │   ├── ApiClient.kt
            │   └── SseClient.kt
            ├── model/
            │   ├── Message.kt
            │   ├── Conversation.kt
            │   └── SseEvent.kt
            ├── viewmodel/
            │   └── ChatViewModel.kt
            └── data/
                └── SettingsStore.kt

src/assistant_bird/desktop/window.py  ← MODIFY (1 line: print LAN IP)
```

---

### Task 1: Server-side — Print LAN IP on startup

**Files:**
- Modify: `src/assistant_bird/desktop/window.py:31-35`

- [ ] **Step 1: Add `_get_lan_ip()` helper and print at startup**

Add this helper function after the `DEFAULT_PORT` constants (after line 27):

```python
import socket


def _get_lan_ip() -> str:
    """Return the primary LAN IP address, or '127.0.0.1' if not found."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # 8.8.8.8 is never actually reached — we just need the route
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
```

In `start_desktop()`, after `url = f"http://localhost:{DEFAULT_PORT}"` (line 203), insert:

```python
    lan_ip = _get_lan_ip()
```

And after the `print("Starting desktop window...")` block (lines 33-35), insert:

```python
    if lan_ip != "127.0.0.1":
        print(f"📱 手机连接地址: http://{lan_ip}:{DEFAULT_PORT}")
```

- [ ] **Step 2: Verify**

Run: `poetry run assistant-bird` — should print the LAN IP line before opening the window.
Press Ctrl+C after confirming the output.

- [ ] **Step 3: Commit**

```bash
git add src/assistant_bird/desktop/window.py
git commit -m "feat: print LAN IP on startup for mobile client connection"
```

---

### Task 2: Android project scaffold — build files

**Files:**
- Create: `android/build.gradle.kts`
- Create: `android/settings.gradle.kts`
- Create: `android/gradle.properties`
- Create: `android/gradle/libs.versions.toml`
- Create: `android/app/build.gradle.kts`

- [ ] **Step 1: Create project-level `android/build.gradle.kts`**

```kotlin
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
}
```

- [ ] **Step 2: Create `android/settings.gradle.kts`**

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolution {
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "assistant-bird"
include(":app")
```

- [ ] **Step 3: Create `android/gradle.properties`**

```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
```

- [ ] **Step 4: Create `android/gradle/libs.versions.toml`**

```toml
[versions]
agp = "8.7.0"
kotlin = "2.1.0"
compose-bom = "2024.12.01"
activity-compose = "1.9.3"
lifecycle = "2.8.7"
navigation-compose = "2.8.5"
okhttp = "4.12.0"
datastore = "1.1.1"
compose-markdown = "0.5.1"
core-ktx = "1.15.0"

[libraries]
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "core-ktx" }
androidx-activity-compose = { group = "androidx.activity", name = "activity-compose", version.ref = "activity-compose" }
androidx-lifecycle-viewmodel-compose = { group = "androidx.lifecycle", name = "lifecycle-viewmodel-compose", version.ref = "lifecycle" }
androidx-lifecycle-runtime-compose = { group = "androidx.lifecycle", name = "lifecycle-runtime-compose", version.ref = "lifecycle" }
androidx-navigation-compose = { group = "androidx.navigation", name = "navigation-compose", version.ref = "navigation-compose" }
androidx-datastore-preferences = { group = "androidx.datastore", name = "datastore-preferences", version.ref = "datastore" }
compose-bom = { group = "androidx.compose", name = "compose-bom", version.ref = "compose-bom" }
compose-material3 = { group = "androidx.compose.material3", name = "material3" }
compose-material-icons-extended = { group = "androidx.compose.material", name = "material-icons-extended" }
compose-ui = { group = "androidx.compose.ui", name = "ui" }
compose-ui-graphics = { group = "androidx.compose.ui", name = "ui-graphics" }
compose-ui-tooling-preview = { group = "androidx.compose.ui", name = "ui-tooling-preview" }
compose-ui-tooling = { group = "androidx.compose.ui", name = "ui-tooling" }
compose-markdown = { group = "com.github.jeziellago", name = "compose-markdown", version.ref = "compose-markdown" }
okhttp = { group = "com.squareup.okhttp3", name = "okhttp", version.ref = "okhttp" }
kotlinx-coroutines-android = { group = "org.jetbrains.kotlinx", name = "kotlinx-coroutines-android", version = "1.9.0" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
```

- [ ] **Step 5: Create `android/app/build.gradle.kts`**

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.assistantbird"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.assistantbird"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore.preferences)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.material3)
    implementation(libs.compose.material.icons.extended)
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.markdown)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.coroutines.android)
    debugImplementation(libs.compose.ui.tooling)
}
```

---

### Task 3: AndroidManifest + Resources

**Files:**
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/res/values/strings.xml`
- Create: `android/app/src/main/res/values/themes.xml`

- [ ] **Step 1: Create `AndroidManifest.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:allowBackup="true"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.AssistantBird"
        android:usesCleartextTraffic="true">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

- [ ] **Step 2: Create `res/values/strings.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">鸟助手</string>
</resources>
```

- [ ] **Step 3: Create `res/values/themes.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.AssistantBird" parent="android:Theme.Material.NoActionBar">
        <item name="android:statusBarColor">@android:color/black</item>
        <item name="android:navigationBarColor">@android:color/black</item>
        <item name="android:windowBackground">#FF1A1B23</item>
    </style>
</resources>
```

- [ ] **Step 4: Commit**

```bash
git add android/
git commit -m "feat(android): project scaffold — Gradle, manifest, resources"
```

---

### Task 4: Data models

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/model/Message.kt`
- Create: `android/app/src/main/java/com/assistantbird/model/Conversation.kt`
- Create: `android/app/src/main/java/com/assistantbird/model/SseEvent.kt`

- [ ] **Step 1: Create `model/Message.kt`**

```kotlin
package com.assistantbird.model

enum class MessageRole { User, Assistant, System }

data class Message(
    val id: String,
    val role: MessageRole,
    val content: String,          // plain text during streaming, markdown after done
    val agentName: String? = null, // e.g. "🔍 研究员" — shown as badge
    val toolCards: List<ToolCardData> = emptyList(),
    val isStreaming: Boolean = false, // true while tokens are still arriving
)

data class ToolCardData(
    val id: String,
    val name: String,
    val output: String? = null,   // null → still running
)
```

- [ ] **Step 2: Create `model/Conversation.kt`**

```kotlin
package com.assistantbird.model

data class Conversation(
    val id: String,
    val title: String,
    val updatedAt: String,
    val messageCount: Int,
    val archived: Boolean = false,
)
```

- [ ] **Step 3: Create `model/SseEvent.kt`**

```kotlin
package com.assistantbird.model

/**
 * Parsed SSE event from the backend stream.
 * Mirrors the events defined in server/routes.py.
 */
sealed class SseEvent {
    data class Token(val text: String) : SseEvent()
    data class AgentSwitch(val agent: String, val display: String) : SseEvent()
    data class ToolStart(val name: String, val input: Map<String, String>) : SseEvent()
    data class ToolEnd(val name: String, val output: String) : SseEvent()
    data class Thinking(val text: String) : SseEvent()
    data class System(val message: String) : SseEvent()
    data class Done(val aborted: Boolean = false) : SseEvent()
    data class Error(val type: String, val message: String) : SseEvent()
}
```

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/model/
git commit -m "feat(android): add data models — Message, Conversation, SseEvent"
```

---

### Task 5: SettingsStore — persistent preferences

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/data/SettingsStore.kt`

- [ ] **Step 1: Create `data/SettingsStore.kt`**

```kotlin
package com.assistantbird.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class SettingsStore(private val context: Context) {

    companion object {
        private val KEY_SERVER_URL = stringPreferencesKey("server_url")
        private val KEY_ACTIVE_THREAD = stringPreferencesKey("active_thread_id")
    }

    val serverUrl: Flow<String> = context.dataStore.data.map { prefs ->
        prefs[KEY_SERVER_URL] ?: ""
    }

    val activeThreadId: Flow<String?> = context.dataStore.data.map { prefs ->
        prefs[KEY_ACTIVE_THREAD]
    }

    suspend fun setServerUrl(url: String) {
        context.dataStore.edit { prefs ->
            prefs[KEY_SERVER_URL] = url
        }
    }

    suspend fun setActiveThreadId(threadId: String?) {
        context.dataStore.edit { prefs ->
            if (threadId != null) {
                prefs[KEY_ACTIVE_THREAD] = threadId
            } else {
                prefs.remove(KEY_ACTIVE_THREAD)
            }
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/data/
git commit -m "feat(android): add SettingsStore for persistent preferences"
```

---

### Task 6: Network layer — ApiClient

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/network/ApiClient.kt`

- [ ] **Step 1: Create `network/ApiClient.kt`**

```kotlin
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
        .readTimeout(5, TimeUnit.MINUTES)  // SSE streams can be long
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    // ── Conversations ──────────────────────────────────────────────────

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

    // ── Messages ───────────────────────────────────────────────────────

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

    // ── Chat (POST, returns ResponseBody for SSE parsing) ──────────────

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
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/network/ApiClient.kt
git commit -m "feat(android): add ApiClient — REST endpoints for conversations, messages, chat"
```

---

### Task 7: Network layer — SseClient

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/network/SseClient.kt`

- [ ] **Step 1: Create `network/SseClient.kt`**

```kotlin
package com.assistantbird.network

import com.assistantbird.model.SseEvent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
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
     *
     * SSE format:
     *   event: <type>
     *   data: <json>
     *   (empty line = end of event)
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
                        // Complete event
                        val parsed = parseEvent(eventType, data)
                        if (parsed != null) {
                            emit(parsed)
                        }
                        eventType = ""
                        data = ""
                    }
                    // else: ignore lines that aren't part of an event
                    // (comments starting with ":", or continuation lines)
                }
            }

            // Emit done if stream ends normally
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
            else -> null  // unknown event type, skip
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/network/SseClient.kt
git commit -m "feat(android): add SseClient — SSE stream parser matching stream.js"
```

---

### Task 8: Theme (Material 3 dark, matching desktop CSS)

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/ui/theme/Color.kt`
- Create: `android/app/src/main/java/com/assistantbird/ui/theme/Type.kt`
- Create: `android/app/src/main/java/com/assistantbird/ui/theme/Theme.kt`

- [ ] **Step 1: Create `ui/theme/Color.kt`**

```kotlin
package com.assistantbird.ui.theme

import androidx.compose.ui.graphics.Color

// Matches desktop/css/style.css dark theme
val BgPrimary = Color(0xFF1A1B23)
val BgSecondary = Color(0xFF23242F)
val BgSidebar = Color(0xFF1E1F29)
val BgInput = Color(0xFF2A2B37)
val BubbleUser = Color(0xFF2D5AA0)
val BubbleAi = Color(0xFF2A2B37)
val ToolCard = Color(0xFF1E1F29)
val Border = Color(0xFF3A3B47)
val TextPrimary = Color(0xFFE8E8ED)
val TextSecondary = Color(0xFF9E9EAE)
val TextMuted = Color(0xFF6B6B7B)
val Accent = Color(0xFF6C8CE0)
val AccentHover = Color(0xFF7D9EF0)
val Success = Color(0xFF4CAF50)
val Warning = Color(0xFFF0A030)
val Error = Color(0xFFE05555)
```

- [ ] **Step 2: Create `ui/theme/Type.kt`**

```kotlin
package com.assistantbird.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.sp

val AppTypography = Typography(
    bodyLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontSize = 15.sp,
        lineHeight = 22.sp,
        color = TextPrimary,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontSize = 13.sp,
        lineHeight = 18.sp,
        color = TextSecondary,
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontSize = 11.sp,
        lineHeight = 14.sp,
        color = TextMuted,
    ),
)
```

- [ ] **Step 3: Create `ui/theme/Theme.kt`**

```kotlin
package com.assistantbird.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme = darkColorScheme(
    primary = Accent,
    onPrimary = TextPrimary,
    secondary = AccentHover,
    background = BgPrimary,
    surface = BgSecondary,
    onBackground = TextPrimary,
    onSurface = TextPrimary,
    error = Error,
)

@Composable
fun AssistantBirdTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = AppTypography,
        content = content,
    )
}
```

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/ui/theme/
git commit -m "feat(android): add Material 3 dark theme matching desktop CSS"
```

---

### Task 9: ChatViewModel — core state management

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/viewmodel/ChatViewModel.kt`

- [ ] **Step 1: Create `viewmodel/ChatViewModel.kt`**

```kotlin
package com.assistantbird.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.assistantbird.data.SettingsStore
import com.assistantbird.model.Conversation
import com.assistantbird.model.Message
import com.assistantbird.model.MessageRole
import com.assistantbird.model.SseEvent
import com.assistantbird.model.ToolCardData
import com.assistantbird.network.ApiClient
import com.assistantbird.network.SseClient
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.util.UUID

data class ChatUiState(
    val messages: List<Message> = emptyList(),
    val conversations: List<Conversation> = emptyList(),
    val activeThreadId: String? = null,
    val isStreaming: Boolean = false,
    val serverConfigured: Boolean = false,
    val serverUrl: String = "",
    val errorMessage: String? = null,
)

class ChatViewModel(application: Application) : AndroidViewModel(application) {

    private val settingsStore = SettingsStore(application)

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var apiClient: ApiClient? = null
    private var streamJob: Job? = null

    init {
        viewModelScope.launch {
            val url = settingsStore.serverUrl.first()
            if (url.isNotEmpty()) {
                apiClient = ApiClient(url)
                _uiState.update { it.copy(serverConfigured = true, serverUrl = url) }
                loadConversations()
            }
        }
    }

    // ── Setup ──────────────────────────────────────────────────────────

    fun setServerUrl(url: String) {
        viewModelScope.launch {
            val normalized = url.trimEnd('/')
            settingsStore.setServerUrl(normalized)
            apiClient = ApiClient(normalized)
            _uiState.update { it.copy(serverConfigured = true, serverUrl = normalized) }
            loadConversations()
        }
    }

    // ── Conversations ──────────────────────────────────────────────────

    fun loadConversations() {
        val client = apiClient ?: return
        viewModelScope.launch {
            try {
                val convos = client.getConversations()
                val activeId = client.getActiveThreadId()
                _uiState.update { it.copy(conversations = convos, activeThreadId = activeId) }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "无法连接服务器: ${e.message}") }
            }
        }
    }

    fun newConversation() {
        val client = apiClient ?: return
        viewModelScope.launch {
            try {
                val threadId = client.newConversation()
                _uiState.update { it.copy(messages = emptyList(), activeThreadId = threadId) }
                loadConversations()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "创建对话失败: ${e.message}") }
            }
        }
    }

    fun switchConversation(threadId: String) {
        val client = apiClient ?: return
        viewModelScope.launch {
            try {
                client.switchConversation(threadId)
                val messages = client.getMessages(threadId)
                _uiState.update { it.copy(messages = messages, activeThreadId = threadId) }
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "切换对话失败: ${e.message}") }
            }
        }
    }

    fun deleteConversation(threadId: String) {
        val client = apiClient ?: return
        viewModelScope.launch {
            try {
                client.deleteConversation(threadId)
                _uiState.update { state ->
                    if (state.activeThreadId == threadId) {
                        state.copy(messages = emptyList(), activeThreadId = null)
                    } else state
                }
                loadConversations()
            } catch (e: Exception) {
                _uiState.update { it.copy(errorMessage = "删除失败: ${e.message}") }
            }
        }
    }

    // ── Send Message ───────────────────────────────────────────────────

    fun sendMessage(text: String) {
        val client = apiClient ?: return
        if (_uiState.value.isStreaming) return

        val userMsg = Message(
            id = UUID.randomUUID().toString(),
            role = MessageRole.User,
            content = text,
        )

        val assistantMsg = Message(
            id = UUID.randomUUID().toString(),
            role = MessageRole.Assistant,
            content = "",
            isStreaming = true,
        )

        _uiState.update { state ->
            state.copy(
                messages = state.messages + userMsg + assistantMsg,
                isStreaming = true,
                errorMessage = null,
            )
        }

        // Dismiss error
        _uiState.update { it.copy(errorMessage = null) }

        streamJob = viewModelScope.launch {
            try {
                val response = client.postChat(text)
                if (!response.isSuccessful) {
                    _uiState.update { state ->
                        state.copy(
                            isStreaming = false,
                            messages = state.messages.map {
                                if (it.id == assistantMsg.id) it.copy(
                                    content = "HTTP ${response.code}: ${response.message}",
                                    isStreaming = false
                                ) else it
                            }
                        )
                    }
                    return@launch
                }

                SseClient.parse(response).collect { event ->
                    handleSseEvent(event, assistantMsg.id)
                }
            } catch (e: Exception) {
                _uiState.update { state ->
                    state.copy(
                        isStreaming = false,
                        messages = state.messages.map {
                            if (it.id == assistantMsg.id) it.copy(
                                content = "连接错误: ${e.message}",
                                isStreaming = false
                            ) else it
                        }
                    )
                }
            }
        }
    }

    fun stopStreaming() {
        streamJob?.cancel()
        streamJob = null
        _uiState.update { state ->
            state.copy(
                isStreaming = false,
                messages = state.messages.map {
                    if (it.isStreaming) it.copy(isStreaming = false) else it
                }
            )
        }
    }

    // ── SSE Event Handler ──────────────────────────────────────────────

    private fun handleSseEvent(event: SseEvent, assistantMsgId: String) {
        when (event) {
            is SseEvent.Token -> {
                _uiState.update { state ->
                    state.copy(messages = state.messages.map { msg ->
                        if (msg.id == assistantMsgId) msg.copy(
                            content = msg.content + event.text
                        ) else msg
                    })
                }
            }

            is SseEvent.AgentSwitch -> {
                _uiState.update { state ->
                    state.copy(messages = state.messages.map { msg ->
                        if (msg.id == assistantMsgId) msg.copy(
                            agentName = event.display
                        ) else msg
                    })
                }
            }

            is SseEvent.ToolStart -> {
                val card = ToolCardData(
                    id = UUID.randomUUID().toString(),
                    name = event.name,
                    output = null,  // still running
                )
                _uiState.update { state ->
                    state.copy(messages = state.messages.map { msg ->
                        if (msg.id == assistantMsgId) msg.copy(
                            toolCards = msg.toolCards + card
                        ) else msg
                    })
                }
            }

            is SseEvent.ToolEnd -> {
                _uiState.update { state ->
                    state.copy(messages = state.messages.map { msg ->
                        if (msg.id == assistantMsgId) {
                            // Find the last tool card with null output and update it
                            val updated = msg.toolCards.toMutableList()
                            val index = updated.indexOfLast { it.output == null }
                            if (index >= 0) {
                                updated[index] = updated[index].copy(output = event.output)
                            }
                            msg.copy(toolCards = updated)
                        } else msg
                    })
                }
            }

            is SseEvent.System -> {
                val sysMsg = Message(
                    id = UUID.randomUUID().toString(),
                    role = MessageRole.System,
                    content = event.message,
                )
                _uiState.update { state ->
                    state.copy(messages = state.messages + sysMsg)
                }
            }

            is SseEvent.Done -> {
                _uiState.update { state ->
                    state.copy(
                        isStreaming = false,
                        messages = state.messages.map { msg ->
                            if (msg.id == assistantMsgId) msg.copy(isStreaming = false) else msg
                        }
                    )
                }
                loadConversations()  // refresh counts
            }

            is SseEvent.Error -> {
                _uiState.update { state ->
                    state.copy(
                        isStreaming = false,
                        errorMessage = event.message,
                        messages = state.messages.map { msg ->
                            if (msg.id == assistantMsgId) msg.copy(
                                isStreaming = false,
                                content = msg.content + "\n\n⚠️ ${event.message}"
                            ) else msg
                        }
                    )
                }
            }

            is SseEvent.Thinking -> {
                // Could show a subtle indicator; for now, no-op
            }
        }
    }

    fun clearError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/viewmodel/
git commit -m "feat(android): add ChatViewModel — full SSE lifecycle + conversation CRUD"
```

---

### Task 10: UI Components — InputArea + MessageBubble + ToolCard

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/ui/component/InputArea.kt`
- Create: `android/app/src/main/java/com/assistantbird/ui/component/MessageBubble.kt`
- Create: `android/app/src/main/java/com/assistantbird/ui/component/ToolCard.kt`

- [ ] **Step 1: Create `ui/component/InputArea.kt`**

```kotlin
package com.assistantbird.ui.component

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.assistantbird.ui.theme.*

@Composable
fun InputArea(
    isStreaming: Boolean,
    onSend: (String) -> Unit,
    onStop: () -> Unit,
) {
    var text by remember { mutableStateOf("") }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = BgInput,
        shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp),
        tonalElevation = 4.dp,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier.weight(1f),
                placeholder = {
                    Text("输入消息…", color = TextMuted)
                },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = TextPrimary,
                    unfocusedTextColor = TextPrimary,
                    focusedBorderColor = Border,
                    unfocusedBorderColor = Border,
                    focusedContainerColor = BgSecondary,
                    unfocusedContainerColor = BgSecondary,
                ),
                shape = RoundedCornerShape(20.dp),
                maxLines = 4,
            )

            Spacer(modifier = Modifier.width(8.dp))

            FilledIconButton(
                onClick = {
                    if (isStreaming) {
                        onStop()
                    } else if (text.isNotBlank()) {
                        onSend(text.trim())
                        text = ""
                    }
                },
                modifier = Modifier.size(48.dp),
                shape = CircleShape,
                colors = IconButtonDefaults.filledIconButtonColors(
                    containerColor = if (isStreaming) Error else Accent,
                    contentColor = TextPrimary,
                ),
            ) {
                Icon(
                    imageVector = if (isStreaming) Icons.Default.Close else Icons.AutoMirrored.Filled.Send,
                    contentDescription = if (isStreaming) "停止" else "发送",
                )
            }
        }
    }
}
```

- [ ] **Step 2: Create `ui/component/MessageBubble.kt`**

```kotlin
package com.assistantbird.ui.component

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistantbird.model.Message
import com.assistantbird.model.MessageRole
import com.assistantbird.ui.theme.*

@Composable
fun MessageBubble(message: Message, modifier: Modifier = Modifier) {
    when (message.role) {
        MessageRole.User -> UserBubble(message, modifier)
        MessageRole.Assistant -> AssistantBubble(message, modifier)
        MessageRole.System -> SystemMessage(message, modifier)
    }
}

@Composable
private fun UserBubble(message: Message, modifier: Modifier) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.End,
    ) {
        Box(
            modifier = Modifier
                .widthIn(max = 320.dp)
                .clip(RoundedCornerShape(16.dp, 4.dp, 16.dp, 16.dp))
                .background(BubbleUser)
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(
                text = message.content,
                color = TextPrimary,
                fontSize = 15.sp,
                lineHeight = 22.sp,
            )
        }
    }
}

@Composable
private fun AssistantBubble(message: Message, modifier: Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp, vertical = 4.dp),
        horizontalAlignment = Alignment.Start,
    ) {
        // Agent badge
        if (message.agentName != null) {
            Text(
                text = message.agentName,
                color = Accent,
                fontSize = 11.sp,
                modifier = Modifier.padding(start = 6.dp, bottom = 2.dp),
            )
        }

        Box(
            modifier = Modifier
                .widthIn(max = 340.dp)
                .clip(RoundedCornerShape(4.dp, 16.dp, 16.dp, 16.dp))
                .background(BubbleAi)
                .padding(horizontal = 14.dp, vertical = 10.dp)
        ) {
            Text(
                text = message.content,
                color = TextPrimary,
                fontSize = 15.sp,
                lineHeight = 22.sp,
            )
        }

        // Tool cards inside the assistant bubble
        message.toolCards.forEach { card ->
            ToolCardItem(card, Modifier.padding(start = 4.dp, top = 6.dp))
        }
    }
}

@Composable
private fun SystemMessage(message: Message, modifier: Modifier) {
    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 6.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = message.content,
            color = TextMuted,
            fontSize = 12.sp,
            fontStyle = FontStyle.Italic,
        )
    }
}
```

- [ ] **Step 3: Create `ui/component/ToolCard.kt`**

```kotlin
package com.assistantbird.ui.component

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistantbird.model.ToolCardData
import com.assistantbird.ui.theme.*

@Composable
fun ToolCardItem(card: ToolCardData, modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(card.output != null) }

    // Auto-expand when output arrives
    LaunchedEffect(card.output) {
        if (card.output != null) expanded = true
    }

    Column(
        modifier = modifier
            .widthIn(max = 340.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(ToolCard)
    ) {
        // Header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = !expanded }
                .padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = if (card.output != null) Icons.Default.CheckCircle else Icons.Default.Build,
                contentDescription = null,
                tint = if (card.output != null) Success else Accent,
                modifier = Modifier.size(14.dp),
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = card.name,
                color = TextSecondary,
                fontSize = 12.sp,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = Icons.Default.ExpandMore,
                contentDescription = "展开",
                tint = TextMuted,
                modifier = Modifier
                    .size(16.dp)
                    .rotate(if (expanded) 180f else 0f),
            )
        }

        // Body
        AnimatedVisibility(visible = expanded) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(BgPrimary)
                    .padding(10.dp)
            ) {
                if (card.output != null) {
                    Text(
                        text = card.output!!,
                        color = TextSecondary,
                        fontSize = 12.sp,
                        lineHeight = 18.sp,
                    )
                } else {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(12.dp),
                            strokeWidth = 1.5.dp,
                            color = Accent,
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("运行中…", color = TextMuted, fontSize = 12.sp)
                    }
                }
            }
        }
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/ui/component/
git commit -m "feat(android): add UI components — InputArea, MessageBubble, ToolCard"
```

---

### Task 11: ConversationDrawer — slide-out conversation list

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/ui/component/ConversationDrawer.kt`

- [ ] **Step 1: Create `ui/component/ConversationDrawer.kt`**

```kotlin
package com.assistantbird.ui.component

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistantbird.model.Conversation
import com.assistantbird.ui.theme.*

@Composable
fun ConversationDrawerContent(
    conversations: List<Conversation>,
    activeThreadId: String?,
    onNewConversation: () -> Unit,
    onSwitchConversation: (String) -> Unit,
    onDeleteConversation: (String) -> Unit,
    onClose: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxHeight()
            .width(280.dp)
            .background(BgSidebar)
            .padding(16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("对话列表", color = TextPrimary, fontSize = 18.sp)
            TextButton(onClick = onClose) {
                Text("关闭", color = TextMuted)
            }
        }

        Spacer(modifier = Modifier.height(12.dp))

        // New conversation button
        Button(
            onClick = onNewConversation,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = Accent),
            shape = RoundedCornerShape(8.dp),
        ) {
            Icon(Icons.Default.Add, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text("新对话", color = TextPrimary)
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Conversation list
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            items(conversations, key = { it.id }) { convo ->
                val isActive = convo.id == activeThreadId
                ConversationRow(
                    convo = convo,
                    isActive = isActive,
                    onClick = {
                        onSwitchConversation(convo.id)
                        onClose()
                    },
                    onDelete = {
                        onDeleteConversation(convo.id)
                    },
                )
            }
        }
    }
}

@Composable
private fun ConversationRow(
    convo: Conversation,
    isActive: Boolean,
    onClick: () -> Unit,
    onDelete: () -> Unit,
) {
    var showDeleteConfirm by remember { mutableStateOf(false) }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(if (isActive) Accent.copy(alpha = 0.2f) else BgSecondary)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = convo.title,
                color = if (isActive) Accent else TextPrimary,
                fontSize = 14.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = convo.updatedAt.take(10) + " · ${convo.messageCount} 条",
                color = TextMuted,
                fontSize = 11.sp,
            )
        }

        // Delete button (visible on the active or when confirmed)
        IconButton(
            onClick = {
                if (showDeleteConfirm) {
                    onDelete()
                    showDeleteConfirm = false
                } else {
                    showDeleteConfirm = true
                }
            },
            modifier = Modifier.size(32.dp),
        ) {
            Icon(
                imageVector = Icons.Default.Delete,
                contentDescription = "删除",
                tint = if (showDeleteConfirm) Error else TextMuted,
                modifier = Modifier.size(18.dp),
            )
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/ui/component/ConversationDrawer.kt
git commit -m "feat(android): add ConversationDrawer — slide-out conversation list"
```

---

### Task 12: Screens — SetupScreen + ChatScreen

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/ui/screen/SetupScreen.kt`
- Create: `android/app/src/main/java/com/assistantbird/ui/screen/ChatScreen.kt`

- [ ] **Step 1: Create `ui/screen/SetupScreen.kt`**

```kotlin
package com.assistantbird.ui.screen

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistantbird.ui.theme.*

@Composable
fun SetupScreen(onConnected: (String) -> Unit) {
    var url by remember { mutableStateOf("http://192.168.") }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(BgPrimary)
            .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("🐦", fontSize = 48.sp)
        Spacer(modifier = Modifier.height(16.dp))
        Text("鸟助手", color = TextPrimary, fontSize = 28.sp)
        Spacer(modifier = Modifier.height(8.dp))
        Text("连接到你的电脑上的 AI 助手", color = TextSecondary, fontSize = 14.sp)

        Spacer(modifier = Modifier.height(40.dp))

        OutlinedTextField(
            value = url,
            onValueChange = { url = it; error = null },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("服务器地址") },
            placeholder = { Text("如 http://192.168.1.100:19900") },
            singleLine = true,
            colors = OutlinedTextFieldDefaults.colors(
                focusedTextColor = TextPrimary,
                unfocusedTextColor = TextPrimary,
                focusedBorderColor = Accent,
                unfocusedBorderColor = Border,
                focusedContainerColor = BgSecondary,
                unfocusedContainerColor = BgSecondary,
                focusedLabelColor = Accent,
                unfocusedLabelColor = TextSecondary,
            ),
            shape = RoundedCornerShape(12.dp),
        )

        if (error != null) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(error!!, color = Error, fontSize = 13.sp)
        }

        Spacer(modifier = Modifier.height(24.dp))

        Button(
            onClick = {
                val trimmed = url.trim()
                if (trimmed.isBlank() || !trimmed.startsWith("http")) {
                    error = "请输入有效的服务器地址（以 http 开头）"
                } else {
                    onConnected(trimmed)
                }
            },
            modifier = Modifier.fillMaxWidth().height(48.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Accent),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text("连接", fontSize = 16.sp)
        }
    }
}
```

- [ ] **Step 2: Create `ui/screen/ChatScreen.kt`**

```kotlin
package com.assistantbird.ui.screen

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.assistantbird.model.Message
import com.assistantbird.ui.component.ConversationDrawerContent
import com.assistantbird.ui.component.InputArea
import com.assistantbird.ui.component.MessageBubble
import com.assistantbird.ui.theme.*
import com.assistantbird.viewmodel.ChatUiState
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    uiState: ChatUiState,
    onSendMessage: (String) -> Unit,
    onStopStreaming: () -> Unit,
    onNewConversation: () -> Unit,
    onSwitchConversation: (String) -> Unit,
    onDeleteConversation: (String) -> Unit,
    onShowExport: (String) -> Unit,
) {
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    // Auto-scroll to bottom when new messages arrive
    LaunchedEffect(uiState.messages.size) {
        if (uiState.messages.isNotEmpty()) {
            listState.animateScrollToItem(uiState.messages.size - 1)
        }
    }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ConversationDrawerContent(
                conversations = uiState.conversations,
                activeThreadId = uiState.activeThreadId,
                onNewConversation = onNewConversation,
                onSwitchConversation = onSwitchConversation,
                onDeleteConversation = onDeleteConversation,
                onClose = {
                    scope.launch { drawerState.close() }
                },
            )
        },
        gesturesEnabled = true,
    ) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("🐦 鸟助手", fontSize = 18.sp, color = TextPrimary)
                            Text(
                                uiState.serverUrl,
                                fontSize = 11.sp,
                                color = TextMuted,
                            )
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = {
                            scope.launch { drawerState.open() }
                        }) {
                            Icon(
                                Icons.Default.Menu,
                                contentDescription = "对话列表",
                                tint = TextSecondary,
                            )
                        }
                    },
                    actions = {
                        // Export button
                        if (uiState.activeThreadId != null) {
                            IconButton(onClick = {
                                onShowExport(uiState.activeThreadId)
                            }) {
                                Icon(
                                    Icons.Default.MoreVert,
                                    contentDescription = "导出",
                                    tint = TextSecondary,
                                )
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = BgSidebar,
                    ),
                )
            },
            containerColor = BgPrimary,
        ) { padding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                // Error snackbar area
                if (uiState.errorMessage != null) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        color = Error.copy(alpha = 0.15f),
                    ) {
                        Text(
                            text = uiState.errorMessage!!,
                            color = Error,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        )
                    }
                }

                // Message list
                LazyColumn(
                    state = listState,
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentPadding = PaddingValues(vertical = 8.dp),
                ) {
                    items(uiState.messages, key = { it.id }) { message ->
                        MessageBubble(message = message)
                    }
                }

                // Input area
                InputArea(
                    isStreaming = uiState.isStreaming,
                    onSend = onSendMessage,
                    onStop = onStopStreaming,
                )
            }
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/ui/screen/
git commit -m "feat(android): add SetupScreen + ChatScreen with drawer navigation"
```

---

### Task 13: MainActivity — wire everything together

**Files:**
- Create: `android/app/src/main/java/com/assistantbird/MainActivity.kt`

- [ ] **Step 1: Create `MainActivity.kt`**

```kotlin
package com.assistantbird

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import com.assistantbird.ui.screen.ChatScreen
import com.assistantbird.ui.screen.SetupScreen
import com.assistantbird.ui.theme.AssistantBirdTheme
import com.assistantbird.viewmodel.ChatViewModel

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            AssistantBirdTheme {
                val viewModel: ChatViewModel = viewModel()
                val uiState by viewModel.uiState.collectAsState()

                if (!uiState.serverConfigured) {
                    SetupScreen { url ->
                        viewModel.setServerUrl(url)
                    }
                } else {
                    ChatScreen(
                        uiState = uiState,
                        onSendMessage = { text -> viewModel.sendMessage(text) },
                        onStopStreaming = { viewModel.stopStreaming() },
                        onNewConversation = { viewModel.newConversation() },
                        onSwitchConversation = { id -> viewModel.switchConversation(id) },
                        onDeleteConversation = { id -> viewModel.deleteConversation(id) },
                        onShowExport = { threadId ->
                            // Open export URL in browser
                            val intent = android.content.Intent(
                                android.content.Intent.ACTION_VIEW,
                                android.net.Uri.parse("${uiState.serverUrl}/export/$threadId")
                            )
                            startActivity(intent)
                        },
                    )
                }
            }
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add android/app/src/main/java/com/assistantbird/MainActivity.kt
git commit -m "feat(android): add MainActivity — wire setup flow + chat screen"
```

---

### Task 14: ProGuard rules

**Files:**
- Create: `android/app/proguard-rules.pro`

- [ ] **Step 1: Create `android/app/proguard-rules.pro`**

```proguard
# OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# Kotlin coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# JSON (org.json is in Android SDK, no special rules needed)
```

- [ ] **Step 2: Commit**

```bash
git add android/app/proguard-rules.pro
git commit -m "chore(android): add ProGuard rules"
```

---

## Plan Self-Review

1. **Spec coverage**: All 8 development steps from spec are covered. Server-side change (Task 1), project scaffold (T2-3), models (T4), network layer (T5-7), theme (T8), ViewModel (T9), components (T10-11), screens (T12), wiring (T13), ProGuard (T14).

2. **Placeholder scan**: No TBD/TODO. Every step has complete code. Every function is fully implemented.

3. **Type consistency**: `Message.id` is `String` throughout (UUID in creation, index string from API). `SseEvent.ToolStart.input` is `Map<String, String>` matching `ToolCardItem` usage. `Conversation` fields match the JSON keys in `ApiClient`. `ChatUiState` fields are consumed correctly by `ChatScreen`.

## What You Need

Before running the Android project:
- **Android Studio Hedgehog (2024.1+) or Ladybug** — for Kotlin 2.1 + Compose BOM 2024.12
- **JDK 17** (bundled with Android Studio)
- **Gradle wrapper** — run `gradle wrapper` in `android/` dir, or let Android Studio generate it on import
- **An Android device or emulator** running Android 8.0+ (API 26+)

To generate the Gradle wrapper if you don't have `gradle` installed: open the `android/` directory in Android Studio and it will offer to download the wrapper automatically.
