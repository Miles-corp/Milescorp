'use strict';

/* MILES — cockpit projet (client)
 *
 * Règles appliquées :
 * - le jeton de session et le jeton CSRF ne vivent qu'en mémoire vive :
 *   jamais dans un cookie, jamais dans localStorage ;
 * - tout contenu venu des documents ou du serveur est inséré avec
 *   textContent, jamais avec innerHTML ;
 * - les transitions de statut autorisées sont fournies par le serveur
 *   (`transitions`) : le client ne les réinvente pas.
 */

const STATUS_LABELS = {
  TODO: 'À faire',
  IN_PROGRESS: 'En cours',
  BLOCKED: 'Bloqué',
  DONE: 'Terminé',
  CANCELLED: 'Annulé',
};

const COLUMNS = ['TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE'];

/* Nombre de cartes affichées d'emblée par colonne (les colonnes
   terminées sont longues et peu actionnables). */
const HIDDEN_BY_DEFAULT = { DONE: 6 };

const state = {
  session: null,
  board: null,
  agent: 'Agent A',
  view: 'projet',
};

const byId = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ */
/* Transport                                                          */
/* ------------------------------------------------------------------ */

function authHeaders(extra) {
  const headers = Object.assign({ 'Content-Type': 'application/json' }, extra || {});
  if (state.session) {
    headers['X-MILES-Session'] = state.session.session_id;
    headers['X-MILES-CSRF'] = state.session.csrf_token;
  }
  return headers;
}

async function api(path, options) {
  const settings = options || {};
  const response = await fetch(path, {
    method: settings.method || 'GET',
    headers: authHeaders(settings.headers),
    body: settings.body === undefined ? undefined : JSON.stringify(settings.body),
  });

  if (response.status === 401) {
    showLogin('Session absente ou expirée. Reconnectez-vous.');
    throw new Error('Session expirée.');
  }

  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }

  if (!response.ok) {
    const message = (payload && payload.error) || `Erreur HTTP ${response.status}`;
    const failure = new Error(message);
    failure.code = payload && payload.code;
    throw failure;
  }
  return payload;
}

/* ------------------------------------------------------------------ */
/* Interface générale                                                 */
/* ------------------------------------------------------------------ */

let toastTimer = null;

function toast(message, tone) {
  const element = byId('toast');
  element.textContent = message;
  element.dataset.tone = tone || 'info';
  element.hidden = false;
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    element.hidden = true;
  }, tone === 'error' ? 8000 : 4200);
}

function showLogin(message) {
  state.session = null;
  byId('login').hidden = false;
  byId('app').hidden = true;
  byId('topbar-session').hidden = true;
  const error = byId('login-error');
  if (message) {
    error.textContent = message;
    error.hidden = false;
  } else {
    error.hidden = true;
  }
}

function showApp() {
  byId('login').hidden = true;
  byId('app').hidden = false;
  byId('topbar-session').hidden = false;
  selectView(state.view, false);
}

function selectView(name, focus) {
  state.view = name;
  const tabs = Array.from(document.querySelectorAll('.tab'));
  tabs.forEach((tab) => {
    const selected = tab.dataset.view === name;
    tab.setAttribute('aria-selected', selected ? 'true' : 'false');
    tab.tabIndex = selected ? 0 : -1;
    const panel = byId(`vue-${tab.dataset.view}`);
    if (panel) panel.hidden = !selected;
    if (selected && focus) tab.focus();
  });
  if (name === 'projet') loadBoard();
  if (name === 'memoire') loadMemories();
  if (name === 'outils') loadTools();
}

function initTabs() {
  const tabs = Array.from(document.querySelectorAll('.tab'));
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectView(tab.dataset.view, false));
    tab.addEventListener('keydown', (event) => {
      let next = null;
      if (event.key === 'ArrowRight') next = tabs[(index + 1) % tabs.length];
      if (event.key === 'ArrowLeft') next = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === 'Home') next = tabs[0];
      if (event.key === 'End') next = tabs[tabs.length - 1];
      if (next) {
        event.preventDefault();
        selectView(next.dataset.view, true);
      }
    });
  });
}

