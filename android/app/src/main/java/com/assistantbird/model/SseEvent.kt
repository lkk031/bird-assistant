package com.assistantbird.model

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
