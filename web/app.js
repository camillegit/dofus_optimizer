// Forge de Builds — front-end (vanilla JS)
const ELEMENT_NAMES = { terre: 'Terre', feu: 'Feu', eau: 'Eau', air: 'Air', neutre: 'Neutre', multi: 'Multi' };

const SLOT_LABELS = {
  chapeau: 'Coiffe', cape: 'Cape', amulette: 'Amul.', ceinture: 'Ceint.', arme: 'Arme', bouclier: 'Boucl.',
  anneau1: 'Anneau', anneau2: 'Anneau', bottes: 'Bottes', familier: 'Fami.',
  dofus1: 'Dofus', dofus2: 'Dofus', dofus3: 'Dofus', dofus4: 'Dofus', dofus5: 'Dofus', dofus6: 'Dofus',
};
const WEAPONS = new Set([2, 3, 4, 5, 6, 7, 8, 19, 22]);
const PETS = new Set([18, 121, 331, 332, 333]);

// Character sheet groups (stat display names as returned by the API)
const SHEET = [
  ['Combat', ['PA', 'PM', 'Portée', 'Invocations', 'Initiative', '% Critique', 'Puissance']],
  ['Caractéristiques', ['Vitalité', 'Sagesse', 'Force', 'Intelligence', 'Chance', 'Agilité']],
  ['Dommages', ['Dommages', 'Dommages Terre', 'Dommages Feu', 'Dommages Eau', 'Dommages Air', 'Dommages Neutre',
    'Dommages Critiques', '% Dommages aux sorts', '% Dommages distance', '% Dommages mêlée']],
  ['Résistances', ['% Résistance Terre', '% Résistance Feu', '% Résistance Eau', '% Résistance Air', '% Résistance Neutre']],
];
const STAT_ELEMENT = {
  Force: 'terre', 'Dommages Terre': 'terre', '% Résistance Terre': 'terre',
  Intelligence: 'feu', 'Dommages Feu': 'feu', '% Résistance Feu': 'feu',
  Chance: 'eau', 'Dommages Eau': 'eau', '% Résistance Eau': 'eau',
  Agilité: 'air', 'Dommages Air': 'air', '% Résistance Air': 'air',
  'Dommages Neutre': 'neutre', '% Résistance Neutre': 'neutre',
};

const $ = (sel, root = document) => root.querySelector(sel);
const fmt = (n) => Math.round(n).toLocaleString('fr-FR');
const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* storage unavailable */ } },
};

let classes = [];
let selectedClass = null;
let report = null;

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined) node.append(child.nodeType ? child : document.createTextNode(child));
  }
  return node;
}

/* ---------- Classes ---------- */
async function loadClasses() {
  const response = await fetch('/api/classes');
  classes = await response.json();
  const list = $('#breeds');
  list.replaceChildren(...classes.map((c) => el('button', {
    type: 'button', class: 'breed', role: 'radio', 'aria-checked': 'false', dataset: { id: c.id },
    onclick: () => selectClass(c.id),
  }, el('img', { src: c.img, alt: '', loading: 'lazy' }), c.nom)));
  selectClass(Number(store.get('classe')) || 1);
}

function selectClass(id) {
  selectedClass = classes.find((c) => c.id === id) || classes[0];
  store.set('classe', selectedClass.id);
  document.querySelectorAll('.breed').forEach((b) => b.setAttribute('aria-checked', String(Number(b.dataset.id) === selectedClass.id)));
  const avatar = $('#avatar-img');
  avatar.src = selectedClass.logo;
  avatar.alt = selectedClass.nom;
  $('#forge').textContent = `Forger un build ${selectedClass.nom}`;
}

/* ---------- Form ---------- */
function readForm() {
  const form = $('#settings');
  const data = new FormData(form);
  return {
    classe: String(selectedClass.id),
    niveau: Number(data.get('niveau')),
    pa: Number(data.get('pa')),
    pm: Number(data.get('pm')),
    parchemins: Number(data.get('parchemins')),
    elements: data.getAll('elements'),
    exos: data.getAll('exos'),
    max_exos: data.getAll('exos').length ? Number(data.get('max_exos')) : null,
    profil: data.get('profil'),
    cible: data.get('cible'),
    top: Number(data.get('top')),
    no_dofus: data.has('no_dofus'),
    no_pet: data.has('no_pet'),
  };
}

