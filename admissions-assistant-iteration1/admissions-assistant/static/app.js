// Smart University Admissions Assistant — Iteration 1 Frontend Logic

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const navItems = document.querySelectorAll(".nav-item");
  const tabSections = document.querySelectorAll(".tab-section");
  const fabAskAi = document.getElementById("fab-ask-ai");
  const mobileMenuBtn = document.getElementById("mobile-menu-btn");
  const mobileChatShortcut = document.getElementById("mobile-chat-shortcut");
  const sidebar = document.getElementById("sidebar");
  const sidebarOverlay = document.getElementById("sidebar-overlay");

  // Chat Elements
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatMessages = document.getElementById("chat-messages");
  const clearChatBtn = document.getElementById("clear-chat-btn");
  const promptChips = document.querySelectorAll(".prompt-chip");

  // Programs & FAQ Containers
  const programsGrid = document.getElementById("programs-grid");
  const faqList = document.getElementById("faq-list");
  const faqSearch = document.getElementById("faq-search");
  const filterBtns = document.querySelectorAll(".filter-btn");

  // Documents Checklist Elements
  const docCheckboxes = document.querySelectorAll("#documents-checklist input[type='checkbox']");
  const docProgressText = document.getElementById("doc-progress-text");
  const docProgressPercent = document.getElementById("doc-progress-percent");
  const docProgressFill = document.getElementById("doc-progress-fill");


  let programsData = [];
  let faqData = [];
  let activeFilter = "all";

  // ================= 1. TAB NAVIGATION (SPA) =================
  function switchTab(tabId) {
    // Update active nav button
    navItems.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tabId);
    });

    // Update active section
    tabSections.forEach((section) => {
      section.classList.toggle("active", section.id === `section-${tabId}`);
    });

    // Toggle Floating "Ask AI" button visibility (hide when already in chat)
    if (fabAskAi) {
      if (tabId === "chat") {
        fabAskAi.classList.add("hidden");
      } else {
        fabAskAi.classList.remove("hidden");
      }
    }

    // Close mobile menu if open
    closeMobileSidebar();

    // Lazy load data for sections
    if (tabId === "programs" && programsData.length === 0) {
      loadPrograms();
    } else if (tabId === "faq" && faqData.length === 0) {
      loadFAQ();
    }

    // Focus input if switched to chat
    if (tabId === "chat") {
      setTimeout(() => chatInput.focus(), 150);
    }
  }

  navItems.forEach((item) => {
    item.addEventListener("click", () => {
      switchTab(item.dataset.tab);
    });
  });

  if (fabAskAi) {
    fabAskAi.addEventListener("click", () => {
      switchTab("chat");
    });
  }

  if (mobileChatShortcut) {
    mobileChatShortcut.addEventListener("click", () => {
      switchTab("chat");
    });
  }

  // Mobile menu toggle
  function toggleMobileSidebar() {
    sidebar.classList.toggle("open");
    sidebarOverlay.classList.toggle("active");
  }

  function closeMobileSidebar() {
    sidebar.classList.remove("open");
    sidebarOverlay.classList.remove("active");
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener("click", toggleMobileSidebar);
  }
  if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", closeMobileSidebar);
  }

  // Initialize FAB visibility
  if (fabAskAi) {
    fabAskAi.classList.add("hidden"); // Chat is default
  }

  // ================= 2. CHAT ENGINE (POST /chat) =================
  function formatTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function appendMessage(sender, text, meta = {}) {
    const isBot = sender === "bot";
    const msgEl = document.createElement("div");
    msgEl.className = `message ${isBot ? "bot-message" : "user-message"}`;
    if (meta.isFallback) {
      msgEl.classList.add("fallback-message");
    }

    let sourceBadgeHtml = "";
    if (isBot && meta.source) {
      const badgeClass = meta.source === "program" ? "source-program" : "source-faq";
      const badgeLabel = meta.source === "program" ? "Program Match" : "FAQ Match";
      sourceBadgeHtml = `<span class="msg-badge ${badgeClass}">${badgeLabel}</span>`;
    } else if (isBot && meta.isFallback) {
      sourceBadgeHtml = `<span class="msg-badge source-fallback">Admissions Staff Offer</span>`;
    }

    msgEl.innerHTML = `
      <div class="msg-avatar">${isBot ? "🤖" : "👤"}</div>
      <div class="msg-content">
        <div class="msg-bubble">
          <p>${escapeHtml(text)}</p>
        </div>
        <div class="msg-meta">
          <span class="msg-time">${formatTime()}</span>
          ${sourceBadgeHtml}
        </div>
      </div>
    `;

    chatMessages.appendChild(msgEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function showTypingIndicator() {
    const id = "typing-indicator-" + Date.now();
    const indicatorEl = document.createElement("div");
    indicatorEl.id = id;
    indicatorEl.className = "message bot-message";
    indicatorEl.innerHTML = `
      <div class="msg-avatar">🤖</div>
      <div class="msg-content">
        <div class="msg-bubble">
          <div class="typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    `;
    chatMessages.appendChild(indicatorEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
  }

  function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  async function handleUserMessage(messageText) {
    const text = messageText.trim();
    if (!text) return;

    // Display user bubble
    appendMessage("user", text);
    chatInput.value = "";

    const typingId = showTypingIndicator();

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      });

      removeTypingIndicator(typingId);

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      appendMessage("bot", data.answer, {
        source: data.source,
        isFallback: !data.confident,
        matchedId: data.matched_id
      });
    } catch (err) {
      removeTypingIndicator(typingId);
      appendMessage("bot", "Sorry, an error occurred while connecting to the assistant. Please try again.", {
        isFallback: true
      });
      console.error("Chat error:", err);
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleUserMessage(chatInput.value);
  });

  // Quick Prompt chips
  promptChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.dataset.prompt;
      if (prompt) {
        handleUserMessage(prompt);
      }
    });
  });

  // Reset chat button
  if (clearChatBtn) {
    clearChatBtn.addEventListener("click", () => {
      chatMessages.innerHTML = `
        <div class="message bot-message">
          <div class="msg-avatar">🤖</div>
          <div class="msg-content">
            <div class="msg-bubble">
              <p>Chat cleared. Feel free to ask another question!</p>
            </div>
            <div class="msg-meta">
              <span class="msg-time">${formatTime()}</span>
              <span class="msg-badge system-badge">System</span>
            </div>
          </div>
        </div>
      `;
    });
  }

  // Cross-section shortcut: "Ask in Chat"
  window.askInChat = function(queryText) {
    switchTab("chat");
    chatInput.value = queryText;
    chatInput.focus();
  };

  document.querySelectorAll(".ask-chat-shortcut").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.dataset.question || "Tell me more about required documents";
      window.askInChat(q);
    });
  });

  // ================= 3. PROGRAMS TAB (US1) =================
  async function loadPrograms() {
    try {
      const res = await fetch("/programs");
      if (!res.ok) throw new Error("Failed to load programs");
      programsData = await res.json();
      renderPrograms();
    } catch (err) {
      programsGrid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; color: #b91c1c;">
          Failed to load academic programs. Please check backend status.
        </div>
      `;
      console.error(err);
    }
  }

  function renderPrograms() {
    if (!programsData.length) return;

    const filtered = programsData.filter((p) => {
      if (activeFilter === "all") return true;
      return p.faculty === activeFilter;
    });

    programsGrid.innerHTML = filtered.map((p) => {
      const costFormatted = Number(p.approx_cost_per_year_kzt).toLocaleString("en-US");
      const degreeClass = p.degree.toLowerCase() === "master" ? "degree-master" : "degree-bachelor";
      const languages = Array.isArray(p.language) ? p.language.join(", ") : p.language;
      const untSubjects = p.unt_subjects ? p.unt_subjects.join(" + ") : "N/A";

      return `
        <div class="card program-card">
          <div class="program-top">
            <span class="degree-badge ${degreeClass}">${escapeHtml(p.degree)}</span>
            <span style="font-size: 0.8rem; font-weight: 600; color: var(--primary);">${escapeHtml(p.code)}</span>
            <span style="font-size: 0.8rem; color: var(--text-muted); margin-left: auto;">${p.duration_years} Years</span>
          </div>
          <h3 class="program-title">${escapeHtml(p.name)}</h3>
          <p class="program-desc" style="font-size: 0.85rem; color: #64748b; margin-bottom: 8px;">${escapeHtml(p.faculty)}</p>
          <p class="program-desc">${escapeHtml(p.description)}</p>
          
          <ul class="program-details-list">
            <li><span>Tuition per year:</span> <strong class="program-cost">${costFormatted} KZT</strong></li>
            <li><span>Format:</span> <strong>${escapeHtml(p.format)}</strong></li>
            <li><span>Instruction:</span> <strong>${escapeHtml(languages)}</strong></li>
            <li><span>UNT Subjects:</span> <strong>${escapeHtml(untSubjects)}</strong></li>
          </ul>

          <button class="btn btn-outline" style="width: 100%;" onclick="askInChat('Tell me about the ${escapeJs(p.name)} program')">
            💬 Ask in Chat
          </button>
        </div>
      `;
    }).join("");
  }

  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      renderPrograms();
    });
  });

  // ================= 4. FAQ TAB (US5) =================
  async function loadFAQ() {
    try {
      const res = await fetch("/faq");
      if (!res.ok) throw new Error("Failed to load FAQ");
      faqData = await res.json();
      renderFAQ(faqData);
    } catch (err) {
      faqList.innerHTML = `
        <div class="card" style="color: #b91c1c;">
          Failed to load FAQ. Please check backend status.
        </div>
      `;
      console.error(err);
    }
  }

  function renderFAQ(items) {
    if (!items.length) {
      faqList.innerHTML = `<div class="card"><p style="color: var(--text-muted);">No matching FAQ entries found.</p></div>`;
      return;
    }

    faqList.innerHTML = items.map((item, idx) => {
      const keywordsHtml = item.keywords
        ? item.keywords.map((kw) => `<span class="keyword-badge">#${escapeHtml(kw)}</span>`).join("")
        : "";

      return `
        <div class="faq-item ${idx === 0 ? "open" : ""}" id="faq-item-${item.id}">
          <div class="faq-header" onclick="toggleFaq('faq-item-${item.id}')">
            <h3>${escapeHtml(item.question)}</h3>
            <span class="faq-toggle-icon">▼</span>
          </div>
          <div class="faq-body" style="${idx === 0 ? "" : "display: none;"}">
            <p>${escapeHtml(item.answer)}</p>
            <div class="faq-keywords">${keywordsHtml}</div>
            <button class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.35rem 0.75rem;" onclick="askInChat('${escapeJs(item.question)}')">
              💬 Ask this in Chat
            </button>
          </div>
        </div>
      `;
    }).join("");
  }

  window.toggleFaq = function(faqItemId) {
    const el = document.getElementById(faqItemId);
    if (!el) return;
    const body = el.querySelector(".faq-body");
    const isOpen = el.classList.contains("open");

    if (isOpen) {
      el.classList.remove("open");
      body.style.display = "none";
    } else {
      el.classList.add("open");
      body.style.display = "block";
    }
  };

  if (faqSearch) {
    faqSearch.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase().trim();
      if (!query) {
        renderFAQ(faqData);
        return;
      }

      const filtered = faqData.filter((item) => {
        const inQuestion = item.question.toLowerCase().includes(query);
        const inAnswer = item.answer.toLowerCase().includes(query);
        const inKw = item.keywords && item.keywords.some((k) => k.toLowerCase().includes(query));
        return inQuestion || inAnswer || inKw;
      });

      renderFAQ(filtered);
    });
  }

  // ================= 5. DOCUMENTS CHECKLIST (US4) =================
  function updateDocumentsProgress() {
    const total = docCheckboxes.length;
    let checkedCount = 0;

    docCheckboxes.forEach((cb) => {
      const saved = localStorage.getItem(`doc_${cb.dataset.docId}`);
      if (saved === "true") {
        cb.checked = true;
      }
      if (cb.checked) checkedCount++;
    });

    const percent = Math.round((checkedCount / total) * 100);
    docProgressText.textContent = `${checkedCount} of ${total} documents prepared`;
    docProgressPercent.textContent = `${percent}%`;
    docProgressFill.style.width = `${percent}%`;
  }

  docCheckboxes.forEach((cb) => {
    cb.addEventListener("change", () => {
      localStorage.setItem(`doc_${cb.dataset.docId}`, cb.checked);
      updateDocumentsProgress();
    });
  });

  updateDocumentsProgress();


  // ================= UTILITIES =================
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeJs(str) {
    if (!str) return "";
    return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
  }
});
