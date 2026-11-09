// BenchLedger page helpers. No build step; plain JavaScript.

// htmx ignores error responses (4xx/5xx) and network failures, which would leave a button
// that silently does nothing. Show a message instead.
document.addEventListener("DOMContentLoaded", () => {
  const box = document.getElementById("htmx-error");
  if (!box) return;
  const show = (text) => {
    box.textContent = text; // textContent, never innerHTML: nothing here is parsed as HTML
    box.hidden = false;
  };
  document.body.addEventListener("htmx:responseError", (event) => {
    const status = event.detail.xhr.status;
    show(
      status === 404
        ? "That item no longer exists. Reload the page to see the current state."
        : `The change didn't go through (error ${status}). Reload the page and try again.`
    );
  });
  document.body.addEventListener("htmx:sendError", () => {
    show("BenchLedger isn't responding. Check that the server is running, then reload.");
  });
  document.body.addEventListener("htmx:afterRequest", (event) => {
    if (event.detail.successful) box.hidden = true;
  });
});
