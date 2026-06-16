package com.assistantbird.ui.component

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
                placeholder = { Text("输入消息…", color = TextMuted) },
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
