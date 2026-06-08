/**
 * Main application controller for the desktop chat UI.
 *
 * Manages application state, wires up the SSE streaming client
 * to the component builders, and handles all user interactions.
 */
(function () {
  "use strict";

  // ── DOM References ──────────────────────────────────────────────────
  var messageInput = document.getElementById("message-input");
  var sendBtn = document.getElementById("send-btn");
  var newChatBtn = document.getElementById("new-chat-btn");
  var manageBtn = document.getElementById("manage-btn");
  var manageHint = document.getElementById("manage-hint");
  var exportBtn = document.getElementById("export-btn");
  var convoList = document.getElementById("conversation-list");
  var statusDot = document.getElementById("status-indicator");
  var fileInput = document.getElementById("file-input");
  var attachBtn = document.getElementById("attach-btn");

  // ── Application State ───────────────────────────────────────────────
  var state = {
    conversations: [],
    activeThreadId: null,
    isStreaming: false,
    managing: false,
    streamController: null,
    currentAssistantMsg: null,
    currentAgent: null,
    fullResponse: "",
    hasContent: false,
  };

  // ── Status Indicator ────────────────────────────────────────────────
  function setStatus(status) {
    statusDot.className = "status-dot " + status;
  }

  // ── Load Conversations ──────────────────────────────────────────────
  function loadConversations() {
    fetch("/conversations")
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        state.conversations = data.conversations || [];
        state.activeThreadId = data.active_thread_id;
        Components.renderConversationList(state.conversations, state.activeThreadId);
        exportBtn.disabled = !state.activeThreadId;
      })
      .catch(function (err) {
        console.error("Failed to load conversations:", err);
      });
  }

  // ── Send Message ────────────────────────────────────────────────────
  function sendMessage() {
    var text = messageInput.value.trim();
    if (!text || state.isStreaming) return;

    // Disable input during streaming
    messageInput.value = "";
    messageInput.style.height = "auto";
    setStatus("streaming");
    state.isStreaming = true;
    state.fullResponse = "";
    state.hasContent = false;
    sendBtn.disabled = true;
    sendBtn.classList.add("stop");

    // Render user message
    Components.appendToChat(Components.createUserMessage(text));

    // Create assistant message container for streaming
    var assistant = Components.createAssistantMessage();
    Components.appendToChat(assistant.container);
    state.currentAssistantMsg = assistant;

    // Start SSE streaming
    state.streamController = StreamClient.postSSE(
      "/chat",
      { message: text },
      {
        onToken: handleToken,
        onAgentSwitch: handleAgentSwitch,
        onToolStart: handleToolStart,
        onToolEnd: handleToolEnd,
        onThinking: handleThinking,
        onSystem: handleSystem,
        onDone: handleDone,
        onError: handleError,
      }
    );
  }

  // ── SSE Event Handlers ──────────────────────────────────────────────

  function handleToken(text) {
    state.hasContent = true;
    state.fullResponse += text;
    var content = state.currentAssistantMsg.content;

    // Append token as text — add streaming cursor class
    content.classList.add("streaming-cursor");

    // For simple text streaming, we append to a text node
    content.appendChild(document.createTextNode(text));

    Components.scrollToBottom();
  }

  function handleAgentSwitch(data) {
    state.currentAgent = data.agent;
    Components.showAgentBadge(state.currentAssistantMsg.agentBadge, data.display);
  }

  function handleToolStart(data) {
    var toolCard = Components.createToolCard(data.name);
    Components.appendToChat(toolCard.card);

    // Store reference on the assistant message for later updates
    if (!state.currentAssistantMsg._toolCards) {
      state.currentAssistantMsg._toolCards = [];
    }
    state.currentAssistantMsg._toolCards.push(toolCard);
  }

  function handleToolEnd(data) {
    // Find the matching tool card and update it
    var cards = state.currentAssistantMsg._toolCards || [];
    for (var i = cards.length - 1; i >= 0; i--) {
      if (cards[i].body.textContent === "运行中…") {
        cards[i].setOutput(data.output);
        break;
      }
    }
  }

  function handleThinking(data) {
    // Thinking indicator — could show a subtle animation
    // For now, this just confirms streaming has started
  }

  function handleSystem(data) {
    Components.appendToChat(Components.createSystemMessage(data.message));
  }

  function handleDone(data) {
    finishStreaming();

    if (data.aborted) {
      if (state.hasContent) {
        var content = state.currentAssistantMsg.content;
        content.appendChild(
          document.createTextNode("\n\n⚠️ (已中止)")
        );
      }
    }

    // Finalize: render accumulated markdown
    finalizeAssistantMessage();

    // Reload conversation list to reflect new message counts
    loadConversations();
  }

  function handleError(data) {
    finishStreaming();

    if (state.hasContent) {
      var content = state.currentAssistantMsg.content;
      content.appendChild(
        document.createTextNode("\n\n⚠️ " + (data.message || "出错"))
      );
      finalizeAssistantMessage();
    } else {
      Components.appendToChat(
        Components.createSystemMessage("⚠️ " + (data.message || "处理出错，请重试。"))
      );
    }
  }

  // ── Message Finalization ────────────────────────────────────────────

  function finalizeAssistantMessage() {
    if (!state.currentAssistantMsg) return;

    var content = state.currentAssistantMsg.content;
    content.classList.remove("streaming-cursor");

    // Replace text content with rendered markdown
    if (state.fullResponse && typeof marked !== "undefined") {
      content.innerHTML = Components.renderMarkdown(state.fullResponse);
    }
  }

  function finishStreaming() {
    state.isStreaming = false;
    state.streamController = null;
    setStatus("connected");
    sendBtn.disabled = false;
    sendBtn.classList.remove("stop");
    messageInput.focus();
  }

  // ── Stop Streaming ──────────────────────────────────────────────────
  function stopStreaming() {
    if (state.streamController) {
      state.streamController.abort();
      state.streamController = null;
    }
    finishStreaming();

    // Finalize what we have so far
    if (state.hasContent && state.currentAssistantMsg) {
      finalizeAssistantMessage();
    }
  }

  // ── New Conversation ────────────────────────────────────────────────
  function newConversation() {
    if (state.isStreaming) {
      stopStreaming();
    }

    fetch("/conversations/new", { method: "POST" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        state.activeThreadId = data.thread_id;
        state.currentAssistantMsg = null;
        state.fullResponse = "";
        state.hasContent = false;
        Components.clearChat();
        loadConversations();
      })
      .catch(function (err) {
        console.error("Failed to create new conversation:", err);
      });
  }

  // ── Switch Conversation ─────────────────────────────────────────────
  function switchConversation(threadId) {
    if (threadId === state.activeThreadId) return;
    if (state.isStreaming) {
      stopStreaming();
    }

    fetch("/conversations/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function () {
        state.activeThreadId = threadId;
        Components.updateActiveConversation(threadId);

        // Load and replay messages
        return fetch("/messages/" + threadId);
      })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        Components.clearChat();
        var messages = data.messages || [];
        messages.forEach(function (msg) {
          if (msg.role === "user") {
            Components.appendToChat(
              Components.createUserMessage(msg.content)
            );
          } else if (msg.role === "assistant") {
            var assistant = Components.createAssistantMessage();
            assistant.content.innerHTML =
              Components.renderMarkdown(msg.content);
            Components.appendToChat(assistant.container);
          }
        });

        if (messages.length === 0) {
          Components.showWelcome();
        }

        Components.scrollToBottom();
        exportBtn.disabled = false;
      })
      .catch(function (err) {
        console.error("Failed to switch conversation:", err);
      });
  }

  // ── Delete Conversation ──────────────────────────────────────────────
  function deleteConversation(threadId) {
    if (!confirm("确定要删除此对话吗？此操作不可撤销。")) return;

    fetch("/conversations/" + threadId, { method: "DELETE" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.deleted) {
          // If the deleted conversation was active, refresh UI
          if (threadId === state.activeThreadId) {
            state.activeThreadId = null;
            state.currentAssistantMsg = null;
            state.fullResponse = "";
            state.hasContent = false;
            Components.clearChat();
          }
          loadConversations();
        }
      })
      .catch(function (err) {
        console.error("Failed to delete conversation:", err);
      });
  }

  // ── Export Conversation ─────────────────────────────────────────────
  function exportConversation() {
    if (!state.activeThreadId) return;

    // Open export as download
    var a = document.createElement("a");
    a.href = "/export/" + state.activeThreadId;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ── File Upload ─────────────────────────────────────────────────────
  function handleFileUpload(file) {
    var formData = new FormData();
    formData.append("file", file);

    fetch("/upload", {
      method: "POST",
      body: formData,
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data.file_path) {
          // Pre-fill the input with context about the uploaded file
          messageInput.value =
            "我上传了一个文件: " + data.file_path + "\n\n请帮我分析这个文件。";
          messageInput.focus();
        }
      })
      .catch(function (err) {
        console.error("Upload failed:", err);
      });
  }

  // ── Event Listeners ─────────────────────────────────────────────────

  // Send button
  sendBtn.addEventListener("click", function () {
    if (state.isStreaming) {
      stopStreaming();
    } else {
      sendMessage();
    }
  });

  // Enter to send, Shift+Enter for newline
  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (state.isStreaming) {
        stopStreaming();
      } else {
        sendMessage();
      }
    }
  });

  // Auto-resize textarea
  messageInput.addEventListener("input", function () {
    messageInput.style.height = "auto";
    messageInput.style.height =
      Math.min(messageInput.scrollHeight, 150) + "px";
  });

  // Manage mode toggle
  manageBtn.addEventListener("click", function () {
    state.managing = !state.managing;
    var sidebar = document.getElementById("sidebar");
    if (state.managing) {
      sidebar.classList.add("managing");
      manageBtn.textContent = "✅ 完成";
      manageBtn.classList.add("active");
      manageHint.style.display = "inline";
    } else {
      sidebar.classList.remove("managing");
      manageBtn.textContent = "✏️ 管理";
      manageBtn.classList.remove("active");
      manageHint.style.display = "none";
    }
  });

  // New conversation button
  newChatBtn.addEventListener("click", newConversation);

  // Export button
  exportBtn.addEventListener("click", exportConversation);

  // Conversation list clicks (delegation)
  convoList.addEventListener("click", function (e) {
    var item = e.target.closest(".convo-item");
    if (item && item.dataset.threadId) {
      switchConversation(item.dataset.threadId);
    }
  });

  // File upload
  attachBtn.addEventListener("click", function () {
    fileInput.click();
  });

  fileInput.addEventListener("change", function () {
    if (fileInput.files && fileInput.files[0]) {
      handleFileUpload(fileInput.files[0]);
      fileInput.value = "";
    }
  });

  // Keyboard shortcuts
  document.addEventListener("keydown", function (e) {
    // Ctrl+N: New conversation
    if (e.ctrlKey && e.key === "n") {
      e.preventDefault();
      newConversation();
    }
    // Ctrl+E: Export
    if (e.ctrlKey && e.key === "e") {
      e.preventDefault();
      exportConversation();
    }
    // Ctrl+L: Focus input
    if (e.ctrlKey && e.key === "l") {
      e.preventDefault();
      messageInput.focus();
    }
    // Escape: Stop streaming
    if (e.key === "Escape" && state.isStreaming) {
      e.preventDefault();
      stopStreaming();
    }
  });

  // ── Initialization ──────────────────────────────────────────────────
  function init() {
    loadConversations();
    messageInput.focus();
    setStatus("connected");
  }

  // Expose for external callers (e.g., components.js)
  window.App = {
    deleteConversation: deleteConversation,
  };

  // Start when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