async function forge(event) {
  event.preventDefault();
  const button = $('#forge');
  const status = $('#status');
  const overlay = $('#forging');
  const started = Date.now();
  const timer = setInterval(() => { $('#elapsed').textContent = Math.round((Date.now() - started) / 1000); }, 500);
  button.disabled = true;
  overlay.hidden = false;
  status.className = 'status';
  status.textContent = 'Recherche du meilleur stuff pour chaque élément…';
  try {
    const response = await fetch('/api/build', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(readForm()),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.erreur || `Erreur ${response.status}`);
    report = payload;
    if (!report.builds.length) throw new Error('Aucun stuff ne respecte ces contraintes (PA, PM, niveau…).');
    status.textContent = `${report.builds.length} build(s) forgé(s) en ${Math.round((Date.now() - started) / 1000)} s.`;
    renderLadder();
    showBuild(0);
  } catch (error) {
    status.className = 'status error';
    status.textContent = error.message;
  } finally {
    clearInterval(timer);
    overlay.hidden = true;
    button.disabled = false;
  }
}

/* ---------- Results ---------- */
function renderLadder() {
  $('#ladder').replaceChildren(...report.builds.map((b, i) => el('button', {
    type: 'button', class: `c-${b.element}`, 'aria-pressed': 'false', dataset: { index: i },
    onclick: () => showBuild(i),
  }, el('small', {}, `${ELEMENT_NAMES[b.element] || b.element}${b.rang > 1 ? ` #${b.rang}` : ''}`),
  el('strong', {}, fmt(b.degats_par_tour)))));
}

function slotFor(item, used) {
  const type = item.type_id;
  const take = (...names) => names.find((n) => !used.has(n));
  if (type === 16) return take('chapeau');
  if (type === 17) return take('cape');
  if (type === 1) return take('amulette');
  if (type === 10) return take('ceinture');
  if (type === 11) return take('bottes');
  if (type === 9) return take('anneau1', 'anneau2');
  if (type === 82) return take('bouclier');
  if (WEAPONS.has(type)) return take('arme');
  if (PETS.has(type)) return take('familier');
  if (type === 23 || type === 151) return take('dofus1', 'dofus2', 'dofus3', 'dofus4', 'dofus5', 'dofus6');
  return null;
}

function showBuild(index) {
  const build = report.builds[index];
  document.querySelectorAll('#ladder button').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.index) === index)));

  // Inventory
  document.querySelectorAll('.slot').forEach((slot) => {
    slot.className = slot.className.replace(/\bfilled\b/g, '').trim();
    slot.replaceChildren();
    slot.removeAttribute('tabindex');
    slot.onmouseenter = slot.onmouseleave = slot.onfocus = slot.onblur = null;
  });
  const used = new Set();
  for (const item of build.items) {
    const name = slotFor(item, used);
    if (!name) continue;
    used.add(name);
    const slot = $(`.slot[data-slot="${name}"]`);
    slot.classList.add('filled');
    slot.tabIndex = 0;
    slot.setAttribute('aria-label', item.nom);
    slot.append(el('img', { src: item.img, alt: '', loading: 'lazy' }));
    if (item.exo) slot.append(el('span', { class: 'badge' }, `+1 ${item.exo}`));
    if (item.a_verifier.length) slot.append(el('span', { class: 'warn', title: 'Condition à vérifier en jeu' }, '!'));
    bindTooltip(slot, () => itemTooltip(item));
  }

  // Medallion
  $('#damage-total').textContent = fmt(build.degats_par_tour);
  const targets = Object.entries(build.degats_par_cible);
  $('#damage-sub').textContent = targets.length > 1
    ? `pire cas sur ${targets.length} cibles`
    : `${ELEMENT_NAMES[build.element] || build.element}${build.cout != null ? ` · ${fmt(build.cout)} k` : ''}`;

  renderSheet(build);
  renderSpells(build);
}