/* ------------------------------------------------------------------ */
/* Session                                                            */
/* ------------------------------------------------------------------ */

async function login(event) {
  event.preventDefault();
  const error = byId('login-error');
  const token = byId('token').value.trim();
  error.hidden = true;
  if (!token) {
    error.textContent = 'Saisissez le jeton affiché au démarrage du serveur.';
    error.hidden = false;
    return false;
  }
  try {
    const response = await fetch('/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: token }),
    });
    const payload = await response.json();
    if (!response.ok) {
      error.textContent = payload.error || 'Connexion refusée.';
      error.hidden = false;
      return false;
    }
    state.session = payload;
    byId('token').value = '';
    showApp();
    toast('Session ouverte.', 'ok');
    await loadAll();
  } catch (failure) {
    error.textContent = 'Erreur réseau : ' + failure.message;
    error.hidden = false;
  }
  return false;
}

async function logout() {
  try {
    await api('/logout', { method: 'POST', body: {} });
  } catch (error) {
    /* La session peut déjà être expirée : on ferme quand même l'interface. */
  }
  state.session = null;
  state.board = null;
  showLogin('Session fermée.');
  toast('Session fermée.');
}

/* ------------------------------------------------------------------ */
/* Santé du service                                                   */
/* ------------------------------------------------------------------ */

function renderHealth(board) {
  const provider = (board.health && board.health.provider) || {};
  const memory = (board.health && board.health.memory) || {};

  byId('health-provider').textContent = provider.name || 'non configuré';
  const providerNote = [
    provider.mode ? `mode ${provider.mode}` : null,
    provider.model ? `modèle ${provider.model}` : null,
    provider.availability || null,
  ].filter(Boolean).join(' · ');
  byId('health-provider-note').textContent = providerNote || 'Disponibilité non testée';

  byId('health-memory').textContent = memory.available ? 'active' : 'indisponible';
  byId('health-memory').classList.toggle('is-off', !memory.available);

  const documents = board.documents || {};
  const names = Object.keys(documents);
  const readable = names.filter((name) => documents[name].exists).length;
  byId('health-docs').textContent = `${readable}/${names.length} lisibles`;
  const tasksMeta = documents['TASKS.md'];
  byId('health-docs-note').textContent = tasksMeta && tasksMeta.modified
    ? `TASKS.md modifié le ${formatDate(tasksMeta.modified)}`
    : 'Documents de coordination introuvables';

  byId('health-session').textContent = state.agent;
}

