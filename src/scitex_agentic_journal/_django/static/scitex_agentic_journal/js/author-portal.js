/* Navigation uses shared SDK tab chrome; intake is explicit and never auto-runs. */
const tabs = [...document.querySelectorAll('[data-journal-tabs] [role="tab"]')];
for (const tab of tabs) tab.addEventListener("keydown", (event) => {
  const index = tabs.indexOf(tab);
  const next = event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index - 1 + tabs.length) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : null;
  if (next !== null) { event.preventDefault(); tabs[next].focus(); }
  if (event.key === " ") { event.preventDefault(); tab.click(); }
});
const form = document.querySelector("[data-journal-submit]");
if (form) form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const status = form.querySelector("[data-journal-submit-status]");
  const button = form.querySelector('button[type="submit"]');
  if (button.disabled) return;
  let files;
  try { files = JSON.parse(form.elements.files.value || "{}"); }
  catch { status.textContent = "Text files must be a valid JSON object."; return; }
  if (!files || Array.isArray(files) || typeof files !== "object") { status.textContent = "Text files must be a JSON object."; return; }
  const token = form.querySelector('[name="csrfmiddlewaretoken"]')?.value;
  if (!token) { status.textContent = "Reload the page before submitting."; return; }
  button.disabled = true;
  status.textContent = "Running structural intake…";
  try {
    const response = await fetch(form.action, { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json", "X-CSRFToken": token }, body: JSON.stringify({ bundle_yaml: form.elements.bundle_yaml.value, files }) });
    if (!(response.headers.get("content-type") || "").includes("application/json")) throw new Error("The server did not return an intake result. Reload and check your archive before retrying.");
    const result = await response.json();
    if (!response.ok || !result.ok) throw new Error(result.reason || "Intake could not be completed.");
    status.textContent = `Structural intake recorded: ${result.submission_id}`;
    const link = document.createElement("a");
    link.textContent = " View your submission";
    link.href = `?section=review&submission=${encodeURIComponent(result.submission_id)}`;
    status.append(link);
  } catch (error) { status.textContent = error.message || "Intake could not be completed. Check your archive before retrying."; }
  finally { button.disabled = false; }
});
