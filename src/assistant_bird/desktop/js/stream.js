/**
 * SSE streaming client for POST-based chat requests.
 *
 * Standard EventSource only supports GET, so we implement SSE parsing
 * on top of fetch() with ReadableStream for POST-based streaming.
 */
var StreamClient = (function () {
  "use strict";

  /**
   * Send a POST request and stream SSE events.
   * @param {string} url
   * @param {object} body - JSON body to POST
   * @param {object} callbacks - {onToken, onAgentSwitch, onToolStart, onToolEnd, onThinking, onSystem, onDone, onError}
   * @returns {AbortController} - call .abort() to cancel
   */
  function postSSE(url, body, callbacks) {
    var controller = new AbortController();
    var buffer = "";

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP " + response.status + ": " + response.statusText);
        }
        return response.body.getReader();
      })
      .then(function (reader) {
        var decoder = new TextDecoder();

        function pump() {
          return reader.read().then(function (_a) {
            var done = _a.done;
            var value = _a.value;
            if (done) {
              // Process any remaining buffer data
              if (buffer.trim()) {
                processBuffer(buffer, callbacks);
                buffer = "";
              }
              if (callbacks.onDone) callbacks.onDone({});
              return;
            }

            buffer += decoder.decode(value, { stream: true });
            buffer = processBuffer(buffer, callbacks);
            return pump();
          });
        }

        return pump();
      })
      .catch(function (err) {
        if (err.name === "AbortError") {
          if (callbacks.onDone) callbacks.onDone({ aborted: true });
          return;
        }
        if (callbacks.onError) {
          callbacks.onError({ type: "connection", message: err.message });
        }
      });

    return controller;
  }

  /**
   * Process the SSE buffer: extract complete events, invoke callbacks.
   * Returns the remaining (incomplete) buffer.
   */
  function processBuffer(buffer, callbacks) {
    var lines = buffer.split("\n");
    var currentEvent = { type: "message", data: "" };

    // Keep the last potentially incomplete line in the buffer
    buffer = "";

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];

      // SSE: event field
      if (line.startsWith("event: ")) {
        currentEvent.type = line.slice(7).trim();
      }
      // SSE: data field
      else if (line.startsWith("data: ")) {
        currentEvent.data = line.slice(6);
      }
      // SSE: empty line = end of event
      else if (line === "" || line === "\r") {
        if (currentEvent.data) {
          dispatchEvent(currentEvent, callbacks);
        }
        currentEvent = { type: "message", data: "" };
      }
      // If we're at the last line and it's not empty, it might be incomplete
      else if (i === lines.length - 1) {
        buffer = line;
      }
    }

    return buffer;
  }

  /**
   * Parse event data and dispatch to the appropriate callback.
   */
  function dispatchEvent(event, callbacks) {
    var data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      data = event.data;
    }

    switch (event.type) {
      case "token":
        if (callbacks.onToken) callbacks.onToken(data.text || "");
        break;
      case "agent_switch":
        if (callbacks.onAgentSwitch) callbacks.onAgentSwitch(data);
        break;
      case "tool_start":
        if (callbacks.onToolStart) callbacks.onToolStart(data);
        break;
      case "tool_end":
        if (callbacks.onToolEnd) callbacks.onToolEnd(data);
        break;
      case "thinking":
        if (callbacks.onThinking) callbacks.onThinking(data);
        break;
      case "system":
        if (callbacks.onSystem) callbacks.onSystem(data);
        break;
      case "done":
        if (callbacks.onDone) callbacks.onDone(data);
        break;
      case "error":
        if (callbacks.onError) callbacks.onError(data);
        break;
    }
  }

  return { postSSE: postSSE };
})();