function formatDate(value) {
  if (!value) return 'date inconnue';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/* ------------------------------------------------------------------ */
/* Pilotage du projet                                                 */
/* ------------------------------------------------------------------ */

async function loadBoard() {
  if (!state.session) return;
  const error = byId('board-error');
  error.hidden = true;
  try {
    const board = await api('/api/project');
    state.board = board;
    renderBoard(board);
  } catch (failure) {
    error.textContent = failure.message;
    error.hidden = false;
    byId('board-meta').textContent = 'Pilotage indisponible';
  }
}

function renderBoard(board) {
  renderHealth(board);

  const documents = board.documents || {};
  const readable = Object.keys(documents).filter((name) => documents[name].exists).length;
  byId('board-meta').textContent =
    `${board.coordination_dir} · ${readable} document(s) lu(s) · actualisé à ${formatDate(board.generated_at)}`;

  renderSummary(board.summary || {});
  renderColumns(board);
  renderBlockages(board.blockages || []);
  renderDecisions(board.decisions || []);
  renderMessages(board.messages || {});
  renderIssues(board.issues || []);
}

function renderSummary(summary) {
  const container = byId('summary');
  container.textContent = '';
  const counts = summary.by_status || {};
  const total = document.createElement('article');
  total.className = 'stat';
  const totalValue = document.createElement('p');
  totalValue.className = 'stat-value';
  totalValue.textContent = String(summary.total || 0);
  const totalLabel = document.createElement('p');
  totalLabel.className = 'stat-label';
  totalLabel.textContent = 'Tâches suivies';
  total.append(totalValue, totalLabel);
  container.append(total);

  Object.keys(STATUS_LABELS).forEach((status) => {
    const card = document.createElement('article');
    card.className = 'stat';
    card.dataset.status = status;
    const value = document.createElement('p');
    value.className = 'stat-value';
    value.textContent = String(counts[status] || 0);
    const label = document.createElement('p');
    label.className = 'stat-label';
    label.textContent = STATUS_LABELS[status];
    card.append(value, label);
    container.append(card);
  });
}

function renderColumns(board) {
  const container = byId('board');
  container.textContent = '';
  const tasks = board.tasks || [];
  const transitions = board.transitions || {};

  COLUMNS.forEach((status) => {
    const column = document.createElement('section');
    column.className = 'column';
    column.dataset.status = status;

    const head = document.createElement('div');
    head.className = 'column-head';
    const title = document.createElement('h3');
    title.className = 'column-title';
    title.textContent = STATUS_LABELS[status];
    const count = document.createElement('span');
    count.className = 'count';
    const matching = tasks.filter((task) => task.status_base === status);
    count.textContent = String(matching.length);
    head.append(title, count);
    column.append(head);

    if (matching.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'skeleton';
      empty.textContent = 'Aucune tâche.';
      column.append(empty);
    }

    const limit = HIDDEN_BY_DEFAULT[status];
    const visible = limit ? matching.slice(0, limit) : matching;
    visible.forEach((task) => column.append(buildTaskCard(task, transitions)));

    if (visible.length < matching.length) {
      const hidden = matching.slice(visible.length);
      const more = document.createElement('button');
      more.type = 'button';
      more.className = 'btn btn-small btn-ghost';
      more.textContent = `Afficher les ${hidden.length} autres`;
      more.addEventListener('click', () => {
        more.remove();
        hidden.forEach((task) => column.append(buildTaskCard(task, transitions)));
      });
      column.append(more);
    }

    container.append(column);
  });

  const malformed = tasks.filter((task) => task.malformed);
  if (malformed.length) {
    const column = document.createElement('section');
    column.className = 'column';
    const head = document.createElement('div');
    head.className = 'column-head';
    const title = document.createElement('h3');
    title.className = 'column-title';
    title.textContent = 'Illisibles';
    head.append(title);
    column.append(head);
    malformed.forEach((task) => {
      const card = document.createElement('article');
      card.className = 'task-card';
      const id = document.createElement('p');
      id.className = 'task-id';
      id.textContent = task.id || 'ligne inconnue';
      const note = document.createElement('p');
      note.className = 'task-locked';
      note.textContent = 'Ligne incomplète : corriger TASKS.md à la main.';
      card.append(id, note);
      column.append(card);
    });
    container.append(column);
  }
}

function buildTaskCard(task, transitions) {
  const card = document.createElement('article');
  card.className = 'task-card';
  card.dataset.taskId = task.id;

  const header = document.createElement('header');
  const id = document.createElement('span');
  id.className = 'task-id';
  id.textContent = task.id;
  const owner = document.createElement('span');
  owner.className = 'task-owner';
  owner.textContent = task.owner || 'non assignée';
  header.append(id, owner);

  const title = document.createElement('h3');
  title.textContent = task.title || '(sans titre)';

  const meta = document.createElement('p');
  meta.className = 'task-meta';
  meta.textContent = task.updated ? `Mis à jour le ${task.updated}` : 'Jamais mis à jour';

  card.append(header, title, meta);

  if (task.description) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Description et fichiers';
    const description = document.createElement('p');
    description.textContent = task.description;
    details.append(summary, description);
    if (task.files) {
      const files = document.createElement('p');
      files.textContent = `Fichiers : ${task.files}`;
      details.append(files);
    }
    card.append(details);
  }

  const order = ['IN_PROGRESS', 'BLOCKED', 'CANCELLED', 'DONE'];
  const allowed = (transitions[task.status_base] || [])
    .filter((status) => status !== task.status_base)
    .sort((a, b) => order.indexOf(a) - order.indexOf(b));

  if (!allowed.length) {
    const locked = document.createElement('p');
    locked.className = 'task-locked';
    locked.textContent = 'Tâche clôturée : réouverture manuelle uniquement.';
    card.append(locked);
    return card;
  }

  const actions = document.createElement('div');
  actions.className = 'task-actions';
  const label = document.createElement('label');
  label.className = 'sr-only';
  label.htmlFor = `status-${task.id}`;
  label.textContent = `Nouveau statut pour ${task.id}`;
  const select = document.createElement('select');
  select.id = `status-${task.id}`;
  // Aucune transition n'est presélectionnée : une fausse manipulation ne
  // doit pas déplacer une tâche. Le bouton reste inactif tant que rien
  // n'est choisi explicitement.
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.disabled = true;
  placeholder.selected = true;
  placeholder.textContent = 'Changer…';
  select.append(placeholder);
  allowed.forEach((status) => {
    const option = document.createElement('option');
    option.value = status;
    option.textContent = STATUS_LABELS[status] || status;
    select.append(option);
  });
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'btn btn-small';
  button.textContent = 'Appliquer';
  button.disabled = true;
  select.addEventListener('change', () => {
    button.disabled = !select.value;
  });
  button.addEventListener('click', () => {
    if (select.value) applyStatus(task.id, select.value, button, task.status_base);
  });
  actions.append(label, select, button);
  card.append(actions);
  return card;
}

