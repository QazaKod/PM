function initializeAdmissionsTools({ token, session, resume, language, staff, navigate }) {
  const byId = id => document.getElementById(id);
  let live = null;
  let claimed = null;
  let currentTab = "chat";
  let refreshingDesk = false;
  let catalogRequest = 0;

  function node(tag, text) {
    const el = document.createElement(tag);
    el.textContent = text;
    return el;
  }

  async function api(path, method = "GET", body, download = false) {
    const auth = token();
    const headers = auth ? { Authorization: "Bearer " + auth } : {};
    if (body) headers["Content-Type"] = "application/json";
    const response = await fetch(path, { method, headers, body: JSON.stringify(body), cache: "no-store" });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const failure = new Error(typeof error.detail === "string" ? error.detail : "Check the required fields and try again.");
      failure.status = response.status;
      throw failure;
    }
    const result = download ? await response.blob() : await response.json();
    if (auth !== token()) throw new Error("Session changed.");
    return result;
  }

  function form(id, status, action) {
    byId(id).addEventListener("submit", async event => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button");
      const fields = Object.fromEntries(new FormData(event.currentTarget));
      button.disabled = true;
      byId(status).textContent = "";
      try { await action(fields); }
      catch (error) { byId(status).textContent = error.message; }
      finally { button.disabled = false; }
    });
  }

  async function showCareer() {
    const pid = byId("career-program").value;
    if (!pid) return;
    const data = await api("/choices/" + encodeURIComponent(pid) + "/careers?language=" + language());
    if (pid !== byId("career-program").value) return;
    const result = byId("career-result");
    result.replaceChildren(node("p", data.roles), node("p", data.statistics));
    for (const [url, label] of [[data.source, "Program source"], [data.career_center, "SDU Career Center"]]) {
      if (url) {
        const link = node("a", label);
        link.href = url;
        result.append(link, " ");
      }
    }
  }

  async function loadChoices(selected) {
    const version = ++catalogRequest;
    const programs = await api("/programs");
    if (version !== catalogRequest) return;
    const options = byId("choice-options");
    options.replaceChildren(node("legend", "Select two to four programs"));
    const select = byId("career-program");
    select.replaceChildren();
    for (const p of programs) {
      select.add(new Option(p.name, p.id));
      const label = node("label", "");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = p.id;
      label.append(checkbox, " " + p.name);
      options.append(label);
    }
    if (selected) select.value = selected;
    await showCareer();
  }

  document.addEventListener("click", event => {
    const button = event.target.closest("[data-career]");
    if (button) {
      navigate("choices");
      loadChoices(button.dataset.career).catch(error => byId("choice-status").textContent = error.message);
    }
  });
  byId("career-program").onchange = () => showCareer().catch(error => byId("choice-status").textContent = error.message);
  form("choice-profile", "choice-status", async fields => {
    const matches = await api("/choices/recommend", "POST", fields);
    byId("choice-matches").replaceChildren(...matches.map(p => node("li", p.name)));
    if (!matches.length) byId("choice-status").textContent = "Add a subject, an interest, or a specific career goal.";
  });
  form("choice-compare", "choice-status", async () => {
    const ids = [...byId("choice-options").querySelectorAll(":checked")].map(input => input.value);
    if (ids.length < 2 || ids.length > 4) throw new Error("Select two to four different programs.");
    const params = new URLSearchParams(ids.map(id => ["ids", id]));
    const programs = await api("/choices/compare?" + params);
    const table = document.createElement("table");
    for (const [key, label] of [["name","Program"],["annual_fee","Annual tuition (KZT)"],["passing_score","Recorded UNT threshold"],["years","Duration (years)"],["grants","Confirmed grants"]]) {
      const row = table.insertRow();
      row.append(node("th", label));
      programs.forEach(p => row.append(node(key === "name" ? "th" : "td", p[key] ?? "Unconfirmed")));
    }
    byId("choice-table").replaceChildren(table);
    if (programs.some(p => Object.values(p).includes(null))) byId("choice-status").textContent = "Some official comparison data is unavailable.";
  });

  function requireSession() {
    if (!session() || !token()) throw new Error("Sign in and send a chat message to start a saved conversation.");
    return session();
  }
  function renderTranscript(id, messages) {
    byId(id).replaceChildren(...messages.map(m => node("p", m.sender + " · " + m.message)));
  }
  async function incoming() {
    const sid = live;
    if (!sid || sid !== session()) return;
    let messages;
    try { messages = await api("/handoff/" + encodeURIComponent(sid)); }
    catch (error) {
      if (error.status === 410 && sid === live) live = null;
      throw error;
    }
    if (sid === live) renderTranscript("live-transcript", messages);
  }
  byId("ask-officer").onclick = async () => {
    try {
      const sid = requireSession();
      const result = await api("/handoff", "POST", { session_id: sid, callback: byId("callback-contact").value });
      live = sid;
      byId("consult-status").textContent = result.online ? "An officer has been requested." : "Officers are offline. Your callback request is saved.";
      await incoming();
    } catch (error) { byId("consult-status").textContent = error.message; }
  };
  document.querySelector(".consult-tools").addEventListener("toggle", async event => {
    if (!event.target.open || !token() || session()) return;
    try {
      const { session_id } = await api("/handoff/current");
      if (session_id && !session()) {
        resume(session_id);
        live = session_id;
        await incoming();
      }
    } catch (error) { byId("consult-status").textContent = error.message; }
  });
  form("rate-session", "consult-status", async fields => {
    await api("/feedback", "POST", { session_id: requireSession(), score: Number(fields.score), comment: fields.comment });
    byId("consult-status").textContent = "Thank you for rating this conversation.";
  });

  async function refreshDesk() {
    if (!staff() || currentTab !== "officers" || refreshingDesk || document.hidden) return;
    refreshingDesk = true;
    try {
      const [queue, stats] = await Promise.all([api("/admin/consultations"), api("/admin/feedback")]);
      const queueBox = byId("officer-queue");
      queueBox.replaceChildren();
      if (!queue.length) queueBox.textContent = "No requests waiting.";
      for (const item of queue) {
        const row = node("p", item.title + (item.callback ? " · " + item.callback : "") + " ");
        const button = node("button", item.mine ? "Open chat" : item.available ? "Join chat" : "Assigned");
        button.disabled = !item.mine && !item.available;
        button.onclick = async () => {
          try {
            const messages = await api("/admin/consultations/" + item.session_id + "/claim", "POST");
            claimed = item.session_id;
            renderTranscript("officer-transcript", messages);
            byId("officer-reply").hidden = false;
          } catch (error) { byId("desk-status").textContent = error.message; }
        };
        row.append(button);
        if (item.mine) {
          const finish = node("button", "Close consultation");
          finish.onclick = async () => {
            try {
              await api("/admin/consultations/" + item.session_id, "DELETE");
              if (claimed === item.session_id) {
                claimed = null;
                byId("officer-transcript").replaceChildren();
                byId("officer-reply").hidden = true;
              }
              await refreshDesk();
            } catch (error) { byId("desk-status").textContent = error.message; }
          };
          row.append(finish);
        }
        queueBox.append(row);
      }
      if (claimed) renderTranscript("officer-transcript", await api("/admin/consultations/" + claimed + "/claim", "POST"));
      byId("quality-summary").textContent = "Ratings: " + stats.count + " · Average: " + (stats.average?.toFixed(2) ?? "—") + " · Low ratings: " + stats.review.length;
      byId("quality-review").replaceChildren(...stats.review.map(r => {
        const details = document.createElement("details");
        details.append(node("summary", r.score + "/5 · " + (r.comment || "Review conversation")));
        r.transcript.forEach(m => details.append(node("p", m.sender + " · " + m.message)));
        return details;
      }));
    } catch (error) { byId("desk-status").textContent = error.message; }
    finally { refreshingDesk = false; }
  }
  form("officer-reply", "desk-status", async fields => {
    await api("/admin/consultations/" + claimed + "/messages", "POST", fields);
    byId("officer-reply").reset();
    await refreshDesk();
  });
  form("set-threshold", "desk-status", async fields => {
    await api("/admin/consultation-threshold", "PUT", { value: Number(fields.value) });
    byId("desk-status").textContent = "Threshold saved.";
  });
  form("export-report", "desk-status", async ({ kind, start, end }) => {
    const params = new URLSearchParams();
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    const blob = await api("/admin/reports/" + kind + ".xlsx?" + params, "GET", undefined, true);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = kind + ".xlsx";
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });
  document.addEventListener("portal-tab", event => {
    currentTab = event.detail;
    if (currentTab === "choices") loadChoices().catch(error => byId("choice-status").textContent = error.message);
    if (currentTab === "officers") refreshDesk();
    if (currentTab === "documents") api("/choices/policy").then(policy => {
      const box = byId("policy-documents");
      const source = node("a", "SDU Admissions · " + policy.checked);
      source.href = policy.source;
      box.replaceChildren(source);
      policy.stages.forEach((stage, index) => {
        const details = document.createElement("details");
        details.append(node("summary", stage));
        const list = node("ul", "");
        policy.documents.filter(doc => doc.required[index]).forEach(doc => list.append(node("li", doc.name)));
        details.append(list);
        box.append(details);
      });
    }).catch(error => byId("policy-documents").textContent = error.message);
  });
  setInterval(() => {
    if (document.hidden) return;
    refreshDesk();
    if (currentTab === "chat") incoming().catch(error => byId("consult-status").textContent = error.message);
  }, 3000);
  function reset() {
    live = claimed = null;
    for (const id of ["officer-transcript","officer-queue","quality-summary","quality-review","live-transcript","consult-status","desk-status"]) byId(id).replaceChildren();
    byId("callback-contact").value = "";
    byId("officer-reply").hidden = true;
  }
  byId("clear-chat-btn")?.addEventListener("click", reset);
  return { reset, isLive: sid => Boolean(sid && sid === live), async send(message) {
    try {
      await api("/handoff/" + requireSession() + "/messages", "POST", { message });
      await incoming();
    } catch (error) { byId("consult-status").textContent = error.message; }
  }};
}
