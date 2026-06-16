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

    fun setServerUrl(url: String) {
        viewModelScope.launch {
            val normalized = url.trimEnd('/')
            settingsStore.setServerUrl(normalized)
            apiClient = ApiClient(normalized)
            _uiState.update { it.copy(serverConfigured = true, serverUrl = normalized) }
            loadConversations()
        }
    }

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

    fun clearError() {
        _uiState.update { it.copy(errorMessage = null) }
    }

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
                    output = null,
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
                loadConversations()
            }

            is SseEvent.Error -> {
                _uiState.update { state ->
                    state.copy(
                        isStreaming = false,
                        errorMessage = event.message,
                        messages = state.messages.map { msg ->
                            if (msg.id == assistantMsgId) msg.copy(
                                isStreaming = false,
                                content = msg.content + "\n\n⚠ ${event.message}"
                            ) else msg
                        }
                    )
                }
            }

            is SseEvent.Thinking -> { /* no-op */ }
        }
    }
}