async function applyStatus(taskId, status, button, previous) {
  button.disabled = true;
  try {
    const result = await api(`/api/tasks/${encodeURIComponent(taskId)}/status`, {
      method: 'POST',
      body: { status: status, agent: state.agent },
    });
    toast(result.message || `${taskId} mis à jour.`, result.changed ? 'ok' : 'info');
    await loadBoard();
  } catch (failure) {
    button.disabled = false;
    toast(`${taskId} : ${failure.message}`, 'error');
    if (previous) {
      /* L'état affiché reste celui du serveur : on le relit. */
      await loadBoard();
    }
  }
}

function renderBlockages(lines) {
  const container = byId('blockages');
  container.textContent = '';
  const items = lines
    .map((line) => line.replace(/^[-*]\s*/, '').trim())
    .filter(Boolean);
  if (!items.length) {
    const item = document.createElement('li');
    item.className = 'is-empty';
    item.textContent = 'Aucun blocage déclaré dans STATUS.md.';
    container.append(item);
    return;
  }
  items.forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    container.append(item);
  });
}

function renderDecisions(decisions) {
  const container = byId('decisions');
  container.textContent = '';
  if (!decisions.length) {
    const item = document.createElement('li');
    item.className = 'is-empty';
    item.textContent = 'Aucune décision enregistrée.';
    container.append(item);
    return;
  }
  decisions.forEach((decision) => {
    const item = document.createElement('li');
    const code = document.createElement('code');
    code.textContent = decision.id;
    item.append(code, document.createTextNode(' ' + (decision.title || '')));
    const meta = document.createElement('span');
    meta.className = 'decision-meta';
    meta.textContent = [decision.date, decision.author, decision.status]
      .filter(Boolean)
      .join(' · ');
    item.append(meta);
    container.append(item);
  });
}

function renderMessages(messages) {
  const container = byId('messages');
  container.textContent = '';
  const pending = messages.pending || [];
  if (!pending.length) {
    const item = document.createElement('li');
    item.className = 'is-empty';
    item.textContent = 'Aucun message en attente.';
    container.append(item);
    return;
  }
  pending.forEach((message) => {
    const item = document.createElement('li');
    const head = document.createElement('strong');
    head.textContent = `${message.id} · ${message.route}`;
    const body = document.createElement('span');
    body.textContent = message.subject;
    item.append(head, body);
    container.append(item);
  });
}

function renderIssues(issues) {
  const container = byId('issues');
  container.textContent = '';
  if (!issues.length) {
    const item = document.createElement('li');
    item.className = 'is-empty';
    item.textContent = 'Aucune anomalie : documents cohérents.';
    container.append(item);
    return;
  }
  issues.forEach((issue) => {
    const item = document.createElement('li');
    const head = document.createElement('strong');
    head.textContent = issue.id || 'document';
    const body = document.createElement('span');
    body.textContent = issue.line ? `ligne ${issue.line} · ${issue.problem}` : issue.problem;
    item.append(head, body);
    container.append(item);
  });
}

