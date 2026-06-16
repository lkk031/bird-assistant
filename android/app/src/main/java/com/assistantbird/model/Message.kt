package com.assistantbird.model

enum class MessageRole { User, Assistant, System }

data class Message(
    val id: String,
    val role: MessageRole,
    val content: String,
    val agentName: String? = null,
    val toolCards: List<ToolCardData> = emptyList(),
    val isStreaming: Boolean = false,
)

data class ToolCardData(
    val id: String,
    val name: String,
    val output: String? = null,
)
