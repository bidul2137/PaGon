(function () {
  "use strict";

  var FAV_KEY = "pagon_taryfikator_ulubione";

  var state = {
    kategorie: [],
    rekordy: [],
    query: "",
    kategoriaSlug: "",
    tylkoUlubione: false,
    sort: "default",
  };

  var listaEl = document.getElementById("tar-lista");
  var brakEl = document.getElementById("tar-brak");
  var liczbaEl = document.getElementById("tar-liczba");
  var searchInput = document.getElementById("tar-search-input");
  var filterRow = document.getElementById("tar-filter-row");
  var filterToggle = document.getElementById("tar-filter-toggle");
  var filterCurrent = document.getElementById("tar-filter-current");
  var filterCaret = document.getElementById("tar-filter-caret");
  var clearFilterBtn = document.getElementById("tar-clear-filter");
  var sortSelect = document.getElementById("tar-sort-select");
  var favToggleBtn = document.getElementById("tar-fav-toggle");
  var favToggleIcon = document.getElementById("tar-fav-toggle-icon");

  var modalOverlay = document.getElementById("tar-modal-overlay");
  var modalTitle = document.getElementById("tar-modal-title");
  var modalKategoria = document.getElementById("tar-modal-kategoria");
  var modalBody = document.getElementById("tar-modal-body");
  var modalCloseBtn = document.getElementById("tar-modal-close");
  var modalStarBtn = document.getElementById("tar-modal-star");
  var modalStarIcon = document.getElementById("tar-modal-star-icon");

  var STAR_FULL = window.STAR_FULL_URL;
  var STAR_EMPTY = window.STAR_EMPTY_URL;
  var API_URL = window.TARYFIKATOR_API_URL;

  var aktualnyModalId = null;

  // ---------- Ulubione (localStorage) ----------

  function wczytajUlubione() {
    try {
      var raw = localStorage.getItem(FAV_KEY);
      if (!raw) return [];
      var arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      return [];
    }
  }

  function zapiszUlubione(arr) {
    try {
      localStorage.setItem(FAV_KEY, JSON.stringify(arr));
    } catch (e) {
      /* localStorage niedostepny - ignorujemy, ulubione nie beda trwale */
    }
  }

  function jestUlubiony(id) {
    return wczytajUlubione().indexOf(id) !== -1;
  }

  function przelaczUlubiony(id) {
    var arr = wczytajUlubione();
    var idx = arr.indexOf(id);
    if (idx === -1) {
      arr.push(id);
    } else {
      arr.splice(idx, 1);
    }
    zapiszUlubione(arr);
    return arr.indexOf(id) !== -1;
  }

  // ---------- Pomocnicze ----------

  function nazwaKategorii(slug) {
    for (var i = 0; i < state.kategorie.length; i++) {
      if (state.kategorie[i].slug === slug) return state.kategorie[i].nazwa;
    }
    return slug;
  }

  function pasujeDoSzukania(rekord, q) {
    if (!q) return true;
    var haystack = [
      rekord.title || "",
      rekord.legal_qualification || rekord.legal_basis || "",
      (rekord.keywords || []).join(" "),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.indexOf(q) !== -1;
  }

  function formatKwota(v) {
    if (v === null || v === undefined) return null;
    if (typeof v === "number") return v + " zł";
    return /\d/.test(String(v)) ? String(v) + " zł" : String(v); // np. "50–100" -> "50–100 zł"
  }

  function kwotaNum(r) {
    // liczbowy klucz sortowania z mandate_base (liczba, "20–500", "od 500", formuła...)
    var v = r.mandate_base;
    if (typeof v === "number") return v;
    if (v === null || v === undefined) return -1;
    var m = String(v).match(/\d+/);
    return m ? parseInt(m[0], 10) : -1;
  }

  function filtrowaneRekordy() {
    var q = state.query.trim().toLowerCase();
    var wynik = state.rekordy.filter(function (r) {
      if (state.kategoriaSlug && r.category !== state.kategoriaSlug) return false;
      if (state.tylkoUlubione && !jestUlubiony(r.id)) return false;
      if (!pasujeDoSzukania(r, q)) return false;
      return true;
    });
    var s = state.sort;
    if (s === "mandat-desc") wynik.sort(function (a, b) { return kwotaNum(b) - kwotaNum(a); });
    else if (s === "mandat-asc") wynik.sort(function (a, b) { return kwotaNum(a) - kwotaNum(b); });
    else if (s === "punkty-desc") wynik.sort(function (a, b) { return (b.points_max || 0) - (a.points_max || 0); });
    else if (s === "nazwa") wynik.sort(function (a, b) { return (a.title || "").localeCompare(b.title || "", "pl"); });
    return wynik;
  }

  function formatujPunkty(r) {
    if (!r.points_min && !r.points_max) return "–";
    if (r.points_min === r.points_max) return r.points_min + " pkt";
    return r.points_min + "–" + r.points_max + " pkt";
  }

  // ---------- Renderowanie listy ----------

  function renderujLista() {
    var wyniki = filtrowaneRekordy();
    listaEl.innerHTML = "";

    if (liczbaEl) {
      liczbaEl.textContent = wyniki.length + (wyniki.length === 1 ? " wynik" : " wyników");
    }

    if (wyniki.length === 0) {
      brakEl.hidden = false;
      return;
    }
    brakEl.hidden = true;

    var frag = document.createDocumentFragment();

    wyniki.forEach(function (r) {
      var li = document.createElement("li");
      li.className = "tar-card";
      li.dataset.id = r.id;

      var top = document.createElement("div");
      top.className = "tar-card-top";

      var title = document.createElement("span");
      title.className = "tar-card-title";
      title.textContent = r.title;
      top.appendChild(title);

      var starBtn = document.createElement("button");
      starBtn.type = "button";
      starBtn.className = "tar-star-btn" + (jestUlubiony(r.id) ? " is-active" : "");
      starBtn.setAttribute("aria-label", "Ulubione");
      var starImg = document.createElement("img");
      starImg.src = jestUlubiony(r.id) ? STAR_FULL : STAR_EMPTY;
      starImg.alt = "";
      starBtn.appendChild(starImg);
      starBtn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var teraz = przelaczUlubiony(r.id);
        starBtn.classList.toggle("is-active", teraz);
        starImg.src = teraz ? STAR_FULL : STAR_EMPTY;
        if (state.tylkoUlubione) {
          renderujLista();
        }
        if (aktualnyModalId === r.id) {
          modalStarIcon.src = teraz ? STAR_FULL : STAR_EMPTY;
          modalStarBtn.classList.toggle("is-active", teraz);
        }
      });
      top.appendChild(starBtn);

      li.appendChild(top);

      var artLine = document.createElement("div");
      artLine.className = "tar-card-artykul";
      artLine.textContent = r.legal_qualification || r.legal_basis || "";
      if (artLine.textContent) li.appendChild(artLine);

      var staty = document.createElement("div");
      staty.className = "tar-card-staty";

      var mandatSpan = document.createElement("span");
      mandatSpan.className = "tar-staty-mandat";
      var kwotaBase = formatKwota(r.mandate_base);
      if (kwotaBase) {
        mandatSpan.textContent = "Mandat: " + kwotaBase;
      } else if (r.mandate_max_kpw) {
        mandatSpan.textContent = "Mandat: do " + r.mandate_max_kpw + " zł";
      } else {
        mandatSpan.textContent = "Mandat: wg zasad ogólnych";
      }
      staty.appendChild(mandatSpan);

      if (r.mandate_recidive) {
        var recSpan = document.createElement("span");
        recSpan.className = "tar-staty-recydywa";
        recSpan.textContent = "Recydywa: " + formatKwota(r.mandate_recidive);
        staty.appendChild(recSpan);
      }

      var pktSpan = document.createElement("span");
      pktSpan.className = "tar-staty-punkty";
      pktSpan.textContent = formatujPunkty(r);
      staty.appendChild(pktSpan);

      li.appendChild(staty);

      var wiecejBtn = document.createElement("button");
      wiecejBtn.type = "button";
      wiecejBtn.className = "tar-wiecej-btn";
      wiecejBtn.textContent = "Więcej";
      wiecejBtn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        otworzModal(r);
      });
      li.appendChild(wiecejBtn);

      frag.appendChild(li);
    });

    listaEl.appendChild(frag);
  }

  // ---------- Modal ----------

  var ICO = {
    mandat:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.2v5.6M18 9.2v5.6" stroke-linecap="round"/></svg>',
    recyd:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8a8 8 0 0 1 13.3-2.5L20 8"/><path d="M20 4v4h-4"/><path d="M20 16a8 8 0 0 1-13.3 2.5L4 16"/><path d="M4 20v-4h4"/></svg>',
    punkty:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><circle cx="12" cy="7" r="3.2"/><path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6"/><path d="M8.5 9.5 5 11l1 3M15.5 9.5 19 11l-1 3" stroke-linecap="round"/></svg>',
    kod:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><path d="M4 5.5A2 2 0 0 1 6 4h5v15H6a2 2 0 0 0-2 1.4z"/><path d="M20 5.5A2 2 0 0 0 18 4h-5v15h5a2 2 0 0 1 2 1.4z"/></svg>'
  };

  function komorkaGrid(svg, wartosc, klasa) {
    var cell = document.createElement("div");
    cell.className = "tar-grid-cell";
    var ic = document.createElement("span");
    ic.className = "tar-grid-ico";
    ic.innerHTML = svg;
    var val = document.createElement("span");
    val.className = "tar-grid-val" + (klasa ? " " + klasa : "");
    val.textContent = wartosc;
    cell.appendChild(ic);
    cell.appendChild(val);
    return cell;
  }

  function otworzModal(r) {
    aktualnyModalId = r.id;
    modalTitle.textContent = "Szczegóły wykroczenia";
    modalKategoria.textContent = "Kategoria: " + nazwaKategorii(r.category);

    var aktywny = jestUlubiony(r.id);
    modalStarBtn.classList.toggle("is-active", aktywny);
    modalStarIcon.src = aktywny ? STAR_FULL : STAR_EMPTY;

    modalBody.innerHTML = "";

    // 1) Nazwa wykroczenia + artykuł
    var nazwa = document.createElement("p");
    nazwa.className = "tar-modal-nazwa";
    nazwa.textContent = r.title;
    modalBody.appendChild(nazwa);

    var kwal = r.legal_qualification || r.legal_basis || "";
    if (kwal) {
      var artykul = document.createElement("p");
      artykul.className = "tar-modal-artykul";
      artykul.textContent = kwal;
      modalBody.appendChild(artykul);
    }

    // 2) Siatka ikon: mandat / punkty / recydywa / kod
    var baseKwota = formatKwota(r.mandate_base);
    var mandatTxt = baseKwota
      ? baseKwota
      : (r.mandate_max_kpw ? "do " + r.mandate_max_kpw + " zł" : "–");
    var recydTxt = formatKwota(r.mandate_recidive) || "–";
    var grid = document.createElement("div");
    grid.className = "tar-card-grid";
    grid.appendChild(komorkaGrid(ICO.mandat, mandatTxt, "is-gold"));
    grid.appendChild(komorkaGrid(ICO.punkty, formatujPunkty(r)));
    grid.appendChild(komorkaGrid(ICO.recyd, recydTxt, "is-dim"));
    grid.appendChild(komorkaGrid(ICO.kod, r.code || "–", "is-dim"));
    modalBody.appendChild(grid);

    // 3) Pełna treść przepisów (kwalifikacja prawna)
    if (r.legal_qualification_text) {
      var przepisyTitle = document.createElement("p");
      przepisyTitle.className = "tar-modal-przepisy-title";
      przepisyTitle.textContent = "Kwalifikacja prawna:";
      modalBody.appendChild(przepisyTitle);

      var bloki = String(r.legal_qualification_text).split(/\n\s*\n/);
      bloki.forEach(function (blok) {
        var linie = blok.split("\n");
        var art = document.createElement("div");
        art.className = "tar-modal-przepis";
        var head = document.createElement("div");
        head.className = "tar-modal-przepis-head";
        head.textContent = linie[0];
        art.appendChild(head);
        if (linie.length > 1) {
          var body = document.createElement("div");
          body.className = "tar-modal-przepis-body";
          body.textContent = linie.slice(1).join(" ");
          art.appendChild(body);
        }
        modalBody.appendChild(art);
      });
    }

    // 5) Źródła
    var zrodlaCz = [];
    if (r.source_mandate) zrodlaCz.push(r.source_mandate);
    if (r.source_points) zrodlaCz.push(r.source_points);
    if (zrodlaCz.length) {
      var zrodla = document.createElement("p");
      zrodla.className = "tar-modal-zrodla";
      zrodla.textContent = "Źródła: " + zrodlaCz.join(" · ");
      modalBody.appendChild(zrodla);
    }

    modalOverlay.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function zamknijModal() {
    modalOverlay.hidden = true;
    aktualnyModalId = null;
    document.body.style.overflow = "";
  }

  modalCloseBtn.addEventListener("click", zamknijModal);
  modalOverlay.addEventListener("click", function (ev) {
    if (ev.target === modalOverlay) zamknijModal();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !modalOverlay.hidden) zamknijModal();
  });

  modalStarBtn.addEventListener("click", function () {
    if (aktualnyModalId === null) return;
    var teraz = przelaczUlubiony(aktualnyModalId);
    modalStarBtn.classList.toggle("is-active", teraz);
    modalStarIcon.src = teraz ? STAR_FULL : STAR_EMPTY;
    renderujLista();
  });

  // ---------- Kontrolki: szukaj / filtr kategorii / ulubione ----------

  var debounceTimer = null;
  searchInput.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      state.query = searchInput.value;
      renderujLista();
    }, 120);
  });

  // ---- Zwijany panel kategorii ----
  function nazwaKat(slug) {
    if (!slug) return "Wszystkie";
    return nazwaKategorii(slug);
  }
  function ustawPanel(otwarty) {
    filterRow.hidden = !otwarty;
    filterRow.classList.toggle("is-collapsed", !otwarty);
    filterToggle.setAttribute("aria-expanded", otwarty ? "true" : "false");
    if (filterCaret) filterCaret.textContent = otwarty ? "▴" : "▾";
  }
  function odswiezFiltrUI() {
    if (filterCurrent) filterCurrent.textContent = nazwaKat(state.kategoriaSlug);
    if (clearFilterBtn) clearFilterBtn.hidden = !state.kategoriaSlug;
    filterToggle.classList.toggle("is-active", !!state.kategoriaSlug);
    var cb = document.getElementById("tar-cat-open");
    if (cb) cb.classList.toggle("is-active", !!state.kategoriaSlug);
  }

  filterToggle.addEventListener("click", function () {
    ustawPanel(filterRow.hidden);
  });
  var catOpenBtn = document.getElementById("tar-cat-open");
  if (catOpenBtn) {
    catOpenBtn.addEventListener("click", function () {
      ustawPanel(filterRow.hidden);
    });
  }

  filterRow.addEventListener("click", function (ev) {
    var chip = ev.target.closest(".tar-chip");
    if (!chip) return;
    var chips = filterRow.querySelectorAll(".tar-chip");
    chips.forEach(function (c) {
      c.classList.remove("is-active");
    });
    chip.classList.add("is-active");
    state.kategoriaSlug = chip.dataset.slug || "";
    odswiezFiltrUI();
    ustawPanel(false); // po wyborze zwiń panel, by pokazać wyniki
    renderujLista();
  });

  if (clearFilterBtn) {
    clearFilterBtn.addEventListener("click", function () {
      state.kategoriaSlug = "";
      var chips = filterRow.querySelectorAll(".tar-chip");
      chips.forEach(function (c) {
        c.classList.toggle("is-active", (c.dataset.slug || "") === "");
      });
      odswiezFiltrUI();
      renderujLista();
    });
  }

  if (sortSelect) {
    sortSelect.addEventListener("change", function () {
      state.sort = sortSelect.value || "default";
      renderujLista();
    });
  }

  favToggleBtn.addEventListener("click", function () {
    state.tylkoUlubione = !state.tylkoUlubione;
    favToggleBtn.classList.toggle("is-active", state.tylkoUlubione);
    favToggleIcon.src = state.tylkoUlubione ? STAR_FULL : STAR_EMPTY;
    renderujLista();
  });

  // ---------- Start ----------

  fetch(API_URL)
    .then(function (resp) {
      return resp.json();
    })
    .then(function (dane) {
      state.kategorie = dane.kategorie || [];
      state.rekordy = dane.rekordy || [];
      odswiezFiltrUI();
      renderujLista();
    })
    .catch(function () {
      brakEl.hidden = false;
      brakEl.textContent = "Nie udało się wczytać danych taryfikatora.";
    });
})();
// PaGon taryfikator – renderer (schemat: legal_qualification / legal_qualification_text / KPW / KW)