/* ------------------------------------------------------------------ */
/* Conversation                                                       */
/* ------------------------------------------------------------------ */

function appendMessage(role, text) {
  const chat = byId('chat');
  const element = document.createElement('div');
  element.className = 'msg ' + role;
  element.textContent = text;
  chat.append(element);
  chat.scrollTop = chat.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();
  const input = byId('message');
  const text = input.value.trim();
  if (!text) return false;
  appendMessage('user', text);
  input.value = '';
  try {
    const payload = await api('/message', { method: 'POST', body: { message: text } });
    if (payload.response) appendMessage('assistant', payload.response);
    if (payload.error) appendMessage('error', 'Erreur : ' + payload.error);
  } catch (failure) {
    appendMessage('error', 'Erreur : ' + failure.message);
  }
  return false;
}

/* ------------------------------------------------------------------ */
/* Mémoire                                                            */
/* ------------------------------------------------------------------ */

async function loadMemories() {
  if (!state.session || state.view !== 'memoire') return;
  const container = byId('memories');
  container.textContent = '';
  try {
    const memories = await api('/memory');
    if (!Array.isArray(memories) || memories.length === 0) {
      const item = document.createElement('li');
      item.className = 'is-empty';
      item.textContent = 'Aucun souvenir enregistré.';
      container.append(item);
      return;
    }
    memories.forEach((memory) => {
      const item = document.createElement('li');
      const body = document.createElement('span');
      body.textContent = memory.content;
      const meta = document.createElement('span');
      meta.className = 'memory-meta';
      const parts = [];
      if (memory.category) parts.push(memory.category);
      if (typeof memory.importance !== 'undefined') parts.push('importance ' + memory.importance);
      if (memory.created_at) parts.push(memory.created_at);
      meta.textContent = parts.join(' · ') || 'sans catégorie';
      body.append(meta);

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'btn btn-small btn-ghost';
      remove.textContent = 'Oublier';
      remove.addEventListener('click', () => forgetMemory(memory.id, remove));

      item.append(body, remove);
      container.append(item);
    });
  } catch (failure) {
    const item = document.createElement('li');
    item.className = 'is-empty';
    item.textContent = 'Mémoire indisponible : ' + failure.message;
    container.append(item);
  }
}

async function addMemory(event) {
  event.preventDefault();
  const input = byId('memory-content');
  const content = input.value.trim();
  if (!content) return false;
  try {
    await api('/remember', { method: 'POST', body: { content: content } });
    input.value = '';
    toast('Souvenir enregistré.', 'ok');
    await loadMemories();
  } catch (failure) {
    toast('Mémorisation refusée : ' + failure.message, 'error');
  }
  return false;
}

async function forgetMemory(id, button) {
  button.disabled = true;
  try {
    await api('/forget', { method: 'POST', body: { id: id } });
    toast('Souvenir supprimé.', 'ok');
    await loadMemories();
  } catch (failure) {
    button.disabled = false;
    toast('Suppression impossible : ' + failure.message, 'error');
  }
}

/* ------------------------------------------------------------------ */
/* Outils                                                             */
/* ------------------------------------------------------------------ */

async function loadTools() {
  if (!state.session || state.view !== 'outils') return;
  const container = byId('tools');
  container.textContent = '';
  try {
    const payload = await api('/tools');
    const tools = (payload && payload.tools) || [];
    if (!tools.length) {
      const empty = document.createElement('p');
      empty.className = 'skeleton';
      empty.textContent = 'Aucun outil disponible.';
      container.append(empty);
      return;
    }
    tools.forEach((tool) => container.append(buildTool(tool)));
  } catch (failure) {
    const error = document.createElement('p');
    error.className = 'form-error';
    error.textContent = 'Chargement des outils impossible : ' + failure.message;
    container.append(error);
  }
}