function renderSheet(build) {
  const rows = [];
  for (const [group, names] of SHEET) {
    const present = names.filter((n) => build.stats[n]);
    if (!present.length) continue;
    rows.push(el('div', { class: 'group' }, group));
    for (const name of present) {
      const element = STAT_ELEMENT[name];
      rows.push(el('dt', { class: element ? `c-${element}` : null }, name), el('dd', {}, fmt(build.stats[name])));
    }
  }
  $('#stats').replaceChildren(...rows);

  const extras = [];
  const points = Object.entries(build.points);
  if (points.length) extras.push(el('p', {}, el('strong', {}, 'Points : '), points.map(([k, v]) => `${k} ${v}`).join(', ')));
  if (build.panoplies.length) {
    extras.push(el('p', {}, el('strong', {}, 'Panoplies : '), build.panoplies.map((p) => `${p.nom} (${p.pieces})`).join(', ')));
  }
  extras.push(el('p', {}, el('strong', {}, 'Conditions : '),
    build.conditions_ok ? 'respectées' : 'NON respectées', ` · ${build.bonus_panoplie_actifs} bonus de panoplie`));
  const targets = Object.entries(build.degats_par_cible);
  if (targets.length > 1) {
    extras.push(el('p', {}, el('strong', {}, 'Par cible : '), targets.map(([k, v]) => `${k} ${fmt(v)}`).join(' · ')));
  }
  $('#extras').replaceChildren(...extras);
}

function renderSpells(build) {
  $('#spellbar').replaceChildren(...build.sorts.map((s) => {
    const node = el('li', { class: `spell ${s.lancers ? 'used' : 'unused'}`, tabindex: '0', 'aria-label': `${s.nom}, ${fmt(s.esperance)} dégâts en moyenne` },
      el('div', { class: 'icon' },
        el('img', { src: s.img, alt: '', loading: 'lazy' }),
        el('span', { class: 'pa' }, String(s.pa)),
        s.lancers ? el('span', { class: 'casts' }, `×${s.lancers}`) : null),
      el('span', { class: 'dmg' }, fmt(s.esperance)),
      el('div', { class: 'el-line' }, s.elements.map((e) => el('span', { class: `el-dot c-${e}` }))),
      el('span', { class: 'name' }, s.nom));
    bindTooltip(node, () => spellTooltip(s));
    return node;
  }));
}

/* ---------- Tooltips ---------- */
function itemTooltip(item) {
  return [
    el('h4', {}, item.nom),
    el('div', { class: 'sub' }, `${item.type} · niveau ${item.niveau}`),
    item.exo ? el('div', { class: 'exo' }, `Exo : +1 ${item.exo}`) : null,
    item.a_verifier.length ? el('div', { class: 'warn' }, `À vérifier en jeu : ${item.a_verifier.join(', ')}`) : null,
  ];
}

function spellTooltip(s) {
  return [
    el('h4', {}, s.nom),
    el('div', { class: 'sub' }, `${s.pa} PA · ${s.elements.map((e) => ELEMENT_NAMES[e]).join(', ')}`),
    el('div', { class: 'line' }, 'Normal', el('b', {}, `${fmt(s.normal[0])} – ${fmt(s.normal[1])}`)),
    el('div', { class: 'line crit' }, `Critique (${s.chance_critique} %)`, el('b', {}, `${fmt(s.critique[0])} – ${fmt(s.critique[1])}`)),
    el('div', { class: 'line' }, 'Espérance par lancer', el('b', {}, fmt(s.esperance))),
    el('div', { class: 'line' }, 'Lancers dans la rotation', el('b', {}, String(s.lancers))),
  ];
}

function bindTooltip(node, content) {
  const tip = $('#tooltip');
  const show = () => {
    tip.replaceChildren(...content().filter(Boolean));
    tip.hidden = false;
    const box = node.getBoundingClientRect();
    const width = tip.offsetWidth;
    const left = Math.min(Math.max(8, box.left + box.width / 2 - width / 2), window.innerWidth - width - 8);
    const above = box.top - tip.offsetHeight - 8;
    tip.style.left = `${left}px`;
    tip.style.top = `${above > 8 ? above : box.bottom + 8}px`;
  };
  const hide = () => { tip.hidden = true; };
  node.onmouseenter = node.onfocus = show;
  node.onmouseleave = node.onblur = hide;
}

/* ---------- Init ---------- */
document.querySelectorAll('.slot').forEach((slot) => { slot.dataset.label = SLOT_LABELS[slot.dataset.slot]; });
document.querySelectorAll('.rune span').forEach((span) => { span.dataset.label = span.textContent; });
$('#niveau').addEventListener('input', (e) => { $('#niveau-out').textContent = e.target.value; });
$('#settings').addEventListener('submit', forge);
loadClasses().catch(() => {
  $('#status').className = 'status error';
  $('#status').textContent = 'Impossible de charger les classes (serveur lancé ?)';
});
