(function () {
  "use strict";

  var KEY = "pagon_konto";
  var DEFAULTS = {
    nickname: "j.kowalski",
    email: "j.kowalski@policja.gov.pl",
    accountType: "standard",
    avatarUrl: null,
    accountCreated: false,
  };

  var EYE =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
  var EYE_OFF =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"></path><circle cx="12" cy="12" r="3"></circle><line x1="3" y1="3" x2="21" y2="21"></line></svg>';

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function $(id) { return document.getElementById(id); }

  function load() {
    try {
      var raw = localStorage.getItem(KEY);
      if (!raw) return Object.assign({}, DEFAULTS);
      return Object.assign({}, DEFAULTS, JSON.parse(raw));
    } catch (e) { return Object.assign({}, DEFAULTS); }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }

  var state = load();

  function initials(name) {
    var parts = (name || "").split(/[^A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }

  // ---------- Render HOME ----------
  function renderHome() {
    $("konto-username").textContent = state.nickname || "";

    // plakietka konta
    var badge = $("konto-badge");
    if (state.accountType === "premium") {
      badge.innerHTML =
        '<span class="acct-badge premium"><svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor"><path d="M2.5 7l4.2 3.6L12 3l5.3 7.6L21.5 7 19 19H5z"></path></svg> Konto Premium</span>';
    } else {
      badge.innerHTML = '<span class="acct-badge standard">Konto Standardowe</span>';
    }

    // avatar
    var img = $("konto-avatar-img"), ini = $("konto-initials"), ph = $("konto-placeholder");
    if (state.avatarUrl) {
      img.src = state.avatarUrl; img.hidden = false; ini.hidden = true; ph.hidden = true;
    } else if (state.nickname) {
      ini.textContent = initials(state.nickname); ini.hidden = false; img.hidden = true; ph.hidden = true;
    } else {
      ph.hidden = false; img.hidden = true; ini.hidden = true;
    }

    // "Utwórz konto" tylko gdy konto nieutworzone
    $("btn-create").style.display = state.accountCreated ? "none" : "";
  }

  // ---------- Widoki ----------
  var overlays = ["ov-create", "ov-password", "ov-email", "ov-about", "ov-delete"];
  function hideAll() { overlays.forEach(function (id) { $(id).hidden = true; }); }
  function showView(view) {
    hideAll();
    if (view === "create") { $("cr-nick").value = ""; $("cr-email").value = ""; $("cr-pw").value = ""; $("cr-email-err").hidden = true; toastEl("cr-toast", null); }
    if (view === "password") { $("pw-cur").value = ""; $("pw-new").value = ""; $("pw-rep").value = ""; $("pw-strength").hidden = true; toastEl("pw-toast", null); }
    if (view === "email") { $("em-current").value = state.email; $("em-new").value = ""; $("em-err").hidden = true; toastEl("em-toast", null); }
    if (view === "delete") { $("del-input").value = ""; $("btn-do-delete").disabled = true; toastEl("del-toast", null); }
    var ov = $("ov-" + view);
    if (ov) ov.hidden = false;
  }

  // ---------- Toast ----------
  var timers = {};
  function toastEl(id, obj) {
    var el = $(id);
    if (!el) return;
    clearTimeout(timers[id]);
    if (!obj) { el.textContent = ""; el.className = el.className.replace(/\s*toast--\w+/g, ""); return; }
    el.textContent = obj.msg;
    el.className = "toast toast--" + obj.type;
    timers[id] = setTimeout(function () {
      el.textContent = ""; el.className = "toast";
    }, 3500);
  }

  // ---------- Siła hasła ----------
  function computeStrength(pw) {
    if (!pw) return { level: 0, pct: "0%", label: "", fill: "rgba(196,208,222,.12)" };
    var score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    var level = score <= 2 ? 1 : (score <= 3 ? 2 : 3);
    var map = {
      1: { pct: "33%", label: "słabe", fill: "rgba(196,208,222,.35)" },
      2: { pct: "66%", label: "średnie", fill: "rgba(196,208,222,.7)" },
      3: { pct: "100%", label: "silne", fill: "var(--color-accent)" },
    };
    return Object.assign({ level: level }, map[level]);
  }
  function renderStrength() {
    var pw = $("pw-new").value;
    var box = $("pw-strength");
    if (!pw) { box.hidden = true; return; }
    box.hidden = false;
    var s = computeStrength(pw);
    $("pw-strength-bar").style.width = s.pct;
    $("pw-strength-bar").style.background = s.fill;
    var lab = $("pw-strength-label");
    lab.textContent = s.label;
    lab.className = s.level === 3 ? "strength-label strength-label--strong" : "strength-label";
  }

  // ---------- Akcje ----------
  function doChangePassword() {
    var cur = $("pw-cur").value, nw = $("pw-new").value, rep = $("pw-rep").value;
    var s = computeStrength(nw);
    var toast;
    if (!cur) toast = { type: "error", msg: "Podaj aktualne hasło" };
    else if (nw.length < 8) toast = { type: "error", msg: "Nowe hasło musi mieć min. 8 znaków" };
    else if (s.level < 2) toast = { type: "error", msg: "Wybierz silniejsze hasło" };
    else if (nw !== rep) toast = { type: "error", msg: "Hasła nie są identyczne" };
    else toast = { type: "success", msg: "Hasło zostało zmienione" };
    if (toast.type === "success") {
      $("pw-cur").value = ""; $("pw-new").value = ""; $("pw-rep").value = ""; renderStrength();
    }
    toastEl("pw-toast", toast);
  }

  function doSaveEmail() {
    var val = $("em-new").value.trim();
    if (!val) { toastEl("em-toast", { type: "error", msg: "Podaj nowy adres e-mail" }); return; }
    if (!EMAIL_RE.test(val)) { toastEl("em-toast", { type: "error", msg: "Popraw adres e-mail" }); return; }
    state.email = val; save();
    $("em-current").value = state.email; $("em-new").value = ""; $("em-err").hidden = true;
    toastEl("em-toast", { type: "success", msg: "Adres e-mail został zmieniony" });
  }

  function doCreateAccount() {
    var nick = $("cr-nick").value.trim(), email = $("cr-email").value.trim(), pw = $("cr-pw").value;
    var toast;
    if (!nick) toast = { type: "error", msg: "Podaj nazwę użytkownika" };
    else if (!email) toast = { type: "error", msg: "Podaj adres e-mail" };
    else if (!EMAIL_RE.test(email)) toast = { type: "error", msg: "Popraw adres e-mail" };
    else if (pw.length < 8) toast = { type: "error", msg: "Hasło musi mieć min. 8 znaków" };
    else toast = { type: "success", msg: "Konto zostało utworzone" };
    if (toast.type === "success") {
      state.accountCreated = true; state.nickname = nick; state.email = email; save();
      renderHome();
      setTimeout(function () { hideAll(); }, 900);
    }
    toastEl("cr-toast", toast);
  }

  function doDelete() {
    toastEl("del-toast", { type: "error", msg: "Konto zostało zgłoszone do usunięcia (demo)." });
    $("del-input").value = ""; $("btn-do-delete").disabled = true;
  }

  // ---------- Podpięcie zdarzeń ----------
  function bind() {
    // menu -> widoki
    document.querySelectorAll(".menu-btn[data-view]").forEach(function (b) {
      b.addEventListener("click", function () { showView(b.getAttribute("data-view")); });
    });
    // powrót / anuluj
    document.querySelectorAll("[data-back]").forEach(function (b) {
      b.addEventListener("click", hideAll);
    });
    // przełączniki hasła
    document.querySelectorAll(".pw-toggle[data-pwtoggle]").forEach(function (b) {
      b.innerHTML = EYE;
      b.addEventListener("click", function () {
        var inp = $(b.getAttribute("data-pwtoggle"));
        if (!inp) return;
        var show = inp.type === "password";
        inp.type = show ? "text" : "password";
        b.innerHTML = show ? EYE_OFF : EYE;
      });
    });
    // avatar
    $("konto-avatar-pick").addEventListener("click", function () { $("konto-avatar-input").click(); });
    $("konto-avatar-input").addEventListener("change", function (e) {
      var file = e.target.files && e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function (ev) { state.avatarUrl = ev.target.result; save(); renderHome(); };
      reader.readAsDataURL(file);
    });
    // siła hasła
    $("pw-new").addEventListener("input", renderStrength);
    // e-mail walidacja live
    $("em-new").addEventListener("input", function () {
      var v = $("em-new").value;
      $("em-err").hidden = !(v.length > 0 && !EMAIL_RE.test(v));
    });
    $("cr-email").addEventListener("input", function () {
      var v = $("cr-email").value;
      $("cr-email-err").hidden = !(v.length > 0 && !EMAIL_RE.test(v));
    });
    // usuń konto — aktywacja przyciskiem po wpisaniu USUŃ
    $("del-input").addEventListener("input", function () {
      $("btn-do-delete").disabled = $("del-input").value.trim().toUpperCase() !== "USUŃ";
    });
    // akcje
    $("btn-do-create").addEventListener("click", doCreateAccount);
    $("btn-do-password").addEventListener("click", doChangePassword);
    $("btn-do-email").addEventListener("click", doSaveEmail);
    $("btn-do-delete").addEventListener("click", doDelete);
  }

  renderHome();
  bind();
})();