function buildTool(tool) {
  const card = document.createElement('article');
  card.className = 'tool';

  const header = document.createElement('header');
  const name = document.createElement('code');
  name.textContent = tool.id;
  const risk = document.createElement('span');
  risk.className = 'risk';
  risk.dataset.risk = tool.risk_level || '';
  risk.textContent = tool.risk_level || 'risque inconnu';
  header.append(name, risk);
  if (tool.requires_confirmation) {
    const confirmation = document.createElement('span');
    confirmation.className = 'risk';
    confirmation.textContent = 'confirmation requise';
    header.append(confirmation);
  }

  const description = document.createElement('p');
  description.textContent = tool.description || '';

  const params = document.createElement('div');
  params.className = 'tool-params';
  (tool.parameters || []).forEach((parameter) => {
    const input = document.createElement('input');
    input.type = 'text';
    input.dataset.param = parameter.name;
    input.dataset.type = parameter.type;
    input.placeholder = parameter.name;
    input.setAttribute('aria-label', `${parameter.name} (${parameter.type})`);
    params.append(input);
  });

  const run = document.createElement('button');
  run.type = 'button';
  run.className = 'btn btn-small';
  run.textContent = 'Exécuter';
  run.addEventListener('click', () => runTool(tool, params, run));
  params.append(run);

  card.append(header, description, params);
  return card;
}

function collectParams(container) {
  const values = {};
  container.querySelectorAll('input[data-param]').forEach((input) => {
    const value = input.value.trim();
    if (!value) return;
    const type = input.dataset.type;
    if (type === 'int') values[input.dataset.param] = parseInt(value, 10);
    else if (type === 'float') values[input.dataset.param] = parseFloat(value);
    else if (type === 'bool') values[input.dataset.param] = (value === 'true' || value === '1');
    else values[input.dataset.param] = value;
  });
  return values;
}

async function postTool(toolId, parameters, confirmed, token) {
  const body = { tool: toolId, parameters: parameters };
  if (confirmed) {
    body.user_confirmed = true;
    body.confirmation_token = token;
  }
  return api('/tool', { method: 'POST', body: body });
}

async function runTool(tool, container, button) {
  const parameters = collectParams(container);
  button.disabled = true;
  try {
    let result = await postTool(tool.id, parameters, false, null);
    if (result.confirmation_required) {
      const accepted = window.confirm(
        `L'outil « ${tool.id} » requiert une confirmation humaine.\nExécuter ?`
      );
      if (!accepted) {
        appendMessage('system', 'Action annulée.');
        return;
      }
      result = await postTool(tool.id, parameters, true, result.confirmation_token);
    }
    if (result.success) {
      appendMessage(
        'assistant',
        `Résultat de ${tool.id} :\n${formatToolResult(result.result)}`
      );
      toast(`${tool.id} exécuté.`, 'ok');
    } else {
      appendMessage('error', `Outil ${tool.id} : ${result.error || 'échec'}`);
    }
  } catch (failure) {
    toast(`${tool.id} : ${failure.message}`, 'error');
  } finally {
    button.disabled = false;
  }
}

function formatToolResult(result) {
  if (result === null || result === undefined) return '(aucun résultat)';
  if (typeof result === 'object') return JSON.stringify(result, null, 2);
  return String(result);
}

/* ------------------------------------------------------------------ */
/* Démarrage                                                          */
/* ------------------------------------------------------------------ */

async function loadAll() {
  await loadBoard();
  if (state.view === 'memoire') await loadMemories();
  if (state.view === 'outils') await loadTools();
}

function init() {
  initTabs();
  byId('login-form').addEventListener('submit', login);
  byId('chat-form').addEventListener('submit', sendMessage);
  byId('memory-form').addEventListener('submit', addMemory);
  byId('logout').addEventListener('click', logout);
  byId('refresh-board').addEventListener('click', loadBoard);
  byId('agent').addEventListener('change', (event) => {
    state.agent = event.target.value;
    renderHealth(state.board || {});
    toast(`Vous agissez en tant que ${state.agent}.`);
  });
  showLogin();
}

document.addEventListener('DOMContentLoaded', init);
