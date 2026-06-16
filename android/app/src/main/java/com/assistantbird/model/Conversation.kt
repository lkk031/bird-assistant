package com.assistantbird.model

data class Conversation(
    val id: String,
    val title: String,
    val updatedAt: String,
    val messageCount: Int,
    val archived: Boolean = false,
)
