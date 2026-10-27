/* miles-bridge.js — branche le cockpit Miles Companion aux VRAIES routes MILES.
   Meme origine via serve.py (proxy local 8787 -> 8080). Session demandee une
   fois au premier usage, gardee en sessionStorage (vie de l'onglet). Aucun
   secret ecrit sur disque, aucun affichage de cle. */
(function () {
  "use strict";
  var SK = "miles_session", CK = "miles_csrf";

  function api(method, path, body) {
    var h = { "Content-Type": "application/json" };
    var s = sessionStorage.getItem(SK);
    if (s) { h["X-MILES-Session"] = s; h["X-MILES-CSRF"] = sessionStorage.getItem(CK) || ""; }
    return fetch(path, { method: method, headers: h, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) {
        return r.text().then(function (t) {
          var j = null; try { j = t ? JSON.parse(t) : null; } catch (e) {}
          return { status: r.status, json: j };
        });
      });
  }

  function toast(msg, ok) {
    if (!document.body) { setTimeout(function () { toast(msg, ok); }, 400); return; }
    var d = document.createElement("div");
    d.setAttribute("role", "status");
    d.style.cssText = "position:fixed;right:16px;bottom:16px;z-index:99999;max-width:440px;" +
      "background:" + (ok ? "#0f2a1f" : "#2a1215") + ";color:" + (ok ? "#34d399" : "#f87171") +
      ";border:1px solid currentColor;border-radius:8px;padding:12px 16px;font:14px/1.45 system-ui,sans-serif;" +
      "white-space:pre-wrap;box-shadow:0 8px 24px rgba(0,0,0,.45)";
    d.textContent = msg;
    document.body.appendChild(d);
    setTimeout(function () { d.remove(); }, 7000);
  }

  function ensureSession() {
    if (sessionStorage.getItem(SK)) return Promise.resolve(true);
    var tok = window.prompt("Jeton d'acces MILES\n(il s'affiche au demarrage de : python miles.py --web)");
    if (!tok) { toast("Session MILES non fournie : action non executee.", false); return Promise.resolve(false); }
    return api("POST", "/session", { token: tok }).then(function (r) {
      if (r.status === 200 && r.json && r.json.session_id) {
        sessionStorage.setItem(SK, r.json.session_id);
        sessionStorage.setItem(CK, r.json.csrf_token || "");
        toast("Connecte a MILES (" + (r.json.user_id || "local") + ").", true);
        setTimeout(loadTelemetry, 0);
        return true;
      }
      toast("Connexion refusee : " + (r.json && r.json.error ? r.json.error : "HTTP " + r.status), false);
      return false;
    }).catch(function () {
      toast("Serveur MILES injoignable sur 127.0.0.1:8080 — lancez miles.py --web.", false);
      return false;
    });
  }

  /* Boutons du cockpit -> routes reelles MILES.
     Les commandes propres a la Miles Box demo (« Aura violette »,
     « Redemarre le boitier »...) restent locales : pas de fausse promesse. */
  var ACTIONS = [
    { re: /^statut du bo[iî]tier$/i, run: function () {
        return api("GET", "/status").then(function (r) {
          if (r.status !== 200 || !r.json) return toast("MILES /status: HTTP " + r.status, false);
          var j = r.json;
          toast("MILES /status\nFournisseur : " + j.name + "\nMode : " + j.mode +
                "\nDisponibilite : " + (j.availability || "non testee") +
                "\nMessages : " + (j.messages_count !== undefined ? j.messages_count : "?"), true);
        });
      }},
    { re: /^architecture du firmware$/i, run: function () {
        return api("GET", "/provider").then(function (r) {
          if (r.status !== 200 || !r.json) return toast("MILES /provider: HTTP " + r.status, false);
          var j = r.json;
          toast("MILES /provider\n" + j.model + "\n" + j.base_url + "\nDispo : " + (j.availability || "non testee"), true);
        });
      }},
    { re: /^active le mode furtif$/i, run: function () {
        return api("GET", "/log").then(function (r) {
          if (r.status !== 200 || !r.json) return toast("MILES /log: HTTP " + r.status, false);
          var e = r.json.entries || [];
          var lignes = e.slice(-5).reverse().map(function (x) { return x.timestamp.slice(11, 19) + "  " + x.tool_id + "  " + x.result; });
          toast("Journal d'activite MILES (" + e.length + ")\n" + (lignes.join("\n") || "aucune activite"), true);
        });
      }}
  ];

  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("button,[role=button]") : null;
    if (!el) return;
    var t = (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ");
    for (var i = 0; i < ACTIONS.length; i++) {
      if (ACTIONS[i].re.test(t)) {
        e.preventDefault(); e.stopPropagation();
        ensureSession().then(function (ok) { if (ok) ACTIONS[i].run(); });
        return;
      }
    }
  }, true);

  /* Chat : Entree dans un champ -> VRAIE reponse MILES (POST /message). */
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" || e.shiftKey) return;
    var el = e.target;
    if (!el || (el.tagName !== "TEXTAREA" && el.tagName !== "INPUT")) return;
    if (el.type && el.type !== "text") return;
    var txt = (el.value || "").trim();
    if (!txt) return;
    e.preventDefault(); e.stopPropagation();
    ensureSession().then(function (ok) {
      if (!ok) return;
      return api("POST", "/message", { message: txt }).then(function (r) {
        if (r.status === 200 && r.json) {
          var rep = r.json.response || r.json.error || "(vide)";
          toast("MILES : " + rep, !r.json.error);
        } else {
          toast("MILES /message : HTTP " + r.status, false);
        }
      });
    });
  }, true);

  /* --- Filigrane Readdy : retrait defensif (2e couche) --- */
  function _killWatermark() {
    var w = document.getElementById("watermark");
    if (w) { w.remove(); return true; }
    return false;
  }
  _killWatermark();
  if (window.MutationObserver && document.documentElement) {
    new MutationObserver(function () { _killWatermark(); _repairTexts(); _truth(); _liveTiles(); })
      .observe(document.documentElement, { childList: true, subtree: true });
  }
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest ? e.target.closest("a[href*='readdy.ai']") : null;
    if (a && !/static\.readdy\.ai/.test(a.href)) {
      e.preventDefault(); e.stopPropagation();
      toast("Lien Readdy neutralise (copie locale de votre site).", true);
    }
  }, true);

  /* ================= v2 — pont complet =================
     (1) saut automatique du préchargeur bloqué,
     (2) réparation des textes cassés par l'animation (source = aria-label),
     (3) connecteurs réels supplémentaires,
     (4) badge d'état MILES réel,
     (5) vérité : valeurs matérielles marquées « (démo) », aucune donnée inventée. */

  function _skipLoader() {
    if (!document.body) return false;
    var txt = document.body.innerText || "";
    if (txt.indexOf("CHARGEMENT") === -1) return true;
    var btn = null;
    document.querySelectorAll("button,div,span,a").forEach(function (el) {
      if (!btn && el.children.length === 0 && /^Passer/i.test((el.textContent || "").trim())) btn = el;
    });
    if (btn) btn.click();
    ["keydown", "keyup"].forEach(function (type) {
      var ev = new KeyboardEvent(type, { key: "Escape", keyCode: 27, which: 27, bubbles: true });
      window.dispatchEvent(ev); document.dispatchEvent(ev);
    });
    return false;
  }
  function _hideLoader() {
    if (!document.body) return;
    if ((document.body.innerText || "").indexOf("CHARGEMENT") === -1) return;
    var el = null;
    document.querySelectorAll("div,span,p").forEach(function (n) {
      if (!el && ((n.textContent || "").trim().indexOf("CHARGEMENT") === 0) && n.children.length <= 3) el = n;
    });
    if (!el) return;
    var node = el;
    for (var i = 0; i < 4 && node; i++) {
      var cs = getComputedStyle(node);
      if (cs.position === "fixed" || cs.position === "absolute") { node.style.display = "none"; return; }
      node = node.parentElement;
    }
    el.style.display = "none";
  }
  var _skipTries = 0;
  var _skipTimer = setInterval(function () {
    try {
      if (_skipLoader()) { clearInterval(_skipTimer); return; }
      _skipTries++;
      if (_skipTries >= 16) _hideLoader();
      if (_skipTries > 120) clearInterval(_skipTimer);
    } catch (e) { clearInterval(_skipTimer); }
  }, 500);

  /* --- Telemetrie reelle (GET /api/device) --------------------------------
     L'interface de demonstration affiche des valeurs fabriquees (Math.random).
     On les remplace par des mesures effectives du poste qui heberge MILES, et
     par un « indisponible » explicite pour les capteurs qui n'existent pas.
     Aucune valeur n'est inventee, aucun secret n'est affiche. */
  var TELEM = null;
  var LATENCE_MS = null;   // aller-retour mesure vers MILES (loopback)

  function _fmtDuree(sec) {
    sec = Math.max(0, sec | 0);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
    if (h) return h + " h " + m + " min";
    if (m) return m + " min";
    return sec + " s";
  }

  function _ms() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  function loadTelemetry() {
    if (!sessionStorage.getItem(SK)) return Promise.resolve(null);
    var t0 = _ms();
    return api("GET", "/api/device").then(function (r) {
      var t1 = _ms();
      if (r.status === 200 && r.json && r.json.host) {
        LATENCE_MS = Math.max(1, Math.round(t1 - t0));
        TELEM = r.json;
        try { _truth(); _paintTelemetry(); _liveTiles(); } catch (e) {}
      }
      return TELEM;
    }).catch(function () { return TELEM; });
  }

  /* --- Tuiles de demonstration -> mesures reelles ------------------------
     L'application de demonstration fabrique la charge, la batterie, les
     ventilateurs, le signal, la latence et la session. Aucune de ces mesures
     n'existe cote MILES : on affiche la mesure reelle quand elle existe, et un
     « non mesure » explicite sinon — jamais un chiffre plausible a la place
     d'un capteur absent. */
  var TUILE = {
    "charge": function () { return "non mesur\u00e9e"; },
    "batterie": function () { return "non suivie"; },
    "ventilateurs": function () { return "non expos\u00e9s"; },
    "signal": function () { return "non mesur\u00e9"; },
    "bande passante": function () { return "non mesur\u00e9e"; },
    "latence": function () {
      return LATENCE_MS === null ? "non mesur\u00e9e" : LATENCE_MS + " ms (locale)";
    },
    "session": function () {
      var p = (TELEM && TELEM.process) || null;
      return p && p.uptime_seconds !== undefined ? _fmtDuree(p.uptime_seconds) : "non mesur\u00e9e";
    }
  };
  var VALEUR = /^\d{1,4}(?:[.,]\d{1,2})?\s*(?:%|rpm|ms|Mbps|Mbit\/s|h|min|s|\u00b0C)$/i;
  var DUREE = /^\d{1,3}\s*h\s*\d{1,2}\s*min$/i;

  function _dansUnControle(el) {
    var n = el;
    for (var i = 0; i < 4 && n; i++, n = n.parentElement) {
      if (n.querySelector && n.querySelector("input[type=range],[role=slider]")) return true;
    }
    return false;
  }

  function _valeurDe(labelEl) {
    /* Candidats volontairement limites aux VOISINS IMMEDIATS du libelle et de
       son conteneur : remonter plus haut faisait ecrire la latence dans la
       tuile voisine (la tuile suivante contient elle aussi un nombre). */
    var candidats = [];
    var branche = labelEl.parentElement;
    if (labelEl.nextElementSibling) candidats.push(labelEl.nextElementSibling);
    if (branche) {
      if (branche.nextElementSibling) candidats.push(branche.nextElementSibling);
      if (branche.previousElementSibling) candidats.push(branche.previousElementSibling);
    }
    for (var j = 0; j < candidats.length; j++) {
      var n = candidats[j];
      if (n === labelEl || n.contains(labelEl)) continue;
      var t = (n.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
      if (n.children.length === 0 && (VALEUR.test(t) || DUREE.test(t))) return n;
      if (n.children.length <= 2) {
        for (var k = 0; k < n.children.length; k++) {
          var c = n.children[k];
          if (c === labelEl || (c.contains && c.contains(labelEl))) continue;
          var ct = (c.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
          if (c.children.length === 0 && (VALEUR.test(ct) || DUREE.test(ct))) return c;
        }
      }
    }
    return null;
  }

  function _liveTiles() {
    if (!document.body || !TELEM) return;
    if (_liveTilesEnCours) return;      // jamais reentrant (observer + intervalle)
    _liveTilesEnCours = true;
    try { _liveTilesPasse(); } finally { _liveTilesEnCours = false; }
  }

  var _liveTilesEnCours = false;

  function _liveTilesPasse() {
    var cles = Object.keys(TUILE);
    document.querySelectorAll("p,span,dt,strong").forEach(function (el) {
      if (el.children.length) return;                       // libelle feuille
      var cle = (el.textContent || "").trim().toLowerCase().replace(/[\s\u00a0]+/g, " ");
      if (cles.indexOf(cle) === -1) return;
      if (_dansUnControle(el)) return;                      // jamais un reglage
      var cible = _valeurDe(el);
      if (!cible) return;
      var texte = TUILE[cle]();
      if ((cible.textContent || "").trim() === texte) return;   // rien a faire : aucune mutation
      cible.setAttribute("data-mts-live", cle);                  // marque AVANT d'ecrire
      cible.textContent = texte;
    });
  }

  function _telemetryRows() {
    if (!TELEM) return null;
    var host = TELEM.host || {}, disk = TELEM.disk || {};
    var proc = TELEM.process || {}, prov = TELEM.provider || {};
    var rows = [
      ["Hote", host.name + " · " + host.system + " " + host.release],
      ["Processeur", host.cpu_count + " cœurs logiques"],
      ["Disque", disk.available ? disk.used_percent + " % utilise · " +
        Math.round(disk.free_bytes / 1073741824) + " Gio libres" : "indisponible"],
      ["Processus", "pid " + proc.pid + " · en service " + _fmtDuree(proc.uptime_seconds)],
      ["Fournisseur", prov.name],
      ["Modele", prov.model],
      ["Memoire", (TELEM.memory && TELEM.memory.label) || "—"]
    ];
    return rows;
  }

  function _paintTelemetry() {
    if (!document.body) return;
    var surBoitier = /\/(device|boitier)\/?$/.test(location.pathname);
    var box = document.getElementById("miles-telemetry");
    if (!surBoitier || !TELEM) { if (box) box.remove(); return; }
    if (!box) {
      box = document.createElement("section");
      box.id = "miles-telemetry";
      box.setAttribute("aria-label", "Telemetrie reelle MILES");
      box.style.cssText = "position:fixed;left:16px;bottom:84px;z-index:99997;width:300px;max-width:calc(100vw - 32px);" +
        "background:#12161d;border:1px solid #232936;border-radius:12px;padding:12px 14px;" +
        "font:12px/1.5 system-ui,sans-serif;color:#e6e8ee;box-shadow:0 12px 32px rgba(0,0,0,.5)";
      var head = document.createElement("div");
      head.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px";
      var titre = document.createElement("strong");
      titre.textContent = "Donnees reelles · MILES local";
      titre.style.fontSize = "11px";
      var fermer = document.createElement("button");
      fermer.type = "button"; fermer.textContent = "×";
      fermer.setAttribute("aria-label", "Masquer la telemetrie");
      fermer.style.cssText = "background:none;border:0;color:#9aa1b3;font-size:16px;cursor:pointer;line-height:1";
      fermer.onclick = function () { box.remove(); };
      head.appendChild(titre); head.appendChild(fermer);
      var dl = document.createElement("dl");
      dl.id = "miles-telemetry-body";
      dl.style.cssText = "margin:0;display:grid;grid-template-columns:88px 1fr;gap:4px 8px";
      box.appendChild(head); box.appendChild(dl);
      document.body.appendChild(box);
    }
    var dl = document.getElementById("miles-telemetry-body");
    var rows = _telemetryRows();
    if (!dl || !rows) return;
    var signature = JSON.stringify(rows);
    if (dl.dataset.signature === signature) return;  // aucune mutation inutile
    dl.dataset.signature = signature;
    dl.textContent = "";
    rows.forEach(function (pair) {
      var dt = document.createElement("dt");
      dt.textContent = pair[0];
      dt.style.cssText = "color:#9aa1b3;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em";
      var dd = document.createElement("dd");
      dd.textContent = pair[1];
      dd.style.cssText = "margin:0;overflow-wrap:anywhere";
      dl.appendChild(dt); dl.appendChild(dd);
    });
    var capteurs = document.createElement("p");
    capteurs.style.cssText = "margin:10px 0 0;color:#9aa1b3;font-size:10.5px";
    capteurs.textContent = "Capteurs boitier : " + ((TELEM.sensors || []).map(function (s) {
      return s.label + " indisponible";
    }).join(" · ") || "—");
    dl.appendChild(capteurs);
  }

  function _repairTexts() {
    document.querySelectorAll("[aria-label]").forEach(function (el) {
      if (el.dataset.mts) return;
      var est_split = (el.className && String(el.className).indexOf("split") !== -1) || el.querySelector(".split-line,.split-word,.split-char");
      if (!est_split) return;
      var marque = el.querySelector("[data-mts]");
      if (marque) return; // ne jamais effacer une marque (evite la boucle repair<->truth)
      var aria = (el.getAttribute("aria-label") || "").trim();
      if (!aria || aria.length > 60) return;
      if (aria.indexOf("\u00b0C") !== -1 || aria === "Miles est en ligne" || aria === "Miles LOCAL" || aria === "LOCAL" ||
          aria === "Hors ligne" || aria === "Aucune adresse" || aria.indexOf("miles-local") !== -1 ||
          aria.indexOf("d\u00e9mo") !== -1 || aria.indexOf("\u00c9veill") === 0) return; // libelle faux : ne pas ressusciter
      // Valeur de demonstration gravee dans l'aria-label (charge, batterie,
      // ventilateurs, signal, latence, session) : la restaurer annulerait la
      // mesure reelle et declencherait une boucle de micro-taches avec
      // _liveTiles (chaque mutation en rappelle une autre).
      if (VALEUR.test(aria) || DUREE.test(aria)) return;
      if (el.querySelector("[data-mts-live]")) return;   // deja remplace : intouchable
      var vis = (el.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
      if (vis && vis !== aria) el.textContent = aria;   // texte degrade par l'animation
    });
  }

  function _truth() {
    if (!document.body) return;
    var actif = !!sessionStorage.getItem(SK);
    var te = TELEM;
    var reel = !!(te && te.host);
    var reTemp = /\d{1,3}\s*\u00b0C/;
    document.querySelectorAll("div,span,p,li,b,strong,em,i,small,code").forEach(function (el) {
      var t = (el.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
      if (!t || t.length > 75) return;
      var remplace = null;
      if (reTemp.test(t) && t.length <= 50 && !/^Erreur|^Capteurs/.test(t)) {
        // La temperature n'existe pas, mais le reste de la machine est
        // mesurable : on affiche une donnee reelle a la place du chiffre faux.
        remplace = reel ? "CPU " + te.host.cpu_count + " cœurs · disque " + te.disk.used_percent + " %"
                        : "\u26a0 pas de capteurs";
      } else if (t.indexOf("Miles est en ligne") === 0) {
        remplace = reel ? "Miles repond (MILES local)" : "\u26a0 hors ligne";
      } else if (t === "\u00c9veill\u00e9" || t.indexOf("\u00c9veill\u00e9") === 0) {
        remplace = reel ? "en service " + _fmtDuree((te.process || {}).uptime_seconds) : "\u26a0 hors ligne";
      } else if (t === "Miles LOCAL" || t === "LOCAL") {
        remplace = reel ? String((te.provider || {}).mode || "local") : "\u26a0 source absente";
      } else if (t === "miles-local-7b") {
        remplace = reel ? String((te.provider || {}).model || "—") : "\u26a0 id introuvable";
      } else if (t === "Aucune adresse") {
        remplace = reel ? "127.0.0.1:8080" : (actif ? "MILES 127.0.0.1" : "\u26a0 aucune source");
      } else if (t === "Hors ligne") {
        remplace = reel ? "connecte · 127.0.0.1:8080" : "\u26a0 Bo\u00eetier non connecte";
      } else {
        return;
      }
      // noeud le plus interne : si un descendant porte la meme donnee, on l'ecarte
      var desc = el.querySelectorAll("div,span,p,li,b,strong,em,i,small,code");
      for (var i = 0; i < desc.length; i++) {
        var dt = (desc[i].textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
        if (dt === t || (reTemp.test(t) && reTemp.test(dt))) return;
      }
      // anti-boucle : si le remplacement est deja applique, rien a faire
      var actuel = (el.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
      if (actuel === remplace) return;
      el.textContent = remplace;
    });
    _badge();
  }

  function _badge() {
    var actif = !!TELEM;   // allume seulement si MILES a REELLEMENT repondu
    var b = document.getElementById("miles-badge");
    if (!b) {
      if (!document.body) return;
      b = document.createElement("div");
      b.id = "miles-badge";
      b.style.cssText = "position:fixed;top:12px;right:12px;z-index:99998;font:600 12px system-ui;padding:6px 12px;border-radius:99px;pointer-events:none";
      document.body.appendChild(b);
    }
    var label = actif ? "MILES ● actif (127.0.0.1)" : "MILES ○ aucune mesure";
    if (b.textContent !== label) b.textContent = label;   // garde : AUCUNE mutation si inchange (sinon boucle observer)
    var etat = actif ? "1" : "0";
    if (b.dataset.on !== etat) {
      b.dataset.on = etat;
      b.style.background = actif ? "#0f2a1f" : "#1a1e28";
      b.style.color = actif ? "#34d399" : "#9aa1b3";
      b.style.border = "1px solid " + (actif ? "#34d399" : "#5a6173");
    }
  }
  _badge();

  /* Connecteurs reels supplementaires (pages du cockpit -> routes MILES) */
  ACTIONS.push(
    { re: /^réglages$/i, run: function () { _openSettingsPanel(); } },
    { re: /^routines$/i, run: function () {
        return api("GET", "/missions").then(function (r) {
          if (r.status !== 200 || !r.json) return toast("MILES /missions indisponible : HTTP " + r.status, false);
          var ms = r.json.missions || [];
          var lignes = ms.slice(0, 5).map(function (m) { return m.state + "  " + (m.objective || "").slice(0, 60); });
          toast("Missions MILES (" + ms.length + ")\n" + (lignes.join("\n") || "aucune mission"), true);
        });
      }},
    { re: /^bo[iî]tier$/i, run: function () {
        return api("GET", "/status").then(function (r) {
          if (r.status !== 200 || !r.json) return toast("MILES /status indisponible : HTTP " + r.status, false);
          var j = r.json;
          toast("MILES /status\n" + j.name + " · " + j.mode + "\nMémoire : " + (j.memory_available ? "activée" : "désactivée") + "\nDispo : " + (j.availability || "non testee"), true);
        });
      }}
  );

  /* Onglets (souvent des <div>/<a> leaf, pas des boutons) : second capteur */
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t) return;
    if (t.closest && t.closest("button,[role=button]")) return; // deja gere par le 1er capteur
    var label = (t.textContent || "").trim().replace(/\s+/g, " ");
    if (!label || label.length > 40) return; // seuls les libelles EXACTS declenchent
    for (var i = 0; i < ACTIONS.length; i++) {
      if (ACTIONS[i].re.test(label)) { ACTIONS[i].run(); return; }
    }
  }, true);

  /* --- Cockpit projet : lien dans la navigation existante -----------------
     L'app React ne connait pas le cockpit ; on ajoute un lien vers les vues
     Projet / Conversation / Memoire / Outils servies par le meme serveur sous
     /cockpit/ (implementation unique du depot, aucun contenu recopie). */
  var BASE = "";

  function _addProjectLink() {
    document.querySelectorAll('nav[aria-label="Navigation principale"]').forEach(function (nav) {
      if (!nav.querySelector("a[data-miles-projet]")) {
        var modele = nav.querySelector("a");
        if (!modele) return;
        var a = modele.cloneNode(true);
        a.setAttribute("data-miles-projet", "1");
        a.setAttribute("href", BASE + "/cockpit/");
        // Le modele clone est un Link React : sans ce garde, React Router
        // intercepte le clic et affiche son propre 404. On force la navigation
        // complete, en capture, avant que le routeur ne voie l'evenement.
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          window.location.assign(a.getAttribute("href"));
        }, true);
        a.removeAttribute("aria-current");
        a.classList.remove("is-active", "active");
        a.style.background = "";
        a.style.color = "";
        var icone = a.querySelector("i");
        if (icone) icone.className = "ri-layout-column-line";
        a.childNodes.forEach(function (n) {
          if (n.nodeType === 3 && n.textContent.trim()) n.textContent = "Projet";
        });
        nav.appendChild(a);
      }
    });
  }
  _addProjectLink();
  setInterval(function () { try { _addProjectLink(); } catch (e) {} }, 1500);
  setInterval(function () { try { _repairTexts(); _truth(); _liveTiles(); } catch (e) {} }, 1500);

  function _openSettingsPanel() {
    var old = document.getElementById("miles-settings");
    if (old) { old.remove(); return; }
    var p = document.createElement("div");
    p.id = "miles-settings";
    p.style.cssText = "position:fixed;top:72px;right:16px;width:344px;max-width:calc(100vw - 32px);z-index:99997;" +
      "background:#13161e;border:1px solid #262a36;border-radius:12px;padding:16px;" +
      "font:14px/1.5 system-ui,sans-serif;color:#e6e8ee;box-shadow:0 12px 40px rgba(0,0,0,.55)";
    p.innerHTML = "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px'>" +
      "<strong style='font-size:15px'>Connexion rapide IA</strong>" +
      "<button id='ms-close' aria-label='Fermer' style='background:none;border:0;color:#9aa1b3;font-size:18px;cursor:pointer;width:32px;height:32px'>×</button></div>" +
      "<div id='ms-etat' style='font-size:12.5px;color:#9aa1b3;margin-bottom:10px'>Chargement de l'état MILES…</div>" +
      "<label for='ms-provider' style='font-size:12.5px;color:#9aa1b3'>Fournisseur</label>" +
      "<select id='ms-provider' style='width:100%;margin:4px 0 10px;padding:8px;background:#1a1e28;color:#e6e8ee;border:1px solid #262a36;border-radius:8px'>" +
      "<option value='groq'>Groq</option><option value='gemini'>Gemini</option>" +
      "<option value='mistral'>Mistral</option><option value='openai'>OpenAI</option>" +
      "<option value='claude'>Claude</option></select>" +
      "<label for='ms-key' style='font-size:12.5px;color:#9aa1b3'>Clé API (masquée, jamais retournée)</label>" +
      "<input id='ms-key' type='password' autocomplete='off' placeholder='clé du fournisseur' " +
      "style='width:100%;margin:4px 0 10px;padding:8px;background:#1a1e28;color:#e6e8ee;border:1px solid #262a36;border-radius:8px'>" +
      "<button id='ms-save' style='width:100%;padding:10px;background:#5b7cff;color:#fff;border:0;border-radius:8px;font-weight:600;cursor:pointer'>Connecter et enregistrer</button>" +
      "<div id='ms-result' style='margin-top:10px;font-size:12.5px'></div>";
    document.body.appendChild(p);
    document.getElementById("ms-close").onclick = function () { p.remove(); };
    Promise.all([api("GET", "/status"), api("GET", "/provider")]).then(function (r) {
      var st = r[0], pv = r[1], box = document.getElementById("ms-etat");
      if (!box || !document.body.contains(p)) return;
      if (st.status === 401) {
        box.innerHTML = "<span style='color:#fbbf24'>Session MILES requise : validez une action pour connecter.</span>";
        return;
      }
      if (st.status !== 200 || !st.json) {
        box.innerHTML = "<span style='color:#f87171'>⚠ État MILES indisponible (HTTP " + st.status + ")</span>";
        return;
      }
      box.innerHTML = "Fournisseur : " + st.json.name + " · " + st.json.mode + "<br>" +
        "Modèle : " + ((pv.json && pv.json.model) || "—") +
        " · Dispo : " + (st.json.availability || "non testée") +
        "<br><span style='color:#5a6173'>Clé stockée localement dans .env, jamais affichée.</span>";
    }).catch(function () {
      var box = document.getElementById("ms-etat");
      if (box) box.innerHTML = "<span style='color:#f87171'>⚠ Serveur MILES injoignable</span>";
    });
    document.getElementById("ms-save").onclick = function () {
      var prov = document.getElementById("ms-provider").value;
      var key = document.getElementById("ms-key").value;
      var res = document.getElementById("ms-result");
      res.innerHTML = "<span style='color:#9aa1b3'>Envoi…</span>";
      ensureSession().then(function (ok) {
        if (!ok) { res.innerHTML = "<span style='color:#f87171'>⚠ Session MILES refusée ou injoignable</span>"; return; }
        return api("POST", "/configure", { provider: prov, api_key: key }).then(function (r) {
          if (r.status === 200 && r.json && r.json.ok) {
            res.innerHTML = "<span style='color:#34d399'>✓ " + r.json.message + "</span>";
            document.getElementById("ms-key").value = "";
          } else {
            var msg = (r.json && r.json.error) || ("HTTP " + r.status);
            res.innerHTML = "<span style='color:#f87171'>⚠ " + msg + "</span>";
          }
        }).catch(function () {
          res.innerHTML = "<span style='color:#f87171'>⚠ Serveur MILES injoignable</span>";
        });
      });
    };
  }

  window.MILES_BRIDGE = { api: api, toast: toast, ensureSession: ensureSession, version: "1.1" };

  /* Telemetrie : chargee des qu'une session existe, rafraichie doucement
     (une requete locale toutes les 15 s, pas de boucle serree). */
  if (sessionStorage.getItem(SK)) { setTimeout(loadTelemetry, 600); }
  setInterval(function () {
    if (sessionStorage.getItem(SK)) loadTelemetry();
  }, 15000);

  setTimeout(function () {
    toast(sessionStorage.getItem(SK)
      ? "Pont MILES actif — donnees reelles via 127.0.0.1:8080."
      : "Session MILES non ouverte : la telemetrie reelle s'affichera apres connexion.",
      !!sessionStorage.getItem(SK));
  }, 1500);
})();
