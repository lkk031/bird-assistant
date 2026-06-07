/**
 * Assistant-Bird custom frontend script.
 *
 * Receives window messages from the Chainlit backend via
 * cl.send_window_message() and triggers page navigation.
 */
(function () {
  "use strict";

  window.addEventListener("message", function (event) {
    var data = event.data;
    if (!data) return;

    // Support both direct and Chainlit-wrapped payloads
    var payload = data.type ? data : (data.data || null);
    if (!payload) return;

    if (payload.type === "assistant_bird_new_conversation") {
      // Hard-navigate to the base URL so the page loads fresh.
      // We preserve cookies intentionally — the session cookie keeps the
      // same session_id, which on_chat_start uses to look up the new
      // thread_id that on_start_new_conversation just saved.
      // Using .replace() removes the current history entry so the back
      // button won't return to the stale page.
      window.location.replace(
        window.location.origin + window.location.pathname
      );
    }
  });
})();
