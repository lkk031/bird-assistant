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
