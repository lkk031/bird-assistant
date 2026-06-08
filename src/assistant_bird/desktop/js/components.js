/**
 * UI Component builders for the chat interface.
 *
 * Each function creates and returns a DOM element. No global state.
 */
var Components = (function () {
  "use strict";

  var chatContainer = document.getElementById("chat-container");
  var convoList = document.getElementById("conversation-list");

  // ── Message Bubbles ─────────────────────────────────────────────────

  /**
   * Create a user message bubble.
   * @param {string} text - The message content
   * @returns {HTMLElement} The message element
   */
  function createUserMessage(text) {
    var msg = document.createElement("div");
    msg.className = "message user";

    var content = document.createElement("div");
    content.className = "message-content";
    content.textContent = text;

    msg.appendChild(content);
    return msg;
  }

  /**
   * Create an assistant message container (for streaming into).
   * The returned element is the container; tokens append to .message-content.
   * @returns {{container: HTMLElement, content: HTMLElement, agentBadge: HTMLElement}}
   */
  function createAssistantMessage() {
    var msg = document.createElement("div");
    msg.className = "message assistant";

    var badge = document.createElement("div");
    badge.className = "agent-badge";
    badge.style.display = "none";
    badge.textContent = "";

    var content = document.createElement("div");
    content.className = "message-content";

    msg.appendChild(badge);
    msg.appendChild(content);

    return { container: msg, content: content, agentBadge: badge };
  }

  /**
   * Create a system/info message.
   * @param {string} text
   * @returns {HTMLElement}
   */
  function createSystemMessage(text) {
    var msg = document.createElement("div");
    msg.className = "message system";

    var content = document.createElement("div");
    content.className = "message-content";
    content.textContent = text;

    msg.appendChild(content);
    return msg;
  }

  // ── Agent Badge ─────────────────────────────────────────────────────

  /**
   * Show or update the agent badge on an assistant message.
   * @param {HTMLElement} badgeEl - The badge element
   * @param {string} display - Display name (e.g., "🔍 研究员")
   */
  function showAgentBadge(badgeEl, display) {
    badgeEl.textContent = display;
    badgeEl.style.display = "inline-block";
  }

  // ── Tool Cards ──────────────────────────────────────────────────────

  /**
   * Create a tool-start card (collapsed, waiting for output).
   * @param {string} name - Tool name
   * @returns {{card: HTMLElement, body: HTMLElement, setOutput: function}}
   */
  function createToolCard(name) {
    var card = document.createElement("div");
    card.className = "tool-card";

    var header = document.createElement("div");
    header.className = "tool-header";

    var icon = document.createElement("span");
    icon.className = "tool-icon";
    icon.textContent = "🔧";

    var nameSpan = document.createElement("span");
    nameSpan.className = "tool-name";
    nameSpan.textContent = name;

    var toggle = document.createElement("span");
    toggle.className = "tool-toggle";
    toggle.textContent = "▶";

    header.appendChild(icon);
    header.appendChild(nameSpan);
    header.appendChild(toggle);

    var body = document.createElement("div");
    body.className = "tool-body";
    body.textContent = "运行中…";

    card.appendChild(header);
    card.appendChild(body);

    // Toggle expand/collapse
    header.addEventListener("click", function () {
      if (card.classList.contains("expanded")) {
        card.classList.remove("expanded");
      } else {
        card.classList.add("expanded");
      }
    });

    var result = {
      card: card,
      body: body,
      setOutput: function (output) {
        body.textContent = output;
        // Auto-expand when output arrives
        card.classList.add("expanded");
        icon.textContent = "✅";
      },
    };

    return result;
  }

  // ── Conversation List ───────────────────────────────────────────────

  /**
   * Render the conversation list in the sidebar.
   * @param {Array} conversations - Array of {id, title, updated_at, message_count, archived, ...}
   * @param {string} activeThreadId - Currently active conversation ID
   */
  function renderConversationList(conversations, activeThreadId) {
    convoList.innerHTML = "";

    if (conversations.length === 0) {
      var empty = document.createElement("div");
      empty.className = "convo-item";
      empty.style.color = "var(--text-muted)";
      empty.style.fontSize = "12px";
      empty.textContent = "(暂无历史对话)";
      convoList.appendChild(empty);
      return;
    }

    conversations.forEach(function (convo) {
      var item = document.createElement("div");
      item.className = "convo-item";
      if (convo.id === activeThreadId) {
        item.classList.add("active");
      }
      item.dataset.threadId = convo.id;

      var title = document.createElement("div");
      title.className = "convo-title";

      // Build title with badges
      var prefix = convo.archived ? "📦 " : "";
      title.textContent = prefix + convo.title;

      if (convo.continued_in) {
        var badgeFork = document.createElement("span");
        badgeFork.className = "convo-badge forked";
        badgeFork.textContent = "→续";
        title.appendChild(badgeFork);
      }
      if (convo.continued_from) {
        var badgeFrom = document.createElement("span");
        badgeFrom.className = "convo-badge forked";
        badgeFrom.textContent = "←续前";
        title.appendChild(badgeFrom);
      }

      var meta = document.createElement("div");
      meta.className = "convo-meta";
      var date = (convo.updated_at || "").slice(0, 10);
      meta.textContent = date + " · " + convo.message_count + " 条消息";

      // Wrap title+meta in a text container for flex layout
      var textDiv = document.createElement("div");
      textDiv.className = "convo-text";
      textDiv.appendChild(title);
      textDiv.appendChild(meta);

      // Delete button — inline styles so it's always visible
      var delBtn = document.createElement("button");
      delBtn.className = "convo-delete";
      delBtn.textContent = "🗑 删除";
      delBtn.setAttribute("style",
        "flex-shrink:0;padding:4px 10px;" +
        "border:1px solid #e05555;border-radius:4px;" +
        "background:#3d1f1f;color:#e05555;" +
        "font-size:12px;cursor:pointer;white-space:nowrap;" +
        "font-weight:600;"
      );
      delBtn.addEventListener("mouseenter", function() {
        this.style.background = "#e05555";
        this.style.color = "#fff";
      });
      delBtn.addEventListener("mouseleave", function() {
        this.style.background = "#3d1f1f";
        this.style.color = "#e05555";
      });
      delBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        if (window.App && window.App.deleteConversation) {
          window.App.deleteConversation(convo.id);
        }
      });

      item.appendChild(textDiv);
      item.appendChild(delBtn);

      convoList.appendChild(item);
    });
  }

  /**
   * Update the active conversation highlight.
   * @param {string} activeThreadId
   */
  function updateActiveConversation(activeThreadId) {
    var items = convoList.querySelectorAll(".convo-item");
    items.forEach(function (item) {
      if (item.dataset.threadId === activeThreadId) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });
  }

  // ── Chat Container Utilities ────────────────────────────────────────

  /**
   * Append an element to the chat container and scroll into view.
   * @param {HTMLElement} el
   */
  function appendToChat(el) {
    hideWelcome();
    chatContainer.appendChild(el);
    scrollToBottom();
  }

  /**
   * Hide the welcome screen.
   */
  function hideWelcome() {
    var welcome = document.getElementById("welcome-screen");
    if (welcome && !welcome.classList.contains("hidden")) {
      welcome.classList.add("hidden");
    }
  }

  /**
   * Show the welcome screen (when no messages exist).
   */
  function showWelcome() {
    var welcome = document.getElementById("welcome-screen");
    if (welcome) {
      welcome.classList.remove("hidden");
    }
  }

  /**
   * Clear all messages from the chat container, restoring welcome screen.
   */
  function clearChat() {
    var children = chatContainer.querySelectorAll(".message, .tool-card");
    children.forEach(function (c) {
      return c.remove();
    });
    showWelcome();
  }

  /**
   * Scroll the chat container to the bottom.
   */
  function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  /**
   * Render markdown text into HTML using marked.js.
   * @param {string} text
   * @returns {string} HTML string
   */
  function renderMarkdown(text) {
    if (typeof marked !== "undefined") {
      marked.setOptions({ breaks: true, gfm: true });
      return marked.parse(text);
    }
    // Fallback: escape HTML and convert newlines
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\n/g, "<br>");
  }

  return {
    createUserMessage: createUserMessage,
    createAssistantMessage: createAssistantMessage,
    createSystemMessage: createSystemMessage,
    showAgentBadge: showAgentBadge,
    createToolCard: createToolCard,
    renderConversationList: renderConversationList,
    updateActiveConversation: updateActiveConversation,
    appendToChat: appendToChat,
    hideWelcome: hideWelcome,
    showWelcome: showWelcome,
    clearChat: clearChat,
    scrollToBottom: scrollToBottom,
    renderMarkdown: renderMarkdown,
  };
})();
