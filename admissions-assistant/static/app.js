// Smart University Admissions Assistant — Iteration 1 Frontend Logic

document.addEventListener("DOMContentLoaded", () => {
  // Storage can be disabled completely (not just full). Earlier sections must
  // not abort initialization before the guide handlers have been registered.
  const storageMemory = new Map();
  const safeStorage = {
    getItem(key) {
      if (storageMemory.has(key)) return storageMemory.get(key);
      try { return window.localStorage.getItem(key); } catch (_) { return null; }
    },
    setItem(key, value) {
      storageMemory.set(key, String(value));
      try { window.localStorage.setItem(key, value); } catch (_) { /* Session only. */ }
    },
    removeItem(key) {
      storageMemory.set(key, null);
      try { window.localStorage.removeItem(key); } catch (_) { /* Session only. */ }
    }
  };

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
  const filterBtns = document.querySelectorAll("#section-programs .filter-btn");

  // Documents Checklist Elements
  const docCheckboxes = document.querySelectorAll("#documents-checklist input[type='checkbox']");
  const docProgressText = document.getElementById("doc-progress-text");
  const docProgressPercent = document.getElementById("doc-progress-percent");
  const docProgressFill = document.getElementById("doc-progress-fill");


  let requirementContext = null;
  let chatBusy = false;
  let programsData = [];
  let faqData = [];
  let activeFilter = "all";
  let currentUser = null;
  let userFavorites = new Set();

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
    } else if (tabId === "guide") {
      loadAdmissionGuide();
    } else if (tabId === "links") {
      loadOfficialLinks();
    } else if (tabId === "deadlines") {
      loadDeadlines();
    } else if (tabId === "faq-admin") {
      loadAdminFAQs();
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

  // Bot answers (and especially AI answers) come back with light markdown.
  // Escape first, THEN convert the few safe constructs — order matters,
  // otherwise this would be an HTML injection hole.
  function renderAnswer(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^\s*[-*]\s+(.*)$/gm, "• $1")
      .replace(/https:\/\/sdu\.edu\.kz\/[a-zA-Z0-9/_-]*/g, url => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`)
      .replace(/\n/g, "<br>");
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
      const badgeLabel = meta.source === "admission_guide" ? "Admission Guide · US7" : meta.source === "requirements" ? "Admission Requirements" : meta.source === "program" ? "Program Match" : "FAQ Match";
      sourceBadgeHtml = `<span class="msg-badge ${badgeClass}">${badgeLabel}</span>`;
    } else if (isBot && meta.isFallback) {
      sourceBadgeHtml = `<span class="msg-badge source-fallback">Admissions Staff Offer</span>`;
    }

    msgEl.innerHTML = `
      <div class="msg-avatar">${isBot ? "🤖" : "👤"}</div>
      <div class="msg-content">
        <div class="msg-bubble">
          <p>${renderAnswer(text)}</p>
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
    if (!text || chatBusy) return;
    chatBusy = true;
    clearChatBtn.disabled = true;

    // Display user bubble
    appendMessage("user", text);
    chatInput.value = "";

    const typingId = showTypingIndicator();

    try {
      const token = safeStorage.getItem("auth_token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const response = await fetch("/chat", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ message: text, context: requirementContext, language: document.getElementById("requirements-language").value || null })
      });

      removeTypingIndicator(typingId);

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      requirementContext = data.context || null;
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
    } finally {
      chatBusy = false;
      clearChatBtn.disabled = false;
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
      requirementContext = null;
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
    programsGrid.innerHTML = `<div class="loading-spinner">Loading academic programs...</div>`;
    try {
      const res = await fetch("/programs");
      if (!res.ok) throw new Error("Failed to load programs: HTTP " + res.status);
      programsData = await res.json();
      renderPrograms();
    } catch (err) {
      programsGrid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; color: #b91c1c; display: flex; flex-direction: column; gap: 0.75rem; align-items: flex-start;">
          <span>Failed to load academic programs. Please check backend status.</span>
          <button class="btn btn-secondary" onclick="loadPrograms()" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">🔄 Try Again</button>
        </div>
      `;
      console.error("loadPrograms error:", err);
    }
  }
  window.loadPrograms = loadPrograms;

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
      const isFav = userFavorites.has(p.id);

      return `
        <div class="card program-card">
          <div class="program-top">
            <span class="degree-badge ${degreeClass}">${escapeHtml(p.degree)}</span>
            <span style="font-size: 0.8rem; font-weight: 600; color: var(--primary);">${escapeHtml(p.code)}</span>
            <button class="program-fav-btn ${isFav ? 'active' : ''}" onclick="toggleFavorite('${escapeJs(p.id)}')" title="Bookmark program">${isFav ? '★' : '☆'}</button>
            <span style="font-size: 0.8rem; color: var(--text-muted); margin-left: auto;">${p.duration_years} Years</span>
          </div>
          <h3 class="program-title">${escapeHtml(p.name)}</h3>
          <p class="program-desc" style="font-size: 0.85rem; color: #64748b; margin-bottom: 8px;">${escapeHtml(p.faculty)}</p>
          <p class="program-desc">${escapeHtml(p.description)}</p>
          
          <ul class="program-details-list">
            <li><span>Tuition per year:</span> <strong class="program-cost">${costFormatted} KZT</strong></li>
            <li><span>Format:</span> <strong>${escapeHtml(p.format)}</strong></li>
            <li><span>Instruction:</span> <strong>${escapeHtml(languages)}</strong></li>
          </ul>

          <button class="btn btn-outline" style="width: 100%;" onclick="askInChat('Tell me about the ${escapeJs(p.name)} program')">
            💬 Ask in Chat
          </button>
          <button class="btn btn-outline" style="width: 100%;" onclick="askInChat('Admission requirements for ${escapeJs(p.name)}')">Admission requirements</button>
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
    faqList.innerHTML = `<div class="loading-spinner">Loading FAQ...</div>`;
    try {
      const res = await fetch("/faq");
      if (!res.ok) throw new Error("Failed to load FAQ: HTTP " + res.status);
      faqData = await res.json();
      renderFAQ(faqData);
    } catch (err) {
      faqList.innerHTML = `
        <div class="card" style="color: #b91c1c; display: flex; flex-direction: column; gap: 0.75rem; align-items: flex-start;">
          <span>Failed to load FAQ. Please check backend status.</span>
          <button class="btn btn-secondary" onclick="loadFAQ()" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">🔄 Try Again</button>
        </div>
      `;
      console.error("loadFAQ error:", err);
    }
  }
  window.loadFAQ = loadFAQ;

  function renderFAQ(items) {
    if (!items || !items.length) {
      faqList.innerHTML = `<div class="card"><p style="color: var(--text-muted);">No matching FAQ entries found.</p></div>`;
      return;
    }

    faqList.innerHTML = items.map((item, idx) => {
      const rawKw = item.keywords;
      const kwList = Array.isArray(rawKw)
        ? rawKw
        : (typeof rawKw === "string" ? rawKw.split(",").map(k => k.trim()) : []);

      const keywordsHtml = kwList
        .map((kw) => `<span class="keyword-badge">#${escapeHtml(kw)}</span>`)
        .join("");

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
        const inQuestion = (item.question || "").toLowerCase().includes(query);
        const inAnswer = (item.answer || "").toLowerCase().includes(query);
        const rawKw = item.keywords;
        const kwList = Array.isArray(rawKw)
          ? rawKw
          : (typeof rawKw === "string" ? rawKw.split(",") : []);
        const inKw = kwList.some((k) => k.toLowerCase().includes(query));
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
      const saved = safeStorage.getItem(`doc_${cb.dataset.docId}`);
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
      safeStorage.setItem(`doc_${cb.dataset.docId}`, cb.checked);
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
    return String(str)
      .replace(/\\/g, "\\\\")
      .replace(/'/g, "\\'")
      .replace(/"/g, '\\"')
      .replace(/\n/g, "\\n")
      .replace(/\r/g, "\\r");
  }

  window.escapeHtml = escapeHtml;
  window.escapeJs = escapeJs;

  // ================= 6. AUTH & USER PROFILES =================
  async function initAuth() {
    const token = safeStorage.getItem("auth_token");
    if (!token) {
      renderAuthWidget(null);
      return;
    }
    try {
      const res = await fetch("/auth/me", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!res.ok) {
        throw new Error("Invalid token");
      }
      currentUser = await res.json();
      renderAuthWidget(currentUser);
      await loadFavorites();
    } catch (err) {
      safeStorage.removeItem("auth_token");
      currentUser = null;
      renderAuthWidget(null);
    }
  }

  async function loadFavorites() {
    const token = safeStorage.getItem("auth_token");
    if (!token) return;
    try {
      const res = await fetch("/auth/favorites", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const favs = await res.json();
        userFavorites = new Set(favs.map((f) => f.program_id));
        if (programsData.length > 0) renderPrograms();
      }
    } catch (err) {
      console.error("Failed to load favorites", err);
    }
  }

  function renderAuthWidget(user) {
    const container = document.getElementById("auth-widget-container");
    if (!container) return;

    const faqAdminNav = document.getElementById("nav-item-faq-admin");
    if (faqAdminNav) {
      if (user && ["admin", "manager"].includes(user.role)) {
        faqAdminNav.style.display = "flex";
      } else {
        faqAdminNav.style.display = "none";
      }
    }

    if (!user) {
      container.innerHTML = `
        <div class="auth-widget">
          <button class="auth-btn-login" onclick="openAuthModal('login')">
            <i class="ph ph-sign-in"></i>
            <span>Sign In / Register</span>
          </button>
        </div>
      `;
    } else {
      const initial = (user.full_name || user.email)[0].toUpperCase();
      container.innerHTML = `
        <div class="auth-widget">
          <div class="auth-user-info">
            <div class="auth-avatar">${initial}</div>
            <div class="auth-details">
              <div class="auth-name" title="${escapeHtml(user.full_name)}">${escapeHtml(user.full_name)}</div>
              <div class="auth-role">${escapeHtml(user.role)}</div>
            </div>
          </div>
          <div class="auth-actions">
            <button class="auth-btn-small auth-btn-profile" onclick="openProfileModal()">
              <i class="ph ph-user"></i> Profile
            </button>
            <button class="auth-btn-small auth-btn-logout" onclick="handleLogout()">
              <i class="ph ph-sign-out"></i> Logout
            </button>
          </div>
        </div>
      `;
    }
  }

  window.openAuthModal = function(tab = 'login') {
    switchAuthTab(tab);
    document.getElementById("auth-modal").classList.add("active");
  };

  window.closeAuthModal = function() {
    document.getElementById("auth-modal").classList.remove("active");
  };

  window.switchAuthTab = function(tab) {
    const isLogin = tab === 'login';
    const isRegister = tab === 'register';
    const isForgot = tab === 'forgot';
    const isReset = tab === 'reset';
    const isVerifyReg = tab === 'verify_reg';

    const tabsContainer = document.querySelector(".auth-tabs");
    if (tabsContainer) {
      tabsContainer.style.display = (isForgot || isReset || isVerifyReg) ? "none" : "flex";
    }

    document.getElementById("tab-btn-login").classList.toggle("active", isLogin);
    document.getElementById("tab-btn-register").classList.toggle("active", isRegister);

    document.getElementById("form-login").style.display = isLogin ? "block" : "none";
    document.getElementById("form-register").style.display = isRegister ? "block" : "none";
    document.getElementById("form-forgot").style.display = isForgot ? "block" : "none";
    document.getElementById("form-reset").style.display = isReset ? "block" : "none";
    const formVerifyReg = document.getElementById("form-verify-reg");
    if (formVerifyReg) formVerifyReg.style.display = isVerifyReg ? "block" : "none";

    if (isLogin) document.getElementById("auth-modal-title").textContent = "Sign In";
    else if (isRegister) document.getElementById("auth-modal-title").textContent = "Create Account";
    else if (isVerifyReg) document.getElementById("auth-modal-title").textContent = "Verify Account";
    else if (isForgot) document.getElementById("auth-modal-title").textContent = "Forgot Password";
    else if (isReset) document.getElementById("auth-modal-title").textContent = "Reset Password";

    const errorIds = ["login-error", "reg-error", "forgot-error", "reset-error", "verify-reg-error"];
    errorIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = "";
    });
  };

  let pendingResetEmail = "";
  let forgotChannel = "email";

  window.setForgotChannel = function(channel) {
    forgotChannel = channel;
    const emailBtn = document.getElementById("channel-btn-email");
    const tgBtn = document.getElementById("channel-btn-telegram");
    const submitBtn = document.getElementById("forgot-submit-btn");

    if (emailBtn) emailBtn.classList.toggle("active", channel === "email");
    if (tgBtn) tgBtn.classList.toggle("active", channel === "telegram");

    if (submitBtn) {
      submitBtn.textContent = channel === "telegram" ? "Get Code via Telegram Bot" : "Send Code via Email";
    }
  };

  window.handleForgotSubmit = async function(e) {
    e.preventDefault();
    const email = document.getElementById("forgot-email").value.trim();
    const errorEl = document.getElementById("forgot-error");
    errorEl.textContent = "";

    try {
      const res = await fetch("/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, channel: forgotChannel })
      });
      const data = await res.json();
      if (!res.ok) {
        errorEl.textContent = data.detail || "Failed to process request";
        return;
      }

      pendingResetEmail = email;
      switchAuthTab('reset');

      const notice = document.getElementById("reset-notice");
      const tgContainer = document.getElementById("reset-tg-container");
      const tgLink = document.getElementById("reset-tg-link");

      if (data.channel === "telegram") {
        if (tgContainer) tgContainer.style.display = "block";
        if (tgLink && data.bot_url) tgLink.href = data.bot_url;

        let msg = `Click the button below to open our Telegram bot and receive your 6-digit code for <strong>${escapeHtml(email)}</strong>.`;
        if (data.debug_code) {
          msg += `<br><small style="color: #b4690e;"><strong>Dev Mode:</strong> Code is <strong>${data.debug_code}</strong> (logged to app.log)</small>`;
        }
        notice.innerHTML = msg;
      } else {
        if (tgContainer) tgContainer.style.display = "none";
        let msg = `A 6-digit verification code has been sent to <strong>${escapeHtml(email)}</strong>. Please check your inbox and enter it below.`;
        if (data.debug_code) {
          msg += `<br><small style="color: #b4690e;"><strong>Dev Mode:</strong> Code is <strong>${data.debug_code}</strong> (logged to app.log)</small>`;
        }
        notice.innerHTML = msg;
      }
    } catch (err) {
      errorEl.textContent = "Network error. Please try again.";
    }
  };

  window.handleResetSubmit = async function(e) {
    e.preventDefault();
    const code = document.getElementById("reset-code").value.trim();
    const new_password = document.getElementById("reset-new-password").value;
    const confirm_password = document.getElementById("reset-confirm-password").value;
    const errorEl = document.getElementById("reset-error");
    errorEl.textContent = "";

    if (new_password !== confirm_password) {
      errorEl.textContent = "Passwords do not match. Please verify.";
      return;
    }

    try {
      const res = await fetch("/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: pendingResetEmail,
          code,
          new_password,
          confirm_password
        })
      });
      const data = await res.json();
      if (!res.ok) {
        errorEl.textContent = data.detail || (data.detail && data.detail[0]?.msg) || "Failed to reset password";
        return;
      }

      switchAuthTab('login');
      document.getElementById("login-email").value = pendingResetEmail;
      const loginError = document.getElementById("login-error");
      loginError.style.color = "var(--ok, #1B7F5C)";
      loginError.textContent = "Password successfully changed! Please log in.";
      setTimeout(() => {
        loginError.style.color = "var(--alert, #b32d3a)";
        loginError.textContent = "";
      }, 6000);
    } catch (err) {
      errorEl.textContent = "Network error. Please try again.";
    }
  };

  window.handleLoginSubmit = async function(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const errorEl = document.getElementById("login-error");
    errorEl.textContent = "";

    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (!res.ok) {
        errorEl.textContent = data.detail || "Login failed";
        return;
      }
      safeStorage.setItem("auth_token", data.access_token);
      currentUser = data.user;
      renderAuthWidget(currentUser);
      closeAuthModal();
      await loadFavorites();
    } catch (err) {
      errorEl.textContent = "Network error. Please try again.";
    }
  };

  window.togglePasswordVisibility = function(inputId, btnEl) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
      input.type = "text";
      btnEl.textContent = "🙈";
    } else {
      input.type = "password";
      btnEl.textContent = "👁️";
    }
  };

  let registerChannel = "email";
  let phoneDeliveryMethod = "phone_sms";
  let pendingVerifyIdentifier = "";

  window.setRegisterChannel = function(ch) {
    registerChannel = ch;
    const emailBtn = document.getElementById("reg-channel-email");
    const phoneBtn = document.getElementById("reg-channel-phone");
    const emailGroup = document.getElementById("reg-email-group");
    const phoneGroup = document.getElementById("reg-phone-group");

    if (emailBtn) emailBtn.classList.toggle("active", ch === "email");
    if (phoneBtn) phoneBtn.classList.toggle("active", ch === "phone");

    if (emailGroup) emailGroup.style.display = ch === "email" ? "block" : "none";
    if (phoneGroup) phoneGroup.style.display = ch === "phone" ? "block" : "none";
  };

  window.setPhoneDeliveryMethod = function(method) {
    phoneDeliveryMethod = method;
    const smsBtn = document.getElementById("reg-phone-via-sms");
    const tgBtn = document.getElementById("reg-phone-via-tg");
    if (smsBtn) smsBtn.classList.toggle("active", method === "phone_sms");
    if (tgBtn) tgBtn.classList.toggle("active", method === "phone_telegram");
  };

  window.handleRegisterSubmit = async function(e) {
    e.preventDefault();
    const full_name = document.getElementById("reg-name").value.trim();
    const password = document.getElementById("reg-password").value;
    const confirm_password = document.getElementById("reg-confirm-password").value;
    const errorEl = document.getElementById("reg-error");
    errorEl.textContent = "";

    if (password !== confirm_password) {
      errorEl.textContent = "Passwords do not match. Please verify.";
      return;
    }

    const payload = {
      full_name,
      password,
      confirm_password,
      channel: registerChannel === "email" ? "email" : phoneDeliveryMethod
    };

    if (registerChannel === "email") {
      const email = document.getElementById("reg-email").value.trim();
      if (!email) {
        errorEl.textContent = "Please enter your email address.";
        return;
      }
      payload.email = email;
    } else {
      const phone = document.getElementById("reg-phone").value.trim();
      if (!phone) {
        errorEl.textContent = "Please enter your phone number.";
        return;
      }
      payload.phone = phone;
    }

    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) {
        errorEl.textContent = data.detail || (data.detail && data.detail[0]?.msg) || "Registration failed";
        return;
      }

      pendingVerifyIdentifier = data.identifier;
      switchAuthTab('verify_reg');

      const notice = document.getElementById("verify-reg-notice");
      const tgContainer = document.getElementById("verify-reg-tg-container");
      const tgLink = document.getElementById("verify-reg-tg-link");

      if (data.channel === "phone_telegram") {
        if (tgContainer) tgContainer.style.display = "block";
        if (tgLink && data.bot_url) tgLink.href = data.bot_url;
        let msg = `Click the button below to open our Telegram bot and receive your 6-digit verification code for <strong>${escapeHtml(data.identifier)}</strong>.`;
        if (data.debug_code) {
          msg += `<br><small style="color: #b4690e;"><strong>Dev Mode:</strong> Code is <strong>${data.debug_code}</strong> (logged to app.log)</small>`;
        }
        notice.innerHTML = msg;
      } else {
        if (tgContainer) tgContainer.style.display = "none";
        let destType = data.channel === "email" ? "email inbox" : "phone via SMS";
        let msg = `A 6-digit verification code has been sent to your <strong>${destType}</strong> (<strong>${escapeHtml(data.identifier)}</strong>). Please enter it below.`;
        if (data.debug_code) {
          msg += `<br><small style="color: #b4690e;"><strong>Dev Mode:</strong> Code is <strong>${data.debug_code}</strong> (logged to app.log)</small>`;
        }
        notice.innerHTML = msg;
      }
    } catch (err) {
      errorEl.textContent = "Network error. Please try again.";
    }
  };

  window.handleVerifyRegSubmit = async function(e) {
    e.preventDefault();
    const code = document.getElementById("verify-reg-code").value.trim();
    const errorEl = document.getElementById("verify-reg-error");
    errorEl.textContent = "";

    try {
      const res = await fetch("/auth/verify-registration", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          identifier: pendingVerifyIdentifier,
          code
        })
      });
      const data = await res.json();
      if (!res.ok) {
        errorEl.textContent = data.detail || (data.detail && data.detail[0]?.msg) || "Verification failed";
        return;
      }

      safeStorage.setItem("auth_token", data.access_token);
      currentUser = data.user;
      renderAuthWidget(currentUser);
      closeAuthModal();
      openProfileModal();
    } catch (err) {
      errorEl.textContent = "Network error. Please try again.";
    }
  };

  window.handleResendCode = async function() {
    const errorEl = document.getElementById("verify-reg-error");
    errorEl.textContent = "";
    try {
      const res = await fetch("/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: pendingVerifyIdentifier })
      });
      const data = await res.json();
      if (res.ok) {
        const notice = document.getElementById("verify-reg-notice");
        let msg = `A fresh verification code has been sent to <strong>${escapeHtml(pendingVerifyIdentifier)}</strong>.`;
        if (data.debug_code) {
          msg += `<br><small style="color: #b4690e;"><strong>Dev Mode:</strong> Code is <strong>${data.debug_code}</strong></small>`;
        }
        notice.innerHTML = msg;
      } else {
        errorEl.textContent = data.detail || "Failed to resend code";
      }
    } catch (err) {
      errorEl.textContent = "Network error.";
    }
  };

  window.openProfileModal = function() {
    if (!currentUser) return;
    const p = currentUser.profile || {};
    document.getElementById("prof-citizenship").value = p.citizenship || "domestic";
    document.getElementById("prof-degree").value = p.target_degree || "undergraduate";
    document.getElementById("prof-unt").value = p.unt_score || "";
    document.getElementById("prof-ielts").value = p.ielts_score || "";
    document.getElementById("prof-phone").value = p.phone || "";
    const alertCb = document.getElementById("prof-telegram-alerts");
    if (alertCb) {
      alertCb.checked = currentUser.telegram_notifications_enabled !== false;
    }
    document.getElementById("profile-status").textContent = "";
    document.getElementById("profile-modal").classList.add("active");
  };

  window.closeProfileModal = function() {
    document.getElementById("profile-modal").classList.remove("active");
  };

  window.handleProfileSubmit = async function(e) {
    e.preventDefault();
    const citizenship = document.getElementById("prof-citizenship").value;
    const target_degree = document.getElementById("prof-degree").value;
    const unt_score = document.getElementById("prof-unt").value ? parseInt(document.getElementById("prof-unt").value) : null;
    const ielts_score = document.getElementById("prof-ielts").value ? parseFloat(document.getElementById("prof-ielts").value) : null;
    const phone = document.getElementById("prof-phone").value.trim() || null;
    const statusEl = document.getElementById("profile-status");
    statusEl.textContent = "";

    if (phone) {
      const digits = phone.replace(/\D/g, "");
      if (digits.length < 10 || digits.length > 15) {
        statusEl.style.color = "var(--alert, #b32d3a)";
        statusEl.textContent = "Phone number must contain between 10 and 15 digits (e.g. +7 777 123 4567).";
        return;
      }
    }

    const token = safeStorage.getItem("auth_token");
    if (!token) return;

    try {
      const res = await fetch("/auth/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ citizenship, target_degree, unt_score, ielts_score, phone })
      });
      if (res.ok) {
        const updatedProf = await res.json();
        currentUser.profile = updatedProf;
        const alertCb = document.getElementById("prof-telegram-alerts");
        if (alertCb) {
          try {
            await fetch("/deadlines/preferences", {
              method: "PATCH",
              headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
              },
              body: JSON.stringify({ telegram_notifications_enabled: alertCb.checked })
            });
            currentUser.telegram_notifications_enabled = alertCb.checked;
          } catch (prefErr) {
            console.warn("Could not save telegram alert preference:", prefErr);
          }
        }
        statusEl.textContent = "Profile updated successfully!";
        setTimeout(() => closeProfileModal(), 900);
      } else {
        const data = await res.json();
        statusEl.style.color = "var(--alert, #b32d3a)";
        statusEl.textContent = data.detail || "Failed to update profile";
      }
    } catch (err) {
      statusEl.style.color = "var(--alert, #b32d3a)";
      statusEl.textContent = "Network error.";
    }
  };

  window.handleLogout = function() {
    safeStorage.removeItem("auth_token");
    currentUser = null;
    userFavorites = new Set();
    renderAuthWidget(null);
    const faqAdminNav = document.getElementById("nav-item-faq-admin");
    if (faqAdminNav) faqAdminNav.style.display = "none";
    const currentActiveSection = document.querySelector(".tab-section.active");
    if (currentActiveSection && currentActiveSection.id === "section-faq-admin") {
      switchTab("chat");
    }
    if (programsData.length > 0) renderPrograms();
  };

  window.toggleFavorite = async function(programId) {
    const token = safeStorage.getItem("auth_token");
    if (!token) {
      openAuthModal('login');
      return;
    }
    const isFav = userFavorites.has(programId);
    try {
      const res = await fetch(`/auth/favorites/${encodeURIComponent(programId)}`, {
        method: isFav ? "DELETE" : "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        if (isFav) {
          userFavorites.delete(programId);
        } else {
          userFavorites.add(programId);
        }
        renderPrograms();
      }
    } catch (err) {
      console.error("Error toggling favorite", err);
    }
  };

  // ================= 7. STEP-BY-STEP ADMISSION GUIDE (US7) =================
  let guideCategory = "domestic";
  let guideLevel = "undergraduate";
  let guideLang = "ru";
  let guideProgram = "";
  let guideRequest = 0;
  let guideController = null;
  let guideCatalog = null;
  const guideCopy = {
    ru: {heading: "Пошаговый гид поступления", subtitle: "Выберите программу, категорию и уровень обучения.", domestic: "Граждане РК", international: "Иностранные абитуриенты", undergraduate: "Бакалавриат", graduate: "Магистратура", program: "Программа", general: "Общий маршрут", refresh: "Обновить гид", chat: "Спросить в чате", loading: "Загрузка проверенного гида…", error: "Гид недоступен. Не удалось получить проверенные данные. Повторите запрос или обратитесь в приёмную комиссию.", empty: "Для выбранного маршрута нет проверенных шагов.", reviewed: "Проверено", due: "Перепроверка до", version: "Версия", source: "Официальный источник", done: "Выполнено", storage: "Прогресс сохраняется на этом устройстве для выбранного маршрута и версии.", noStorage: "Хранилище браузера недоступно: прогресс сохранится только до перезагрузки.", portal: "Портал приёмной комиссии"},
    kk: {heading: "Қадамдық қабылдау нұсқаулығы", subtitle: "Бағдарламаны, талапкер санатын және оқу деңгейін таңдаңыз.", domestic: "ҚР азаматтары", international: "Шетелдік талапкерлер", undergraduate: "Бакалавриат", graduate: "Магистратура", program: "Бағдарлама", general: "Жалпы жол", refresh: "Нұсқаулықты жаңарту", chat: "Чатта сұрау", loading: "Тексерілген нұсқаулық жүктелуде…", error: "Нұсқаулық қолжетімсіз. Тексерілген деректер алынбады. Қайталап көріңіз немесе қабылдау комиссиясына хабарласыңыз.", empty: "Таңдалған жол үшін тексерілген қадамдар жоқ.", reviewed: "Тексерілген", due: "Қайта тексеру мерзімі", version: "Нұсқа", source: "Ресми дереккөз", done: "Орындалды", storage: "Осы жол мен нұсқа бойынша прогресс осы құрылғыда сақталады.", noStorage: "Браузер жады қолжетімсіз: прогресс қайта жүктегенге дейін ғана сақталады.", portal: "Қабылдау комиссиясының порталы"},
    en: {heading: "Step-by-Step Admission Guide", subtitle: "Select a program, applicant category and study level.", domestic: "Domestic applicants", international: "International applicants", undergraduate: "Bachelor", graduate: "Master", program: "Program", general: "General route", refresh: "Refresh guide", chat: "Ask in chat", loading: "Loading reviewed guide…", error: "The guide is unavailable. Reviewed data could not be loaded. Retry or contact admissions.", empty: "No reviewed steps are available for this route.", reviewed: "Reviewed", due: "Review due", version: "Version", source: "Official source", done: "Completed", storage: "Progress is saved on this device for the selected route and version.", noStorage: "Browser storage is unavailable: progress lasts only until reload.", portal: "Admissions portal"}
  };
  const guideProgramSelect = document.getElementById("guide-program-select");
  const guideMemory = {};
  function localizeGuideControls() {
    const t = guideCopy[guideLang];
    for (const [id, key] of [["guide-heading", "heading"], ["guide-subtitle", "subtitle"], ["guide-program-label", "program"], ["guide-refresh", "refresh"], ["guide-open-chat", "chat"]]) {
      document.getElementById(id).textContent = t[key];
    }
    document.getElementById("section-guide").lang = guideLang;
    document.querySelectorAll(".guide-cat-btn").forEach(btn => {
      btn.textContent = t[btn.dataset.category];
      btn.setAttribute("aria-pressed", String(btn.dataset.category === guideCategory));
    });
    document.querySelectorAll(".guide-level-btn").forEach(btn => {
      btn.textContent = t[btn.dataset.level];
      btn.setAttribute("aria-pressed", String(btn.dataset.level === guideLevel));
    });
  }
  function updateGuidePrograms() {
    const t = guideCopy[guideLang];
    const degree = guideLevel === "undergraduate" ? "Bachelor" : "Master";
    const available = (guideCatalog || []).filter(p => p.degree === degree);
    if (!available.some(p => p.id === guideProgram)) guideProgram = "";
    guideProgramSelect.innerHTML = `<option value="">${escapeHtml(t.general)}</option>` + available.map(p =>
      `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`).join("");
    guideProgramSelect.value = guideProgram;
  }
  async function loadAdmissionGuide() {
    const container = document.getElementById("guide-steps-container");
    if (!container) return;
    const request = ++guideRequest;
    if (guideController) guideController.abort();
    const controller = new AbortController();
    guideController = controller;
    const timer = setTimeout(() => controller.abort(), 10000);
    localizeGuideControls();
    const t = guideCopy[guideLang];
    container.setAttribute("aria-busy", "true");
    container.innerHTML = `<div class="loading-spinner">${t.loading}</div>`;
    try {
      if (!guideCatalog) {
        const response = await fetch("/programs", {signal: controller.signal, cache: "no-store"});
        if (!response.ok) throw new Error("Program catalog unavailable");
        const catalog = await response.json();
        if (!Array.isArray(catalog)) throw new Error("Invalid program catalog");
        if (request !== guideRequest) return;
        guideCatalog = catalog;
      }
      if (request !== guideRequest) return;
      updateGuidePrograms();
      const params = new URLSearchParams({category: guideCategory, level: guideLevel, lang: guideLang});
      if (guideProgram) params.set("program_id", guideProgram);
      const res = await fetch(`/admissions/guide?${params}`, {signal: controller.signal, cache: "no-store"});
      if (!res.ok) throw new Error("Guide unavailable: HTTP " + res.status);
      const data = await res.json();
      if (request !== guideRequest) return;
      renderAdmissionGuide(data);
    } catch (err) {
      if (request !== guideRequest) return;
      container.innerHTML = `<div class="card" role="alert"><p>${t.error}</p>
        <button class="btn btn-secondary" id="guide-retry">${t.refresh}</button>
        <a href="https://admissions.sdu.edu.kz" target="_blank" rel="noopener noreferrer">${t.portal}</a></div>`;
      document.getElementById("guide-retry").addEventListener("click", loadAdmissionGuide);
    } finally {
      clearTimeout(timer);
      if (request === guideRequest) container.setAttribute("aria-busy", "false");
    }
  }
  window.loadAdmissionGuide = loadAdmissionGuide;
  function renderAdmissionGuide(data) {
    const container = document.getElementById("guide-steps-container");
    const t = guideCopy[guideLang];
    if (!Array.isArray(data.steps) || !data.steps.length) {
      container.innerHTML = `<div class="card" role="status"><p>${t.empty}</p><button id="guide-empty-retry" class="btn btn-secondary">${t.refresh}</button></div>`;
      document.getElementById("guide-empty-retry").addEventListener("click", loadAdmissionGuide);
      return;
    }
    // Key includes version and program so policy changes cannot inherit completed steps.
    const key = `admission-guide:${data.version}:${data.category}:${data.level}:${data.program_id || "general"}`;
    let saved = guideMemory[key] || [];
    let storageAvailable = true;
    try {
      const storedValue = localStorage.getItem(key);
      if (!(key in guideMemory)) {
        const stored = JSON.parse(storedValue || "[]");
        if (Array.isArray(stored)) saved = stored;
      }
      localStorage.setItem(key, JSON.stringify(saved));
    } catch (_) { storageAvailable = false; }
    const completed = new Set(saved.filter(id => data.steps.some(s => s.id === id)));
    guideMemory[key] = [...completed];
    container.innerHTML = `
      <h3>${escapeHtml(data.title)}</h3>
      <div class="guide-notice" role="note">${escapeHtml(data.notice)}</div>
      <p class="guide-review">${t.reviewed}: ${escapeHtml(data.verified_on)} · ${t.due}: ${escapeHtml(data.review_due)} · ${t.version}: ${escapeHtml(data.version)}</p>
      ${data.program_note ? `<p class="guide-program-note">${escapeHtml(data.program_note)}</p>` : ""}
      ${data.program_note_source ? `<p class="guide-review">${t.reviewed}: ${escapeHtml(data.program_note_verified_on)} · <a href="${escapeHtml(data.program_note_source)}" target="_blank" rel="noopener noreferrer">${t.source}</a></p>` : ""}
      <div class="guide-progress"><label for="guide-progress-bar" id="guide-progress-text"></label><progress id="guide-progress-bar" max="${data.steps.length}" value="0"></progress><small id="guide-storage-note">${storageAvailable ? t.storage : t.noStorage}</small></div>
      <div class="guide-steps-timeline">${data.steps.map(s => `
        <article class="guide-step-card">
          <div class="guide-step-header"><div class="guide-step-title-wrap"><div class="guide-step-num">${s.step}</div><h4 class="guide-step-title">${escapeHtml(s.title)}</h4></div></div>
          <p class="guide-step-desc">${escapeHtml(s.description)}</p>
          ${s.timeline ? `<p>${escapeHtml(s.timeline)}</p>` : ""}
          ${s.warning ? `<p class="guide-warning" ${s.deadline_status === "closed" ? 'role="note"' : ""}>${escapeHtml(s.warning)}</p>` : ""}
          <a href="${escapeHtml(s.source_url)}" target="_blank" rel="noopener noreferrer">${t.source}: ${escapeHtml(s.source_title)}</a>
          <label class="guide-step-check"><input type="checkbox" data-step-id="${escapeHtml(s.id)}" ${completed.has(s.id) ? "checked" : ""}> ${t.done}: ${escapeHtml(s.title)}</label>
        </article>`).join("")}</div>
      <a href="https://admissions.sdu.edu.kz" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">${t.portal}</a>`;
    const updateProgress = () => {
      document.getElementById("guide-progress-text").textContent = `${t.done}: ${completed.size} / ${data.steps.length}`;
      document.getElementById("guide-progress-bar").value = completed.size;
    };
    container.querySelectorAll("input[data-step-id]").forEach(input => input.addEventListener("change", () => {
      if (input.checked) completed.add(input.dataset.stepId); else completed.delete(input.dataset.stepId);
      guideMemory[key] = [...completed];
      try { localStorage.setItem(key, JSON.stringify([...completed])); }
      catch (_) { document.getElementById("guide-storage-note").textContent = t.noStorage; }
      updateProgress();
    }));
    updateProgress();
  }
  document.querySelectorAll(".guide-cat-btn").forEach(btn => btn.addEventListener("click", () => {
    guideCategory = btn.dataset.category;
    document.querySelectorAll(".guide-cat-btn").forEach(b => b.classList.toggle("active", b === btn));
    loadAdmissionGuide();
  }));
  document.querySelectorAll(".guide-level-btn").forEach(btn => btn.addEventListener("click", () => {
    guideLevel = btn.dataset.level;
    document.querySelectorAll(".guide-level-btn").forEach(b => b.classList.toggle("active", b === btn));
    loadAdmissionGuide();
  }));
  document.getElementById("guide-lang-select").addEventListener("change", e => {guideLang = e.target.value; loadAdmissionGuide();});
  guideProgramSelect.addEventListener("change", e => {guideProgram = e.target.value; loadAdmissionGuide();});
  document.getElementById("guide-refresh").addEventListener("click", loadAdmissionGuide);
  document.getElementById("guide-open-chat").addEventListener("click", () => {
    requirementContext = {category: guideCategory, study_level: guideLevel, language: guideLang, program_id: guideProgram || null};
    document.getElementById("requirements-language").value = guideLang;
    switchTab("chat");
    handleUserMessage({ru: "Пошаговый гид поступления", kk: "Қабылдау нұсқаулығы", en: "Admission guide"}[guideLang]);
  });

  // ================= 8. CALCULATORS (US18 & US19) =================
  // Subtab toggling
  const calcSubtabBtns = document.querySelectorAll(".calc-subtab-btn");
  calcSubtabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      calcSubtabBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const subtab = btn.dataset.subtab;
      document.querySelectorAll(".calc-panel").forEach((panel) => {
        panel.classList.remove("active");
        panel.style.display = "none";
      });
      const targetPanel = document.getElementById(`calc-subtab-${subtab}`);
      if (targetPanel) {
        targetPanel.classList.add("active");
        targetPanel.style.display = "block";
      }
    });
  });

  // US18: UNT Eligibility Matcher
  const untForm = document.getElementById("unt-matcher-form");
  if (untForm) {
    untForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const s1 = document.getElementById("unt-subject-1").value;
      const s2 = document.getElementById("unt-subject-2").value;
      const scoreVal = parseInt(document.getElementById("unt-score-input").value, 10);
      const loadingEl = document.getElementById("unt-matcher-loading");
      const resultsEl = document.getElementById("unt-matcher-results");

      if (loadingEl) loadingEl.style.display = "inline";
      if (resultsEl) resultsEl.style.display = "none";

      try {
        const res = await fetch("/admissions/unt-matcher", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject_1: s1,
            subject_2: s2,
            score: scoreVal
          })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Matcher failed: HTTP " + res.status);
        }
        renderUNTMatcherResults(data);
      } catch (err) {
        if (resultsEl) {
          resultsEl.innerHTML = `
            <div class="result-status-banner warning">
              <i class="ph ph-warning-circle" style="font-size: 1.2rem;"></i>
              <span>${escapeHtml(err.message)}</span>
            </div>
          `;
          resultsEl.style.display = "block";
        }
      } finally {
        if (loadingEl) loadingEl.style.display = "none";
      }
    });
  }

  function renderUNTMatcherResults(data) {
    const resultsEl = document.getElementById("unt-matcher-results");
    if (!resultsEl) return;

    let eligibleHtml = "";
    if (data.eligible_programs && data.eligible_programs.length > 0) {
      eligibleHtml = `
        <h3 style="font-size: 1.1rem; margin-top: 20px; margin-bottom: 12px; color: var(--ok);">
          ✅ Eligible Programs (${data.eligible_programs.length})
        </h3>
        <div class="calc-results-grid">
          ${data.eligible_programs.map((p) => `
            <div class="program-match-card eligible">
              <div class="match-header">
                <div>
                  <div class="match-title">${escapeHtml(p.name)}</div>
                  <div class="match-faculty">${escapeHtml(p.faculty || "")}</div>
                </div>
                <span class="metric-pill" style="background: var(--ok-lo); color: var(--ok);">Eligible</span>
              </div>
              <div class="match-metrics">
                <span class="metric-pill">Pass Score: ${p.min_score}</span>
                <span class="metric-pill" style="color: var(--ok);">Your Surplus: +${p.points_surplus || 0} pts</span>
                ${p.approx_cost_per_year_kzt ? `<span class="metric-pill">${p.approx_cost_per_year_kzt.toLocaleString()} ₸/yr</span>` : ""}
                ${p.grant_chance ? `<span class="grant-pill ${p.grant_chance}">Grant Chance: ${p.grant_chance.toUpperCase()}</span>` : ""}
              </div>
              <div style="margin-top: 8px;">
                <button class="btn btn-outline" style="font-size: 0.78rem; padding: 5px 12px;" onclick="calculateTuitionForProgram('${p.id}', ${data.score})">
                  💰 Calculate Tuition
                </button>
              </div>
            </div>
          `).join("")}
        </div>
      `;
    }

    let deficitHtml = "";
    if (data.deficit_programs && data.deficit_programs.length > 0) {
      deficitHtml = `
        <h3 style="font-size: 1.1rem; margin-top: 24px; margin-bottom: 12px; color: var(--warn);">
          ⚠️ Programs Needing Higher UNT Score (${data.deficit_programs.length})
        </h3>
        <div class="calc-results-grid">
          ${data.deficit_programs.map((p) => `
            <div class="program-match-card deficit">
              <div class="match-header">
                <div>
                  <div class="match-title">${escapeHtml(p.name)}</div>
                  <div class="match-faculty">${escapeHtml(p.faculty || "")}</div>
                </div>
                <span class="metric-pill" style="background: var(--warn-lo); color: var(--warn);">Need +${p.points_needed} pts</span>
              </div>
              <div class="match-metrics">
                <span class="metric-pill">Threshold: ${p.min_score}</span>
                <span class="metric-pill">Your Score: ${p.user_score}</span>
                ${p.approx_cost_per_year_kzt ? `<span class="metric-pill">${p.approx_cost_per_year_kzt.toLocaleString()} ₸/yr</span>` : ""}
              </div>
            </div>
          `).join("")}
        </div>
      `;
    }

    resultsEl.innerHTML = `
      <div class="result-status-banner ${data.eligible_programs.length > 0 ? "success" : "warning"}">
        <i class="ph ${data.eligible_programs.length > 0 ? "ph-check-circle" : "ph-info"}" style="font-size: 1.4rem;"></i>
        <div>
          <div><strong>${escapeHtml(data.status_message)}</strong></div>
          <div style="font-size: 0.82rem; margin-top: 2px;">Subjects: ${escapeHtml(data.subjects_normalized.join(" + "))} | Total Matched: ${data.total_matched}</div>
        </div>
      </div>
      ${eligibleHtml}
      ${deficitHtml}
    `;
    resultsEl.style.display = "block";
  }

  window.calculateTuitionForProgram = function(progId, untScore) {
    const tuitionTabBtn = document.querySelector('.calc-subtab-btn[data-subtab="tuition"]');
    if (tuitionTabBtn) tuitionTabBtn.click();
    const progSelect = document.getElementById("tuition-program-select");
    if (progSelect) progSelect.value = progId;
    const untInput = document.getElementById("tuition-unt-score");
    if (untInput && untScore) untInput.value = untScore;
    const form = document.getElementById("tuition-calc-form");
    if (form) form.dispatchEvent(new Event("submit"));
  };

  // US19: Tuition & Grant Calculator
  const tuitionForm = document.getElementById("tuition-calc-form");
  if (tuitionForm) {
    tuitionForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const progId = document.getElementById("tuition-program-select").value;
      const scoreRaw = document.getElementById("tuition-unt-score").value;
      const untScoreVal = scoreRaw !== "" ? parseInt(scoreRaw, 10) : null;
      const discountCheckboxes = document.querySelectorAll('#tuition-calc-form input[name="discount"]:checked');
      const discounts = Array.from(discountCheckboxes).map((cb) => cb.value);

      const loadingEl = document.getElementById("tuition-calc-loading");
      const resultsEl = document.getElementById("tuition-calc-results");

      if (loadingEl) loadingEl.style.display = "inline";
      if (resultsEl) resultsEl.style.display = "none";

      try {
        const res = await fetch("/admissions/tuition-calculator", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            program_id: progId,
            unt_score: untScoreVal,
            discounts: discounts
          })
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Calculation failed: HTTP " + res.status);
        }
        renderTuitionCalculatorResults(data);
      } catch (err) {
        if (resultsEl) {
          resultsEl.innerHTML = `
            <div class="result-status-banner warning">
              <i class="ph ph-warning-circle" style="font-size: 1.2rem;"></i>
              <span>${escapeHtml(err.message)}</span>
            </div>
          `;
          resultsEl.style.display = "block";
        }
      } finally {
        if (loadingEl) loadingEl.style.display = "none";
      }
    });
  }

  function renderTuitionCalculatorResults(data) {
    const resultsEl = document.getElementById("tuition-calc-results");
    if (!resultsEl) return;

    let discountsHtml = "";
    if (data.applied_discounts && data.applied_discounts.length > 0) {
      discountsHtml = `
        <div class="tuition-discounts-list">
          <h4>Applied Scholarships & Discounts:</h4>
          ${data.applied_discounts.map((d) => `
            <div class="discount-item-row">
              <span><strong>${escapeHtml(d.title)}</strong> (${d.percentage}%)</span>
              <span style="color: var(--ok); font-weight: 700;">-${d.percentage}%</span>
            </div>
          `).join("")}
          ${data.is_discount_capped ? `
            <div style="font-size: 0.78rem; color: var(--warn); margin-top: 8px;">
              ℹ️ Note: Total university scholarship discount is capped at maximum 50%.
            </div>
          ` : ""}
        </div>
      `;
    }

    const grantInfo = data.grant_probability;
    let grantBannerHtml = "";
    if (grantInfo && grantInfo.chance) {
      grantBannerHtml = `
        <div class="result-status-banner ${grantInfo.chance === "high" ? "success" : "warning"}" style="margin-top: 16px;">
          <i class="ph ${grantInfo.chance === "high" ? "ph-check-circle" : "ph-chart-line-up"}" style="font-size: 1.4rem;"></i>
          <div>
            <div><strong>Государственный грант РК: Шанс ${grantInfo.chance.toUpperCase()}</strong></div>
            <div style="font-size: 0.84rem; margin-top: 2px;">${escapeHtml(grantInfo.description)}</div>
          </div>
        </div>
      `;
    }

    resultsEl.innerHTML = `
      <div class="tuition-summary-card">
        <div class="tuition-header-row">
          <div>
            <div class="tuition-program-name">${escapeHtml(data.program_name)}</div>
            <div class="tuition-faculty-name">${escapeHtml(data.faculty || "")} &bull; ${data.degree} (${data.duration_years} Years)</div>
          </div>
          <div class="tuition-total-tag">
            <div class="tuition-total-amount">${data.discounted_annual_fee.toLocaleString()} ₸</div>
            <div class="tuition-total-label">Final Annual Tuition (${data.total_discount_percent}% off)</div>
          </div>
        </div>

        <div class="tuition-details-grid">
          <div class="tuition-box">
            <span class="tuition-box-label">Base Annual Fee</span>
            <span class="tuition-box-value">${data.base_annual_fee.toLocaleString()} ₸</span>
          </div>
          <div class="tuition-box">
            <span class="tuition-box-label">Annual Savings</span>
            <span class="tuition-box-value" style="color: var(--ok);">${data.discount_amount_kzt.toLocaleString()} ₸</span>
          </div>
          <div class="tuition-box">
            <span class="tuition-box-label">4-Year Degree Total</span>
            <span class="tuition-box-value">${data.discounted_total_fee.toLocaleString()} ₸</span>
          </div>
        </div>

        ${discountsHtml}

        <div class="payment-schedule-card">
          <div style="font-weight: 700; font-size: 0.95rem; color: var(--text);">
            📅 50/50 Semester Payment Schedule & Enrollment
          </div>
          <div class="payment-schedule-grid">
            <div class="payment-installment-box">
              <div class="installment-title">Semester 1 Fee (50%)</div>
              <div class="installment-amount">${data.payment_schedule.semester_1.toLocaleString()} ₸</div>
              <div class="installment-note">Due upon contract signing</div>
            </div>
            <div class="payment-installment-box">
              <div class="installment-title">Mandatory Student Fee</div>
              <div class="installment-amount">${data.registration_fee_kzt.toLocaleString()} ₸</div>
              <div class="installment-note">One-time first-year registration</div>
            </div>
            <div class="payment-installment-box" style="background: var(--steppe-lo); border-color: var(--steppe);">
              <div class="installment-title">First Payment Total</div>
              <div class="installment-amount" style="color: var(--steppe);">${data.payment_schedule.first_payment_total.toLocaleString()} ₸</div>
              <div class="installment-note">Initial deposit for enrollment</div>
            </div>
            <div class="payment-installment-box">
              <div class="installment-title">Semester 2 Fee (50%)</div>
              <div class="installment-amount">${data.payment_schedule.semester_2.toLocaleString()} ₸</div>
              <div class="installment-note">Due before spring semester</div>
            </div>
          </div>
        </div>

        ${grantBannerHtml}
      </div>
    `;
    resultsEl.style.display = "block";
  }

  // ================= 9. OFFICIAL LINKS (US9) =================
  async function loadOfficialLinks() {
    const grid = document.getElementById("official-links-grid");
    if (!grid) return;
    try {
      const res = await fetch("/admissions/links");
      if (!res.ok) return;
      const data = await res.json();
      if (data.links && data.links.length > 0) {
        renderOfficialLinks(data.links);
      }
    } catch (err) {
      console.error("loadOfficialLinks error:", err);
    }
  }
  window.loadOfficialLinks = loadOfficialLinks;

  function renderOfficialLinks(links) {
    const grid = document.getElementById("official-links-grid");
    if (!grid) return;
    const iconMap = {
      sdu_portal: "🏛️",
      admissions_portal: "🎓",
      testcenter: "📝",
      egov: "📑",
      sdu_spt: "🏆",
      whatsapp_admissions: "💬",
      telegram_bot: "✈️",
      dormitory: "🏢"
    };

    const dynamicCards = links.map((l) => `
      <a href="${l.url}" target="_blank" rel="noopener noreferrer" class="link-card card">
        <div class="link-icon">${iconMap[l.id] || "🔗"}</div>
        <div class="link-details">
          <h3>${escapeHtml(l.title)}</h3>
          <p>${escapeHtml(l.description || l.name_ru || "")}</p>
          <span class="link-arrow">Visit link →</span>
        </div>
      </a>
    `).join("");

    grid.innerHTML = dynamicCards + `
      <div class="link-card card" onclick="window.location.href='mailto:admission@sdu.edu.kz'">
        <div class="link-icon">✉️</div>
        <div class="link-details">
          <h3>Admissions Support Email</h3>
          <p>Contact officers directly: <code>admission@sdu.edu.kz</code></p>
          <span class="link-arrow">Send email →</span>
        </div>
      </div>

      <div class="link-card card" onclick="alert('Admissions Hotline: +7 (727) 307-95-65\\nOffice: Abylai Khan str., 1/1, Kaskelen\\nHours: Mon-Fri 09:00 - 18:00')">
        <div class="link-icon">📞</div>
        <div class="link-details">
          <h3>Admissions Hotline & Campus Office</h3>
          <p>+7 (727) 307-95-65 &bull; Mon-Fri 09:00 - 18:00</p>
          <span class="link-arrow">View details →</span>
        </div>
      </div>
    `;
  }

  // ============================================================
  // SPRINT 4: US20 TELEGRAM PUSH NOTIFICATION SETTINGS LISTENER
  // ============================================================
  const profTelegramAlerts = document.getElementById("prof-telegram-alerts");
  if (profTelegramAlerts) {
    profTelegramAlerts.addEventListener("change", async (e) => {
      const enabled = e.target.checked;
      const token = safeStorage.getItem("auth_token");
      if (!token) return;
      try {
        const res = await fetch("/deadlines/preferences", {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ telegram_notifications_enabled: enabled })
        });
        if (res.ok) {
          const data = await res.json();
          if (currentUser) {
            currentUser.telegram_notifications_enabled = enabled;
          }
          const statusEl = document.getElementById("profile-status");
          if (statusEl) {
            statusEl.style.color = "var(--ok, #1B7F5C)";
            statusEl.textContent = data.message || "Telegram notification preference saved!";
          }
        }
      } catch (err) {
        console.error("Failed to update notification preferences", err);
      }
    });
  }

  // ============================================================
  // SPRINT 4: US8 INTERACTIVE DEADLINES & ACADEMIC CALENDAR
  // ============================================================
  let deadlinesData = [];
  let calendarData = null;
  let deadlinesView = "list"; // "list" | "calendar"
  let selectedCalendarMonth = null; // null = all months

  window.setDeadlinesView = function(view) {
    deadlinesView = view;
    const btnList = document.getElementById("deadlines-view-list-btn");
    const btnCal = document.getElementById("deadlines-view-calendar-btn");
    const containerList = document.getElementById("deadlines-list-container");
    const containerCal = document.getElementById("deadlines-calendar-container");

    if (view === "list") {
      if (btnList) btnList.classList.add("active");
      if (btnCal) btnCal.classList.remove("active");
      if (containerList) containerList.style.display = "flex";
      if (containerCal) containerCal.style.display = "none";
    } else {
      if (btnList) btnList.classList.remove("active");
      if (btnCal) btnCal.classList.add("active");
      if (containerList) containerList.style.display = "none";
      if (containerCal) containerCal.style.display = "flex";
      if (!calendarData) {
        loadDeadlinesCalendar();
      }
    }
  };

  window.onDeadlinesFilterChange = function() {
    loadDeadlines();
    if (deadlinesView === "calendar") {
      loadDeadlinesCalendar();
    }
  };

  async function loadDeadlines() {
    const degreeEl = document.getElementById("deadlines-filter-degree");
    const catEl = document.getElementById("deadlines-filter-category");
    const langEl = document.getElementById("deadlines-filter-lang");

    const degree = degreeEl ? degreeEl.value : "all";
    const category = catEl ? catEl.value : "all";
    const lang = langEl ? langEl.value : "ru";

    let url = `/deadlines?lang=${encodeURIComponent(lang)}`;
    if (category && category !== "all") {
      url += `&category=${encodeURIComponent(category)}`;
    }
    if (degree && degree !== "all") {
      url += `&degree_level=${encodeURIComponent(degree)}`;
    }

    const container = document.getElementById("deadlines-list-container");
    if (container && deadlinesData.length === 0) {
      container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--muted);"><i class="ph ph-spinner ph-spin" style="font-size: 1.8rem;"></i><p>Loading deadlines...</p></div>`;
    }

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load deadlines");
      const data = await res.json();
      deadlinesData = data.deadlines || [];
      renderDeadlinesTimeline(deadlinesData);
    } catch (err) {
      console.error("loadDeadlines error:", err);
      if (container) {
        container.innerHTML = `<div class="auth-form-error" style="text-align: center; padding: 20px;">Failed to load deadlines. Please try again later.</div>`;
      }
    }
  }
  window.loadDeadlines = loadDeadlines;

  function renderDeadlinesTimeline(items) {
    const container = document.getElementById("deadlines-list-container");
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 48px; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); color: var(--muted);">
          <i class="ph ph-calendar-blank" style="font-size: 2.5rem; color: var(--muted); margin-bottom: 8px;"></i>
          <p>No deadlines found matching the selected filters.</p>
        </div>
      `;
      return;
    }

    const catLabels = {
      grant: "Grant",
      unt: "UNT Testing",
      contract: "Contract",
      dormitory: "Dormitory",
      olympiad: "SDU SPT",
      exam: "Creative Exam"
    };

    container.innerHTML = items.map((item) => {
      const statusClass = item.status === "active" ? "active" : item.status === "passed" ? "passed" : "upcoming";
      const statusText = item.status === "active" ? "Active Now" : item.status === "passed" ? "Concluded" : "Upcoming";

      let countdownHtml = "";
      if (item.status === "active") {
        countdownHtml = `<span class="countdown-pill urgent"><i class="ph ph-hourglass-high"></i> Active Phase</span>`;
      } else if (item.status === "upcoming") {
        countdownHtml = `<span class="countdown-pill"><i class="ph ph-clock"></i> ${item.days_left} days left</span>`;
      } else {
        countdownHtml = `<span class="countdown-pill"><i class="ph ph-check-circle"></i> Completed</span>`;
      }

      const adviceHtml = (item.status === "passed" && item.passed_advice)
        ? `<div class="deadline-advice"><i class="ph ph-lightbulb" style="font-size: 1.15rem; color: var(--warn, #B4690E); flex-shrink: 0;"></i><div><strong>Next steps:</strong> ${escapeHtml(item.passed_advice)}</div></div>`
        : "";

      const degreeLabel = item.degree_level === "undergraduate" ? "Bachelor" : item.degree_level === "graduate" ? "Master / PhD" : "All Programs";
      const catLabel = catLabels[item.category] || item.category;

      return `
        <div class="deadline-card status-${statusClass}" data-id="${escapeHtml(item.id)}">
          <div class="deadline-card-header">
            <div class="deadline-title-group">
              <div class="deadline-card-title">${escapeHtml(item.title)}</div>
              <div class="deadline-stage-name"><i class="ph ph-caret-right"></i> ${escapeHtml(item.stage_name)}</div>
            </div>
            <div class="deadline-badge-group">
              <span class="deadline-status-pill ${statusClass}">${statusText}</span>
              ${countdownHtml}
            </div>
          </div>
          <div class="deadline-dates-row">
            <div><i class="ph ph-calendar"></i> <strong>Period:</strong> <span class="deadline-date-badge">${escapeHtml(item.date_start)} – ${escapeHtml(item.date_end)}</span></div>
            <div><span class="deadline-cat-tag"><i class="ph ph-tag"></i> ${escapeHtml(catLabel)}</span></div>
            <div><span class="deadline-cat-tag"><i class="ph ph-graduation-cap"></i> ${escapeHtml(degreeLabel)}</span></div>
          </div>
          <div class="deadline-desc">${escapeHtml(item.description)}</div>
          ${adviceHtml}
          <div class="deadline-footer">
            <a href="${escapeHtml(item.action_url)}" target="_blank" rel="noopener noreferrer" class="deadline-action-btn">
              <span>Official Portal / Apply</span>
              <i class="ph ph-arrow-square-out"></i>
            </a>
          </div>
        </div>
      `;
    }).join("");
  }
  window.renderDeadlinesTimeline = renderDeadlinesTimeline;

  async function loadDeadlinesCalendar() {
    const langEl = document.getElementById("deadlines-filter-lang");
    const lang = langEl ? langEl.value : "ru";
    const gridWrap = document.getElementById("deadlines-calendar-grid-wrap");

    if (gridWrap && !calendarData) {
      gridWrap.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 40px; color: var(--muted);"><i class="ph ph-spinner ph-spin" style="font-size: 1.8rem;"></i><p>Loading academic calendar...</p></div>`;
    }

    try {
      const res = await fetch(`/deadlines/calendar?year=2026&lang=${encodeURIComponent(lang)}`);
      if (!res.ok) throw new Error("Failed to load calendar");
      calendarData = await res.json();
      renderDeadlinesCalendar();
    } catch (err) {
      console.error("loadDeadlinesCalendar error:", err);
      if (gridWrap) {
        gridWrap.innerHTML = `<div class="auth-form-error" style="grid-column: 1 / -1; text-align: center; padding: 20px;">Failed to load calendar events.</div>`;
      }
    }
  }
  window.loadDeadlinesCalendar = loadDeadlinesCalendar;

  function renderDeadlinesCalendar() {
    if (!calendarData || !calendarData.months) return;

    const navContainer = document.getElementById("deadlines-month-selector");
    const gridWrap = document.getElementById("deadlines-calendar-grid-wrap");
    const langEl = document.getElementById("deadlines-filter-lang");
    const lang = langEl ? langEl.value : "ru";

    const activeMonths = calendarData.months.filter(m => (m.events && m.events.length > 0) || (m.month >= 1 && m.month <= 8));

    if (navContainer) {
      const allBtnActive = selectedCalendarMonth === null ? "active" : "";
      let navHtml = `
        <button type="button" class="month-nav-btn ${allBtnActive}" onclick="selectCalendarMonth(null)">
          All Intake Months
        </button>
      `;
      activeMonths.forEach((m) => {
        const isActive = selectedCalendarMonth === m.month ? "active" : "";
        navHtml += `
          <button type="button" class="month-nav-btn ${isActive}" onclick="selectCalendarMonth(${m.month})">
            ${escapeHtml(m.month_name)} 2026
          </button>
        `;
      });
      navContainer.innerHTML = navHtml;
    }

    if (!gridWrap) return;

    const monthsToDisplay = selectedCalendarMonth === null
      ? activeMonths
      : activeMonths.filter(m => m.month === selectedCalendarMonth);

    const weekdaysByLang = {
      ru: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
      kk: ["Дүй", "Сей", "Сәр", "Бей", "Жұм", "Сен", "Жек"],
      en: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    };
    const weekdays = weekdaysByLang[lang] || weekdaysByLang.en;

    gridWrap.innerHTML = monthsToDisplay.map((m) => {
      const firstDayOffset = (new Date(m.year, m.month - 1, 1).getDay() + 6) % 7;
      const numDays = new Date(m.year, m.month, 0).getDate();

      let daysHtml = "";
      for (let s = 0; s < firstDayOffset; s++) {
        daysHtml += `<div class="calendar-day-cell empty"></div>`;
      }

      for (let d = 1; d <= numDays; d++) {
        const dayEvents = (m.days && (m.days[d] || m.days[String(d)])) || [];
        const hasEvents = dayEvents.length > 0;
        const hasEventsClass = hasEvents ? "has-events" : "";

        let dotsHtml = "";
        if (hasEvents) {
          dotsHtml = `
            <div class="day-event-dots">
              ${dayEvents.slice(0, 4).map(e => `<span class="event-dot event-tag-${e.color || 'blue'}" title="${escapeHtml(e.title)}"></span>`).join("")}
            </div>
          `;
        }

        const clickAttr = hasEvents ? `onclick="showCalendarDayEvents(${m.year}, ${m.month}, ${d})"` : "";
        daysHtml += `
          <div class="calendar-day-cell ${hasEventsClass}" ${clickAttr} title="${hasEvents ? `${dayEvents.length} event(s)` : ''}">
            <span class="day-num">${d}</span>
            ${dotsHtml}
          </div>
        `;
      }

      return `
        <div class="calendar-month-card">
          <div class="calendar-month-title">
            <span>${escapeHtml(m.month_name)} ${m.year}</span>
            <span class="event-count">${m.events ? m.events.length : 0} events</span>
          </div>
          <div class="calendar-weekdays">
            ${weekdays.map(w => `<span>${w}</span>`).join("")}
          </div>
          <div class="calendar-grid">
            ${daysHtml}
          </div>
        </div>
      `;
    }).join("");
  }
  window.renderDeadlinesCalendar = renderDeadlinesCalendar;

  window.selectCalendarMonth = function(monthNum) {
    selectedCalendarMonth = monthNum;
    renderDeadlinesCalendar();
  };

  window.showCalendarDayEvents = function(year, month, day) {
    const cardWrap = document.getElementById("deadlines-event-card-wrap");
    if (!cardWrap || !calendarData) return;

    const m = calendarData.months.find(x => x.year === year && x.month === month);
    if (!m) return;

    const dayEvents = (m.days && (m.days[day] || m.days[String(day)])) || [];
    if (dayEvents.length === 0) return;

    const eventsHtml = dayEvents.map((ev) => {
      const full = deadlinesData.find(d => d.id === ev.id) || {};
      const stageName = full.stage_name || ev.title;
      const desc = full.description || "";
      const dates = full.date_start ? `${full.date_start} – ${full.date_end}` : "";

      return `
        <div style="border-top: 1px solid var(--line); padding-top: 10px; margin-top: 8px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div style="font-weight: 700; color: var(--text); font-size: 1rem;">
              <span class="event-dot event-tag-${ev.color || 'blue'}" style="margin-right: 6px;"></span>
              ${escapeHtml(ev.title)}
            </div>
            <span class="deadline-status-pill ${ev.status || 'upcoming'}">${escapeHtml(ev.status || 'upcoming')}</span>
          </div>
          <div style="font-size: 0.88rem; font-weight: 600; color: var(--steppe); margin: 4px 0;">
            ${escapeHtml(stageName)}
          </div>
          ${dates ? `<div style="font-size: 0.84rem; color: var(--muted); margin-bottom: 4px;"><i class="ph ph-calendar"></i> ${escapeHtml(dates)}</div>` : ''}
          ${desc ? `<div style="font-size: 0.9rem; line-height: 1.5; color: var(--text); margin-bottom: 8px;">${escapeHtml(desc)}</div>` : ''}
          <div style="display: flex; justify-content: flex-end;">
            <a href="${escapeHtml(ev.action_url || '#')}" target="_blank" rel="noopener noreferrer" class="deadline-action-btn">
              <span>View Portal / Guidelines</span>
              <i class="ph ph-arrow-square-out"></i>
            </a>
          </div>
        </div>
      `;
    }).join("");

    cardWrap.style.display = "block";
    cardWrap.innerHTML = `
      <div class="calendar-event-detail-card">
        <button class="calendar-event-detail-close" onclick="closeCalendarEventDetails()">&times;</button>
        <div style="font-size: 1.05rem; font-weight: 700; color: var(--text);">
          <i class="ph ph-calendar-check" style="color: var(--steppe);"></i> Events on ${day} ${escapeHtml(m.month_name)} ${year}
        </div>
        ${eventsHtml}
      </div>
    `;

    cardWrap.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  window.closeCalendarEventDetails = function() {
    const cardWrap = document.getElementById("deadlines-event-card-wrap");
    if (cardWrap) cardWrap.style.display = "none";
  };

  // ============================================================
  // SPRINT 4: US13 MANAGE FAQ DATABASE (STAFF ADMIN)
  // ============================================================
  let adminFaqsData = [];
  let faqSearchTimer = null;

  window.debounceAdminFaqSearch = function() {
    clearTimeout(faqSearchTimer);
    faqSearchTimer = setTimeout(() => {
      loadAdminFAQs();
    }, 250);
  };

  async function loadAdminFAQs() {
    const token = safeStorage.getItem("auth_token");
    if (!token) return;

    const searchInput = document.getElementById("faq-admin-search");
    const catSelect = document.getElementById("faq-admin-cat-filter");
    const search = searchInput ? searchInput.value.trim() : "";
    const category = catSelect ? catSelect.value : "all";

    const params = [];
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (category && category !== "all") params.push(`category=${encodeURIComponent(category)}`);
    const queryStr = params.length > 0 ? `?${params.join("&")}` : "";

    try {
      const res = await fetch(`/admin/faqs${queryStr}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.status === 401 || res.status === 403) {
        console.warn("Unauthorized to access admin FAQ endpoints.");
        return;
      }
      if (!res.ok) throw new Error("Failed to load FAQs");
      adminFaqsData = await res.json();
      renderAdminFAQs(adminFaqsData);
    } catch (err) {
      console.error("loadAdminFAQs error:", err);
    }
  }
  window.loadAdminFAQs = loadAdminFAQs;

  function renderAdminFAQs(faqs) {
    const tbody = document.getElementById("faq-admin-tbody");
    const countEl = document.getElementById("faq-admin-count");
    const emptyEl = document.getElementById("faq-admin-empty");
    const tableEl = document.getElementById("faq-admin-table");

    if (countEl) countEl.textContent = `${faqs.length} ${faqs.length === 1 ? 'entry' : 'entries'}`;

    if (!tbody) return;

    if (!faqs || faqs.length === 0) {
      tbody.innerHTML = "";
      if (emptyEl) emptyEl.style.display = "block";
      if (tableEl) tableEl.style.display = "none";
      return;
    }

    if (emptyEl) emptyEl.style.display = "none";
    if (tableEl) tableEl.style.display = "table";

    tbody.innerHTML = faqs.map((faq) => {
      const keywords = (faq.keywords || []).map(k => `<span class="keyword-tag">${escapeHtml(k)}</span>`).join("");
      const answerSnippet = faq.answer.length > 130 ? escapeHtml(faq.answer.slice(0, 130)) + "…" : escapeHtml(faq.answer);
      const catClass = `cat-${faq.category || 'general'}`;

      return `
        <tr data-faq-id="${escapeHtml(faq.id)}">
          <td>
            <span class="faq-cat-badge ${catClass}">${escapeHtml(faq.category || 'general')}</span>
          </td>
          <td>
            <strong>${escapeHtml(faq.question)}</strong>
          </td>
          <td>
            <div style="color: var(--muted); line-height: 1.45;">${answerSnippet}</div>
          </td>
          <td>
            <div class="faq-keywords-wrap">${keywords || '<span style="color: var(--muted); font-size: 0.75rem;">—</span>'}</div>
          </td>
          <td>
            <div class="faq-actions">
              <button type="button" class="btn-edit" onclick="openFaqModal('${escapeHtml(faq.id)}')">
                <i class="ph ph-pencil-simple"></i> Edit
              </button>
              <button type="button" class="btn-delete" onclick="deleteFaq('${escapeHtml(faq.id)}')">
                <i class="ph ph-trash"></i> Delete
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join("");
  }
  window.renderAdminFAQs = renderAdminFAQs;

  window.openFaqModal = function(faqId) {
    const modal = document.getElementById("faq-edit-modal");
    const titleEl = document.getElementById("faq-modal-title");
    const idInput = document.getElementById("faq-edit-id");
    const qInput = document.getElementById("faq-edit-question");
    const aInput = document.getElementById("faq-edit-answer");
    const catSelect = document.getElementById("faq-edit-category");
    const kwInput = document.getElementById("faq-edit-keywords");
    const statusEl = document.getElementById("faq-edit-status");

    if (statusEl) statusEl.textContent = "";

    if (faqId) {
      const faq = adminFaqsData.find(f => f.id === faqId);
      if (faq) {
        if (titleEl) titleEl.textContent = "Edit FAQ Entry";
        if (idInput) idInput.value = faq.id;
        if (qInput) qInput.value = faq.question;
        if (aInput) aInput.value = faq.answer;
        if (catSelect) catSelect.value = faq.category || "general";
        if (kwInput) kwInput.value = (faq.keywords || []).join(", ");
      }
    } else {
      if (titleEl) titleEl.textContent = "Add New FAQ Entry";
      if (idInput) idInput.value = "";
      if (qInput) qInput.value = "";
      if (aInput) aInput.value = "";
      if (catSelect) catSelect.value = "general";
      if (kwInput) kwInput.value = "";
    }

    if (modal) modal.classList.add("active");
  };

  window.closeFaqModal = function() {
    const modal = document.getElementById("faq-edit-modal");
    if (modal) modal.classList.remove("active");
  };

  window.handleFaqSubmit = async function(e) {
    e.preventDefault();
    const token = safeStorage.getItem("auth_token");
    if (!token) return;

    const idInput = document.getElementById("faq-edit-id");
    const qInput = document.getElementById("faq-edit-question");
    const aInput = document.getElementById("faq-edit-answer");
    const catSelect = document.getElementById("faq-edit-category");
    const kwInput = document.getElementById("faq-edit-keywords");
    const statusEl = document.getElementById("faq-edit-status");

    const faqId = idInput ? idInput.value.trim() : "";
    const question = qInput ? qInput.value.trim() : "";
    const answer = aInput ? aInput.value.trim() : "";
    const category = catSelect ? catSelect.value : "general";
    const keywordsStr = kwInput ? kwInput.value.trim() : "";
    const keywords = keywordsStr ? keywordsStr.split(",").map(k => k.trim()).filter(Boolean) : [];

    if (!question || question.length < 3) {
      if (statusEl) statusEl.textContent = "Question must be at least 3 characters.";
      return;
    }
    if (!answer || answer.length < 3) {
      if (statusEl) statusEl.textContent = "Answer must be at least 3 characters.";
      return;
    }

    const payload = { question, answer, category, keywords };
    const isEdit = Boolean(faqId);
    const url = isEdit ? `/admin/faqs/${encodeURIComponent(faqId)}` : "/admin/faqs";
    const method = isEdit ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        closeFaqModal();
        await loadAdminFAQs();
      } else {
        const data = await res.json();
        if (statusEl) {
          statusEl.textContent = data.detail || "Failed to save FAQ entry";
        }
      }
    } catch (err) {
      console.error("handleFaqSubmit error:", err);
      if (statusEl) statusEl.textContent = "Network error. Please try again.";
    }
  };

  window.deleteFaq = async function(faqId) {
    if (!confirm("Are you sure you want to delete this FAQ entry? It will be immediately removed from the AI assistant knowledge base.")) {
      return;
    }
    const token = safeStorage.getItem("auth_token");
    if (!token) return;

    try {
      const res = await fetch(`/admin/faqs/${encodeURIComponent(faqId)}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        await loadAdminFAQs();
      } else {
        const data = await res.json();
        alert(data.detail || "Failed to delete FAQ entry");
      }
    } catch (err) {
      console.error("deleteFaq error:", err);
      alert("Network error while deleting FAQ entry.");
    }
  };

  // Initialize Auth on page load
  initAuth();
});

