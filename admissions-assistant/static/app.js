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
      const badgeLabel = meta.source === "requirements" ? "Admission Requirements" : meta.source === "program" ? "Program Match" : "FAQ Match";
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
      const token = localStorage.getItem("auth_token");
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

  // ================= 6. AUTH & USER PROFILES =================
  async function initAuth() {
    const token = localStorage.getItem("auth_token");
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
      localStorage.removeItem("auth_token");
      currentUser = null;
      renderAuthWidget(null);
    }
  }

  async function loadFavorites() {
    const token = localStorage.getItem("auth_token");
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

    const tabsContainer = document.querySelector(".auth-tabs");
    if (tabsContainer) {
      tabsContainer.style.display = (isForgot || isReset) ? "none" : "flex";
    }

    document.getElementById("tab-btn-login").classList.toggle("active", isLogin);
    document.getElementById("tab-btn-register").classList.toggle("active", isRegister);

    document.getElementById("form-login").style.display = isLogin ? "block" : "none";
    document.getElementById("form-register").style.display = isRegister ? "block" : "none";
    document.getElementById("form-forgot").style.display = isForgot ? "block" : "none";
    document.getElementById("form-reset").style.display = isReset ? "block" : "none";

    if (isLogin) document.getElementById("auth-modal-title").textContent = "Sign In";
    else if (isRegister) document.getElementById("auth-modal-title").textContent = "Create Account";
    else if (isForgot) document.getElementById("auth-modal-title").textContent = "Forgot Password";
    else if (isReset) document.getElementById("auth-modal-title").textContent = "Reset Password";

    const errorIds = ["login-error", "reg-error", "forgot-error", "reset-error"];
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
      localStorage.setItem("auth_token", data.access_token);
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

  window.handleRegisterSubmit = async function(e) {
    e.preventDefault();
    const full_name = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    const confirm_password = document.getElementById("reg-confirm-password").value;
    const errorEl = document.getElementById("reg-error");
    errorEl.textContent = "";

    if (password !== confirm_password) {
      errorEl.textContent = "Passwords do not match. Please verify.";
      return;
    }

    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name, email, password, confirm_password })
      });
      const data = await res.json();
      if (!res.ok) {
        errorEl.textContent = data.detail || (data.detail && data.detail[0]?.msg) || "Registration failed";
        return;
      }
      localStorage.setItem("auth_token", data.access_token);
      currentUser = data.user;
      renderAuthWidget(currentUser);
      closeAuthModal();
      openProfileModal();
    } catch (err) {
      errorEl.textContent = "Network error. Please try again.";
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

    const token = localStorage.getItem("auth_token");
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
    localStorage.removeItem("auth_token");
    currentUser = null;
    userFavorites = new Set();
    renderAuthWidget(null);
    if (programsData.length > 0) renderPrograms();
  };

  window.toggleFavorite = async function(programId) {
    const token = localStorage.getItem("auth_token");
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

  // Initialize Auth on page load
  initAuth();
});
