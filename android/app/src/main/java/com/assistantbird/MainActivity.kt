package com.assistantbird

import android.content.Intent
import android.net.Uri
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
                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse("${uiState.serverUrl}/export/$threadId"))
                            startActivity(intent)
                        },
                    )
                }
            }
        }
    }
}
