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
    new MutationObserver(function () { _killWatermark(); _repairTexts(); _truth(); })
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
      var vis = (el.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
      if (vis && vis !== aria) el.textContent = aria;   // texte degrade par l'animation
    });
  }

  function _truth() {
    if (!document.body) return;
    var actif = !!sessionStorage.getItem(SK);
    var reTemp = /\d{1,3}\s*\u00b0C/;
    document.querySelectorAll("div,span,p,li,b,strong,em,i,small,code").forEach(function (el) {
      var t = (el.textContent || "").trim().replace(/[\s\u00a0]+/g, " ");
      if (!t || t.length > 75) return;
      var remplace = null;
      if (reTemp.test(t) && t.length <= 50 && !/^Erreur|^Capteurs/.test(t)) {
        remplace = "\u26a0 pas de capteurs";        // valeur materielle inexistante -> ERREUR
      } else if (t.indexOf("Miles est en ligne") === 0) {
        remplace = "\u26a0 hors ligne";        // fausse affirmation -> ERREUR
      } else if (t === "\u00c9veill\u00e9" || t.indexOf("\u00c9veill\u00e9") === 0) {
        remplace = "\u26a0 hors ligne";
      } else if (t === "Miles LOCAL" || t === "LOCAL") {
        remplace = "\u26a0 source absente";
      } else if (t === "miles-local-7b") {
        remplace = "\u26a0 id introuvable";
      } else if (t === "Aucune adresse") {
        remplace = actif ? "MILES 127.0.0.1" : "\u26a0 aucune source";
      } else if (t === "Hors ligne") {
        remplace = "\u26a0 Bo\u00eetier non connect\u00e9";
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
    _badge(actif);
  }

  function _badge(actif) {
    var b = document.getElementById("miles-badge");
    if (!b) {
      if (!document.body) return;
      b = document.createElement("div");
      b.id = "miles-badge";
      b.style.cssText = "position:fixed;top:12px;right:12px;z-index:99998;font:600 12px system-ui;padding:6px 12px;border-radius:99px;pointer-events:none";
      document.body.appendChild(b);
    }
    var label = actif ? "MILES ● actif (127.0.0.1)" : "MILES ○ non connecté";
    if (b.textContent !== label) b.textContent = label;   // garde : AUCUNE mutation si inchange (sinon boucle observer)
    var etat = actif ? "1" : "0";
    if (b.dataset.on !== etat) {
      b.dataset.on = etat;
      b.style.background = actif ? "#0f2a1f" : "#1a1e28";
      b.style.color = actif ? "#34d399" : "#9aa1b3";
      b.style.border = "1px solid " + (actif ? "#34d399" : "#5a6173");
    }
  }
  _badge(false);

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

  /* --- Page Projet : ajout d'un lien dans la navigation existante ---------
     L'app React ne connait pas cette page ; on ajoute un lien vers la page
     servie par serve.py (/projet). Aucun contenu n'est injecte dans le DOM
     React : la page est autonome et partage la session MILES de l'onglet. */
  var BASE = (location.pathname.match(/^\/preview\/[^\/]+\/[^\/]+/) || [""])[0];

  function _addProjectLink() {
    document.querySelectorAll('nav[aria-label="Navigation principale"]').forEach(function (nav) {
      if (!nav.querySelector("a[data-miles-projet]")) {
        var modele = nav.querySelector("a");
        if (!modele) return;
        var a = modele.cloneNode(true);
        a.setAttribute("data-miles-projet", "1");
        a.setAttribute("href", BASE + "/projet");
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
  setInterval(function () { try { _repairTexts(); _truth(); } catch (e) {} }, 3000);

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

  window.MILES_BRIDGE = { api: api, toast: toast, ensureSession: ensureSession, version: "1.0" };
  setTimeout(function () { toast("Pont MILES actif — boutons Statut / Firmware / Furtif et chat reli\u00e9s a 127.0.0.1:8080.", true); }, 1500);
})();
