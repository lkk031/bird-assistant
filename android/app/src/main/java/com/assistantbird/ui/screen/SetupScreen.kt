package com.assistantbird.ui.screen

import androidx.compose.foundation.background
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
