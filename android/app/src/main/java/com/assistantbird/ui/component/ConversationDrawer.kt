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
                    onDelete = { onDeleteConversation(convo.id) },
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
