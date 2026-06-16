package com.assistantbird.ui.screen

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
                onClose = { scope.launch { drawerState.close() } },
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
                            Text(uiState.serverUrl, fontSize = 11.sp, color = TextMuted)
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Default.Menu, contentDescription = "对话列表", tint = TextSecondary)
                        }
                    },
                    actions = {
                        if (uiState.activeThreadId != null) {
                            IconButton(onClick = { onShowExport(uiState.activeThreadId) }) {
                                Icon(Icons.Default.MoreVert, contentDescription = "导出", tint = TextSecondary)
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = BgSidebar),
                )
            },
            containerColor = BgPrimary,
        ) { padding ->
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
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

                InputArea(
                    isStreaming = uiState.isStreaming,
                    onSend = onSendMessage,
                    onStop = onStopStreaming,
                )
            }
        }
    }
}
