// ========================================================================
// VEDIC KUNDLI — UI layer. All astronomy and interpretation lives in the
// engine API (/api/v1/*); this file only collects input and renders responses.
// ========================================================================
'use strict';

const API = '/api/v1';

const RASHI_NAMES = ["Mesha","Vrishabha","Mithuna","Karka","Simha","Kanya","Tula","Vrishchika","Dhanu","Makara","Kumbha","Meena"];
const RASHI_SHORT = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];
const RASHI_SYMBOLS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"];
const GRAHA_KEYS = ["sun","moon","mars","mercury","jupiter","venus","saturn","rahu","ketu"];
const GRAHAS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"];
const GRAHA_SYMBOLS = ["☉","☽","♂","☿","♃","♀","♄","☊","☋"];
const GRAHA_COLORS = ["#FF6B00","#C0C0C0","#DC2626","#22C55E","#F59E0B","#EC4899","#6366F1","#8B5CF6","#A78BFA"];
const NAKSHATRAS = ["Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"];
const NAKSHATRA_LORDS = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury","Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury","Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"];
const TITHI_NAMES = ["Pratipada","Dwitiya","Tritiya","Chaturthi","Panchami","Shashthi","Saptami","Ashtami","Navami","Dashami","Ekadashi","Dwadashi","Trayodashi","Chaturdashi"];
const YOGAS = ["Vishkambha","Priti","Ayushman","Saubhagya","Shobhana","Atiganda","Sukarma","Dhriti","Shula","Ganda","Vriddhi","Dhruva","Vyaghata","Harshana","Vajra","Siddhi","Vyatipata","Variyan","Parigha","Shiva","Siddha","Sadhya","Shubha","Shukla","Brahma","Indra","Vaidhriti"];
const KARANA_REPEATING = ["Bava","Balava","Kaulava","Taitila","Gara","Vanija","Vishti"];
const KARANA_FIXED = ["Shakuni","Chatushpada","Naga","Kimstughna"];
const VAAR_NAMES = { ravi: "Sunday", soma: "Monday", mangala: "Tuesday", budha: "Wednesday", guru: "Thursday", shukra: "Friday", shani: "Saturday" };

const HOUSE_SIGNIFICATIONS = [
  "Self, personality, physical body, vitality, fame, complexion, overall health & life path",
  "Wealth, family, speech, food habits, early education, right eye, face, values & savings",
  "Siblings, courage, communication, short travels, right ear, arms, hobbies & mental strength",
  "Mother, home, property, vehicles, happiness, emotions, chest, heart & domestic peace",
  "Children, intelligence, education, creativity, romance, past life merits (poorva punya) & speculation",
  "Enemies, debts, diseases, obstacles, daily work, service, maternal uncle & competitive ability",
  "Marriage, partnerships, business, public image, spouse, foreign travel & legal matters",
  "Longevity, sudden events, inheritance, in-laws, occult, transformation, chronic illness & research",
  "Father, fortune, dharma, higher education, long journeys, guru, philosophy & spiritual growth",
  "Career, profession, status, authority, government, reputation, karma & public recognition",
  "Gains, income, elder siblings, social network, aspirations, ankles & fulfillment of desires",
  "Losses, expenses, moksha, foreign lands, isolation, hospitals, left eye, feet & spiritual liberation"
];

const DIGNITY_LABEL = {
  exalted: 'Exalted', debilitated: 'Debilitated', moolatrikona: 'Moolatrikona', own: 'Own Sign',
  great_friend: 'Great Friend', friend: 'Friend', neutral: 'Neutral', enemy: 'Enemy', great_enemy: 'Great Enemy'
};
const DIGNITY_COLOR = {
  exalted: 'green', moolatrikona: 'green', own: 'blue', great_friend: 'blue', friend: 'blue',
  neutral: 'gold', enemy: 'amber', great_enemy: 'red', debilitated: 'red'
};

let kundliData = null;      // /kundli response
let analysisState = { status: 'idle' };   // idle | ok | pending | error
let dailyState = { status: 'idle' };
let currentPlace = null;    // {label, lat, lon, tz} chosen under Today, else the birth place is used
let todayPlaceText = '';
let birthIana = '';          // IANA zone of the picked birth place (for offset births)
let lastPayload = null;
let birthMeta = null;       // what the user typed (display only)
let lang = 'en';

// ---- small helpers ---------------------------------------------------------
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function cap(s) { s = String(s ?? ''); return s.charAt(0).toUpperCase() + s.slice(1); }
function pretty(key) { return esc(String(key ?? '').split('_').map(cap).join(' ')); }
function grahaName(key) { return esc(cap(key)); }
function rashiName(i1) { return esc(RASHI_NAMES[i1 - 1]); }   // i1 is the API's 1-based rashi
function nakName(i1) { return esc(NAKSHATRAS[i1 - 1]); }

/** Localised text from an object carrying `<base>_en` / `<base>_hi`. */
function loc(obj, base) {
  if (!obj) return '';
  if (lang === 'hi' && obj[base + '_hi']) return obj[base + '_hi'];
  return obj[base + '_en'] ?? obj[base] ?? '';
}

/** Date part of an API `*_local` string, for display only. Instants are always taken from `*_utc`. */
function localDate(s) {
  if (!s) return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  if (!m) return s;
  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${Number(m[3])} ${MON[Number(m[2]) - 1]} ${m[1]}`;
}
function localTime(s) {
  const m = /T(\d{2}:\d{2})/.exec(s || '');
  return m ? m[1] : '';
}
function ms(utc) { return Date.parse(utc); }
function yearsBetween(a, b) { return (ms(b) - ms(a)) / (365.25 * 86400000); }

function karanaName(i) {   // 1..60
  if (i === 1) return KARANA_FIXED[3];
  if (i >= 58) return KARANA_FIXED[i - 58];
  return KARANA_REPEATING[(i - 2) % 7];
}
function tithiLabel(index) {   // 1..30
  const n = index <= 15 ? index : index - 15;
  if (index === 15) return 'Purnima';
  if (index === 30) return 'Amavasya';
  return TITHI_NAMES[n - 1];
}

// ---- navigation ----------------------------------------------------------
function showSection(section) {
  document.querySelectorAll('.section-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('section-' + section).classList.add('active');
  document.querySelectorAll('.nav-btn:not(.lang-btn)').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  const navBtns = document.querySelectorAll('.nav-btn:not(.lang-btn)');
  const tabBtns = document.querySelectorAll('.tab-btn');
  const sectionMap = { input: 0, overview: 1, houses: 2, dasha: 3, doshas: 4, predictions: 5 };
  if (navBtns[sectionMap[section]]) navBtns[sectionMap[section]].classList.add('active');
  const tabMap = { input: 0, overview: 1, houses: 2, dasha: 3, predictions: 4 };
  if (tabBtns[tabMap[section]]) tabBtns[tabMap[section]].classList.add('active');
}

// ---- chart SVG -----------------------------------------------------------
function generateKundliSVG(k) {
  const size = 360;
  const half = size / 2;
  const cellSize = size / 4;
  const grid = [[12, 1, 2, 3], [11, null, null, 4], [10, null, null, 5], [9, 8, 7, 6]];
  const lagnaIdx = k.lagna.rashi - 1;

  let svg = `<svg viewBox="0 0 ${size} ${size}" class="kundli-svg" xmlns="http://www.w3.org/2000/svg">`;
  svg += `<rect x="0" y="0" width="${size}" height="${size}" rx="12" fill="#FFFEF7" stroke="#D4AF37" stroke-width="2"/>`;

  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 4; col++) {
      const houseNum = grid[row][col];
      if (houseNum === null) {
        if (row === 1 && col === 1) {
          svg += `<rect x="${col * cellSize}" y="${row * cellSize}" width="${cellSize * 2}" height="${cellSize * 2}" fill="rgba(123,31,31,0.03)" stroke="none"/>`;
          svg += `<text x="${half}" y="${half - 10}" text-anchor="middle" fill="#7B1F1F" font-family="Cinzel" font-size="20" font-weight="700">🕉️</text>`;
          svg += `<text x="${half}" y="${half + 14}" text-anchor="middle" fill="#7B1F1F" font-family="Cinzel" font-size="11" font-weight="600" data-testid="chart-lagna">${RASHI_NAMES[lagnaIdx]} Lagna</text>`;
          svg += `<text x="${half}" y="${half + 28}" text-anchor="middle" fill="#999" font-size="9">${esc(k.lagna.dms)}</text>`;
        }
        continue;
      }
      const x = col * cellSize;
      const y = row * cellSize;
      const bhava = k.bhavas[houseNum - 1];
      svg += `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="${houseNum === 1 ? 'rgba(123,31,31,0.06)' : 'transparent'}" stroke="#D4AF37" stroke-width="0.5" stroke-opacity="0.4"/>`;
      svg += `<text x="${x + 6}" y="${y + 14}" fill="#7B1F1F" font-size="10" font-weight="700">${houseNum}</text>`;
      svg += `<text x="${x + cellSize - 6}" y="${y + 14}" text-anchor="end" fill="#B8960C" font-size="9">${RASHI_SYMBOLS[bhava.rashi - 1]}</text>`;
      bhava.occupants.forEach((key, pi) => {
        const gi = GRAHA_KEYS.indexOf(key);
        if (gi < 0) return;
        const px = x + 8 + (pi % 3) * 28;
        const py = y + 34 + Math.floor(pi / 3) * 22;
        svg += `<text x="${px}" y="${py}" fill="${GRAHA_COLORS[gi]}" font-size="13" font-weight="600">${GRAHA_SYMBOLS[gi]}</text>`;
        svg += `<text x="${px + 15}" y="${py}" fill="#555" font-size="7">${GRAHAS[gi].slice(0, 2)}</text>`;
      });
    }
  }
  svg += `<line x1="${cellSize}" y1="${cellSize}" x2="${cellSize * 3}" y2="${cellSize * 3}" stroke="#D4AF37" stroke-width="0.5" stroke-opacity="0.3"/>`;
  svg += `<line x1="${cellSize * 3}" y1="${cellSize}" x2="${cellSize}" y2="${cellSize * 3}" stroke="#D4AF37" stroke-width="0.5" stroke-opacity="0.3"/>`;
  return svg + '</svg>';
}

// ---- analysis rendering (contract: /analysis and /daily) ------------------
// Every sentence shown below comes from the API response; this file only lays it out.
// Reasons are id-based: judgements carry ids into periods.reasons, month/window reasons carry
// {source, share} pointers to timeline/transit ids, advice texts live in periods.advice.

// Test determinism only: ?now=<ISO instant> is honoured when the server runs with
// KUNDLI_TEST_HOOKS=1 (GET /api/v1/config reports test_hooks); otherwise it is ignored.
let FORCED_NOW = null;
const configReady = (async () => {
  try {
    const raw = new URLSearchParams(location.search).get('now');
    if (!raw || isNaN(Date.parse(raw))) return;
    const res = await fetch(API + '/config');
    const cfg = res.ok ? await res.json() : null;
    if (cfg && cfg.test_hooks === true) FORCED_NOW = raw;
  } catch (_) { /* no hooks */ }
})();
function nowMs() { return FORCED_NOW ? Date.parse(FORCED_NOW) : Date.now(); }

const AREA_ORDER = [
  ['personality', '🧬', 'gold', 'Personality & Self', '🌟'],
  ['career', '💼', 'emerald', 'Career', '🎯'],
  ['income', '💰', 'gold', 'Income', '💵'],
  ['marriage', '💍', 'purple', 'Marriage & Relationships', '💑'],
  ['health', '❤️', 'emerald', 'Health', '💪'],
  ['wealth', '💎', 'amber', 'Wealth & Finance', '📈'],
  ['children', '👶', 'gold', 'Children', '🧸'],
  ['education', '📚', 'blue', 'Education', '📖'],
];
const NATURE_BADGE = { favourable: 'green', mixed: 'amber', challenging: 'red' };
let selectedMonth = 0;

/** Text from an object carrying `en` / `hi`. */
function enhi(o) { return (lang === 'hi' && o.hi) || o.en || ''; }

function statusHtml(state) {
  if (state.status === 'error') {
    return `<div class="analysis-pending" data-state="error">Analysis is unavailable right now (${esc(state.message)})</div>`;
  }
  if (state.status === 'needplace') {
    return '<div class="analysis-pending" data-state="needplace">Pick where you are today in the Today section to see this.</div>';
  }
  return '<div class="analysis-pending" data-state="loading">Loading…</div>';
}

function chipsHtml(why, ref, detail) {
  const chips = (Array.isArray(why) ? why : (why ? [why] : [])).filter(w => w != null && w !== '')
    .map(t => `<span class="chip">${esc(t)}</span>`).join('');
  const badge = ref ? `<span class="badge purple ref-badge" title="Source">📖 ${esc(ref)}</span>` : '';
  const calc = Array.isArray(detail) && detail.length
    ? `<details class="calc"><summary>Calculation details</summary>${detail.map(d => `<div class="calc-line">${esc(d)}</div>`).join('')}</details>` : '';
  return chips || badge || calc ? `<div class="chips">${chips}${badge}</div>${calc}` : '';
}
function statementHtml(st, icon, extraCls) {
  const text = loc(st, 'text');
  if (!text) return '';
  return `<div class="life-item ${extraCls || ''}"><div class="life-item-icon">${icon || '✦'}</div><div class="life-item-content">
    <div class="life-item-desc">${esc(text)}</div>${chipsHtml(st.why, st.ref, st.detail)}</div></div>`;
}

function natureBadge(nature) {
  return `<span class="badge ${NATURE_BADGE[nature] || 'gold'}">${pretty(nature)}</span>`;
}

function signed(n) { return esc((Number(n) > 0 ? '+' : '') + n); }

function scoreBarHtml(score) {
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  const tone = pct >= 60 ? 'green' : pct >= 40 ? 'amber' : 'red';
  return `<div class="score-row"><div class="score-bar" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${esc(pct)}"><span class="score-fill ${tone}" style="width:${pct}%"></span></div><span class="score-num">${esc(score)}/100</span></div>`;
}

function areaCard(key, icon, cls, title, stIcon, delay) {
  if (analysisState.status !== 'ok') return card(icon, cls, title, statusHtml(analysisState), '', delay, key);
  const a = (analysisState.data.areas || {})[key];
  if (!a) return '';
  const moon = (analysisState.data.meta || {}).lagna_basis === 'moon';
  // Income: the ranked sources below carry the same indications with why and ref, so the
  // per-source statements are not repeated here (a Chandra-kundli note, if any, still is).
  const sts = moreBlock((a.statements || []).map((s, i) => [s, i]).filter(([, i]) => key !== 'income' || (moon && i === 0)).map(([s, i]) =>
    statementHtml(s, stIcon, moon && i === 0 ? 'chandra-note' : '')).filter(Boolean), 2);
  const body = scoreBarHtml(a.score) + (loc(a, 'summary') ? `<p class="area-summary">${esc(loc(a, 'summary'))}</p>` : '') + sts +
    (key === 'income' ? incomeSourcesHtml() : '');
  return card(icon, cls, title, body, '', delay, key);
}
function incomeSourcesHtml() {
  const src = analysisState.data.income_sources || [];
  if (!src.length) return '';
  return `<p class="sub-head">Income sources (ranked)</p><div data-testid="income-sources">` + src.map(s => `
    <div class="life-item"><div class="life-item-icon">${esc(s.rank)}</div><div class="life-item-content">
      <div class="life-item-title">${esc(loc(s, 'label'))} <span class="badge gold">${esc(s.score)}</span> <span class="badge blue">${grahaName(s.planet)}</span></div>
      ${chipsHtml(s.why, s.ref, s.detail)}</div></div>`).join('') + '</div>';
}
function luckyHtml() {
  if (analysisState.status !== 'ok') return statusHtml(analysisState);
  const groups = analysisState.data.lucky || [];
  return groups.map(g => `<div class="lucky-group"><p class="sub-head">${grahaName(g.graha)} <small>(${(g.bases || []).map(pretty).join(', ')})</small></p>` +
    (g.items || []).map(it => `<div class="data-row"><span class="data-label">${pretty(it.kind)}</span>
      <span class="data-value">${esc(loc(it, 'value'))}</span></div>
      <div class="chips"><span class="chip">${esc(loc(it, 'label'))}</span><span class="badge purple ref-badge">📖 ${esc(it.source)}</span></div>`).join('') +
    '</div>').join('');
}
// ---- id resolution ----------------------------------------------------------
function reasonTable() { return ((analysisState.data || {}).periods || {}).reasons || {}; }
function adviceFor(key) {
  const a = (((analysisState.data || {}).periods || {}).advice || {})[key];
  return a ? enhi(a) : '';
}
function sourceIndex() {
  const p = (analysisState.data || {}).periods || {};
  const idx = {};
  (p.timeline || []).forEach(t => { idx[t.id] = { kind: 'timeline', item: t }; });
  (p.transits || []).forEach(t => { idx[t.id] = { kind: 'transit', item: t }; });
  return idx;
}
function lordsTitle(lords) { return (lords || []).map(grahaName).join(' › '); }

/** Top reasons of a judgement: ids -> {text, delta, why, ref} from periods.reasons. */
/** First 3 of `items` visible, the rest behind "Show N more". */
function moreBlock(items, n = 3) {
  const rest = items.slice(n);
  return items.slice(0, n).join('') +
    (rest.length ? `<details class="more"><summary>Show ${rest.length} more</summary>${rest.join('')}</details>` : '');
}

/** Top reasons of a judgement: ids -> {text, delta, why, ref} from periods.reasons. */
function judgementReasonsHtml(j) {
  const table = reasonTable();
  const items = ((j || {}).reasons || []).map(id => table[id]).filter(Boolean).map(r =>
    `<div class="reason"><div class="life-item-desc">${esc(r.text)} <span class="badge ${r.delta >= 0 ? 'green' : 'red'}">${signed(r.delta)}</span></div>
      <details class="why-d"><summary>Why</summary>${chipsHtml(r.why, r.ref, r.detail)}</details></div>`);
  if (!items.length) return '';
  const total = (j || {}).reasons_total || items.length;
  const topNote = total > items.length ? `<p class="top-note" data-testid="top-note">Top ${items.length} of ${esc(total)} reasons</p>` : '';
  return `<div class="reasons">${topNote}${moreBlock(items)}</div>`;
}
function sourceReasonHtml(r, idx) {
  const hit = idx[r.source];
  if (!hit) return '';
  const it = hit.item;
  const share = `<span class="badge gold">${esc(Math.round((r.share || 0) * 100))}%</span>`;
  if (hit.kind === 'transit') {
    return `<div class="reason"><div class="life-item-desc"><b>${grahaName(it.graha)} transit</b> ${share} ${esc(loc(it, 'text'))}</div>
      <details class="why-d"><summary>Why</summary>${chipsHtml(it.why, it.ref, it.detail)}</details></div>`;
  }
  return `<div class="reason"><div class="life-item-desc"><b>${pretty(it.level)} ${lordsTitle(it.lords)}</b> ${natureBadge(it.nature)} ${share}</div>
    <details class="why-d"><summary>Why</summary>${judgementReasonsHtml(it.judgement)}${chipsHtml(it.why, it.ref, it.detail)}</details></div>`;
}
function monthReasonsHtml(m, idx) {
  const items = (m.reasons || []).slice().sort((a, b) => (b.share || 0) - (a.share || 0))
    .map(r => sourceReasonHtml(r, idx)).filter(Boolean);
  const note = items.length > 3 ? `<p class="top-note">Top 3 of ${items.length} sources</p>` : '';
  return note + moreBlock(items);
}
// ---- current period ---------------------------------------------------------
function periodLevelHtml(label, lv) {
  if (!lv) return '';
  const adv = adviceFor('advice.' + lv.judgement.nature);
  return `<details class="period-level" data-level="${esc(label.toLowerCase())}">
    <summary><span class="pl-label">${esc(label)}</span> <b>${grahaName(lv.lord)}</b> ${natureBadge(lv.judgement.nature)} <span class="badge gold">${signed(lv.judgement.score)}</span>
      <span class="pl-dates">${esc(localDate(lv.start_local))} → ${esc(localDate(lv.end_local))}</span></summary>
    ${judgementReasonsHtml(lv.judgement)}
    ${adv ? `<p class="advice">💡 ${esc(adv)}</p>` : ''}</details>`;
}
function periodCurrentHtml() {
  if (analysisState.status !== 'ok') return statusHtml(analysisState);
  const cur = (analysisState.data.periods || {}).current;
  if (!cur) return '';
  return `<p class="period-path" data-testid="period-path">${[cur.maha, cur.antar, cur.pratyantar].filter(Boolean).map(l => grahaName(l.lord)).join(' › ')}</p>` +
    periodLevelHtml('Mahadasha', cur.maha) + periodLevelHtml('Antardasha', cur.antar) + periodLevelHtml('Pratyantar', cur.pratyantar);
}

// ---- 24-month timeline -------------------------------------------------------
function monthLabel(m) {
  const mm = /^(\d{4})-(\d{2})/.exec(m.start_local || '');
  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return mm ? `${MON[Number(mm[2]) - 1]} ${mm[1].slice(2)}` : '';
}

function monthDetailHtml(i) {
  const m = (analysisState.data.periods.months || [])[i];
  if (!m) return '';
  return `<div class="month-detail" data-testid="month-detail">
    <div class="data-row"><span class="data-label">${esc(localDate(m.start_local))} → ${esc(localDate(m.end_local))}</span>
      <span class="data-value">${natureBadge(m.nature)} <span class="badge gold">${signed(m.score)}</span></span></div>
    <div class="dosha-detail">Dasha ${signed(m.dasha_score)} · Transit ${signed(m.transit_score)}</div>
    <div class="reasons">${monthReasonsHtml(m, sourceIndex())}</div></div>`;
}

function windowHtml(w, tone, idx) {
  const cls = tone === 'good' ? 'safe' : 'danger';
  const ind = tone === 'good' ? '🟢' : '🔴';
  return `<div class="dosha-card ${cls}"><div class="dosha-indicator">${ind}</div><div>
    <div class="dosha-name">${esc(localDate(w.start_local))} → ${esc(localDate(w.end_local))} ${natureBadge(w.nature)} <span class="badge gold">${signed(w.score)}</span></div>
    <details class="win-why"><summary>Why</summary>${monthReasonsHtml(w, idx)}</details></div></div>`;
}
function timelineHtml() {
  if (analysisState.status !== 'ok') return statusHtml(analysisState);
  const p = analysisState.data.periods || {};
  const idx = sourceIndex();
  const sn = p.scoring_note;
  const note = sn ? `<p class="scoring-note" data-testid="scoring-note">${esc(enhi(sn))}${sn.ref ? ` <span class="badge purple ref-badge">📖 ${esc(sn.ref)}</span>` : ''}</p>` : '';
  const strip = (p.months || []).map((m, i) =>
    `<button type="button" class="month ${esc(m.nature)}${i === selectedMonth ? ' sel' : ''}" data-i="${i}" data-nature="${esc(m.nature)}" aria-pressed="${i === selectedMonth}" title="${esc(m.nature)} ${esc(m.score)}">${esc(monthLabel(m))}</button>`).join('');
  return `${note}<div class="month-strip" data-testid="month-strip">${strip}</div>
    <div id="monthDetail">${monthDetailHtml(selectedMonth)}</div>
    <p class="sub-head">Best windows</p>${(p.best_windows || []).map(w => windowHtml(w, 'good', idx)).join('')}
    <p class="sub-head">Challenging windows</p>${(p.challenging_windows || []).map(w => windowHtml(w, 'bad', idx)).join('')}`;
}

// ---- today's guidance (/daily) -----------------------------------------------
function horaTableHtml(d) {
  const now = nowMs();
  const horas = d.horas || [];
  let curIdx = horas.findIndex(h => now >= ms(h.start_utc) && now < ms(h.end_utc));
  // Window around the current hora (one before, four after); the rest sits behind "Show all 24".
  const from = curIdx < 0 ? 0 : Math.max(0, Math.min(curIdx - 1, horas.length - 6));
  const rows = horas.map((h, i) => {
    const cur = i === curIdx;
    const flag = h.favourable ? '<span class="badge green">Favourable</span>' : h.avoid ? '<span class="badge red">Avoid</span>' : '<span class="badge gold">Neutral</span>';
    const hidden = i < from || i >= from + 6;
    return `<tr class="${cur ? 'hora-now' : ''}${hidden ? ' hora-extra' : ''}" data-current="${cur}"><td>${esc(h.index)}</td>
      <td>${grahaName(h.lord)}${cur ? ' <span class="badge blue">Now</span>' : ''}</td>
      <td>${esc(localTime(h.start_local))}–${esc(localTime(h.end_local))}</td>
      <td>${flag}<div class="hora-text">${esc(loc(h, 'text'))}</div>
      <details class="why-d"><summary>Why</summary>${chipsHtml(h.why, h.ref, h.detail)}<div class="chips"><span class="chip">${esc(loc(h, 'colour'))}</span></div></details></td></tr>`;
  }).join('');
  return `<div class="table-wrap"><table class="house-table hora-table collapsed" data-testid="hora-table"><thead><tr><th>#</th><th>Hora</th><th>Time</th><th>Guidance</th></tr></thead><tbody>${rows}</tbody></table></div>
    <button type="button" class="link-btn" id="horaToggle" data-testid="hora-toggle">Show all 24</button>`;
}
function placeShort(label) { return String(label || '').split(',')[0].trim(); }
function todayHtml() {
  if (dailyState.status === 'needplace') return `<p class="top-note" data-testid="today-needplace">Your birth time uses a manual UTC offset, so we do not know your time zone today. Pick where you are today above to see today's guidance.</p>`;
  if (dailyState.status !== 'ok') return statusHtml(dailyState);
  const d = dailyState.data;
  const where = placeShort(dailyState.place) || 'your birth place';
  const label = `<h4 class="sub-head" data-testid="today-label">Today at ${esc(where)} (${esc(d.tz)})</h4>`;
  const note = dailyState.beforeSunrise ? `<p class="top-note" data-testid="before-sunrise-note">It is before sunrise at ${esc(where)}, so this is still yesterday's Vedic day (${esc(d.date)}).</p>` : '';
  return `${label}<div class="data-row"><span class="data-label">Vaar</span><span class="data-value" data-testid="vaar">${VAAR_NAMES[d.vaar] ? esc(VAAR_NAMES[d.vaar]) + ' (' + pretty(d.vaar) + ')' : pretty(d.vaar)}</span></div>
    ${note}<div class="dosha-detail">Sunrise ${esc(localTime(d.sunrise_local))} · Sunset ${esc(localTime(d.sunset_local))} · ${esc(d.tz)}</div>
    ${horaTableHtml(d)}`;
}
function colourBlock(c, icon, title) {
  if (!c) return '';
  return `<div class="life-item"><div class="life-item-icon">${icon}</div><div class="life-item-content">
    <div class="life-item-title">${title}: ${esc(loc(c, 'colour'))}</div>
    <div class="life-item-desc">${esc(loc(c, 'text'))}</div>${chipsHtml(c.why, c.ref, c.detail)}</div></div>`;
}
function dailyColourHtml() {
  if (dailyState.status !== 'ok') return statusHtml(dailyState);
  const d = dailyState.data;
  return colourBlock(d.colour_today, '🎨', 'Colour today') + colourBlock(d.colour_avoid, '🚫', 'Colour to avoid') +
    moreBlock((d.body_language || []).map(b => statementHtml(b, '🤝')).filter(Boolean));
}

function decisionsHtml() {
  if (dailyState.status !== 'ok') return statusHtml(dailyState);
  return moreBlock((dailyState.data.decisions || []).map(d => `<div class="life-section"><h4>📌 ${pretty(d.category)} ${natureBadge(d.kind)}</h4>
    <p class="prediction-text">${esc(loc(d, 'text'))}</p><details class="why-d"><summary>Why</summary>${chipsHtml(d.why, d.ref, d.detail)}</details></div>`));
}

function renderHonesty() {
  const src = analysisState.status === 'ok' ? analysisState.data : dailyState.status === 'ok' ? dailyState.data : null;
  if (!src) return;
  const el = document.getElementById('honesty');
  el.textContent = lang === 'hi' ? src.disclaimer_hi : src.disclaimer_en;
}

// ---- render ----------------------------------------------------------------
function renderBanner(k) {
  const timeCodes = ['birth_time_sensitive', 'time_unknown', 'moon_nakshatra_uncertain', 'lagna_is_moon'];
  const ws = k.warnings || [];
  const main = ws.filter(w => timeCodes.includes(w.code));
  const rest = ws.filter(w => !timeCodes.includes(w.code));
  let h = '';
  if (main.length) {
    h += `<div class="sens-banner fade-in" data-testid="sensitivity-banner" role="status"><b>⚠️ Birth-time sensitivity</b><ul>${main.map(w => `<li>${esc(w.message)}</li>`).join('')}</ul></div>`;
  }
  return { banner: h, notes: rest.length ? `<p class="notes-line">Notes: ${rest.map(w => esc(w.message)).join(' • ')}</p>` : '' };
}

function renderResults() {
  if (!kundliData) return;
  const k = kundliData;
  const now = nowMs();
  const m = birthMeta;

  ['navOverview', 'navHouses', 'navDasha', 'navDoshas', 'navPredictions', 'tabOverview', 'tabHouses', 'tabDasha', 'tabPred'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = '';
  });
  document.getElementById('honesty').style.display = '';

  const moon = k.grahas.moon, sun = k.grahas.sun;
  const lagnaIdx = k.lagna.rashi - 1;
  const maha = k.vimshottari;
  const curMaha = maha.find(d => now >= ms(d.start_utc) && now < ms(d.end_utc));
  const curAntar = curMaha ? (curMaha.children || []).find(d => now >= ms(d.start_utc) && now < ms(d.end_utc)) : null;
  const pc = k.panchang;
  const { banner, notes } = renderBanner(k);
  const timeLabel = k.meta.time_known ? localTime(k.meta.birth_local) : 'Unknown';
  const dateLabel = k.meta.birth_local ? k.meta.birth_local.slice(0, 10) : m.dob;

  const overviewHTML = `
    ${banner}
    <div class="quick-stats fade-in">
      <div class="stat-card"><div class="stat-emoji">🌅</div><div class="stat-value" data-testid="lagna">${RASHI_NAMES[lagnaIdx]}</div><div class="stat-label">${k.meta.lagna_basis === 'moon' ? 'Chandra Lagna (Moon)' : 'Ascendant (Lagna)'}</div></div>
      <div class="stat-card"><div class="stat-emoji">☽</div><div class="stat-value">${rashiName(moon.rashi)}</div><div class="stat-label">Moon Sign (Rashi)</div></div>
      <div class="stat-card"><div class="stat-emoji">☉</div><div class="stat-value">${rashiName(sun.rashi)}</div><div class="stat-label">Sun Sign</div></div>
      <div class="stat-card"><div class="stat-emoji">⭐</div><div class="stat-value" data-testid="nakshatra">${nakName(pc.nakshatra.index)}</div><div class="stat-label">Nakshatra</div></div>
      <div class="stat-card"><div class="stat-emoji">🔤</div><div class="stat-value">${esc(k.name_syllable.latin)} <span style="font-size:0.8em">${esc(k.name_syllable.devanagari)}</span></div><div class="stat-label">Name Letter</div></div>
      <div class="stat-card"><div class="stat-emoji">⏳</div><div class="stat-value">${curMaha ? grahaName(curMaha.lord) : 'N/A'}</div><div class="stat-label">Current Mahadasha</div></div>
    </div>

    <div class="dashboard-grid">
      <div class="result-card span-2" style="animation-delay:0.1s">
        <div class="card-header">
          <div class="card-icon gold">🕉️</div>
          <div><div class="card-title">Birth Chart (Kundli)</div><div class="card-subtitle">${esc(m.name)} — ${esc(dateLabel)} ${esc(timeLabel === 'Unknown' ? '' : timeLabel)} — ${esc(m.place)}</div></div>
        </div>
        <div class="kundli-chart-container">${generateKundliSVG(k)}</div>
      </div>

      <div class="result-card" style="animation-delay:0.2s">
        <div class="card-header">
          <div class="card-icon maroon">👤</div>
          <div><div class="card-title">Birth Details</div></div>
        </div>
        <div class="data-row"><span class="data-label">Name</span><span class="data-value">${esc(m.name)}</span></div>
        <div class="data-row"><span class="data-label">Date of Birth</span><span class="data-value">${esc(dateLabel)}</span></div>
        <div class="data-row"><span class="data-label">Time of Birth</span><span class="data-value">${esc(timeLabel)}</span></div>
        <div class="data-row"><span class="data-label">Place</span><span class="data-value">${esc(m.place)}</span></div>
        <div class="data-row"><span class="data-label">Ayanamsa</span><span class="data-value">${esc(k.meta.settings.ayanamsa)} ${k.meta.ayanamsa_deg.toFixed(4)}°</span></div>
        <div class="data-row"><span class="data-label">Lagna Lord</span><span class="data-value">${grahaName(k.bhavas[0].lord)}</span></div>
      </div>

      <div class="result-card" style="animation-delay:0.3s">
        <div class="card-header">
          <div class="card-icon gold">📿</div>
          <div><div class="card-title">Panchang</div><div class="card-subtitle">Five limbs of time</div></div>
        </div>
        <div class="data-row"><span class="data-label">Tithi</span><span class="data-value">${esc(cap(pc.paksha))} ${tithiLabel(pc.tithi.index)}</span></div>
        <div class="data-row"><span class="data-label">Nakshatra</span><span class="data-value">${nakName(pc.nakshatra.index)} (Pada ${esc(pc.nakshatra.pada)})</span></div>
        <div class="data-row"><span class="data-label">Nakshatra Lord</span><span class="data-value">${NAKSHATRA_LORDS[pc.nakshatra.index - 1]}</span></div>
        <div class="data-row"><span class="data-label">Yoga</span><span class="data-value">${YOGAS[pc.yoga.index - 1]}</span></div>
        <div class="data-row"><span class="data-label">Karana</span><span class="data-value">${karanaName(pc.karana.index)}</span></div>
        <div class="data-row"><span class="data-label">Vaar</span><span class="data-value">${VAAR_NAMES[pc.vaar] || pretty(pc.vaar)}</span></div>
        <div class="data-row"><span class="data-label">Name Syllable</span><span class="data-value" style="font-size:16px;font-weight:800">${esc(k.name_syllable.latin)}</span></div>
      </div>

      <div class="result-card span-3" style="animation-delay:0.4s">
        <div class="card-header">
          <div class="card-icon purple">🪐</div>
          <div><div class="card-title">Planetary Positions (Graha Sthiti)</div><div class="card-subtitle">Sidereal longitudes with dignity and status</div></div>
        </div>
        <div style="overflow-x:auto">
          <table class="house-table" data-testid="graha-table">
            <thead><tr><th>Graha</th><th>Longitude</th><th>Rashi</th><th>Nakshatra</th><th>House</th><th>Dignity</th><th>Status</th></tr></thead>
            <tbody>
              ${GRAHA_KEYS.map((key, i) => {
                const g = k.grahas[key];
                return `<tr>
                  <td><span style="color:${GRAHA_COLORS[i]};font-weight:700">${GRAHA_SYMBOLS[i]} ${GRAHAS[i]}${g.retro ? ' ℞' : ''}</span></td>
                  <td>${esc(g.dms)}</td>
                  <td>${rashiName(g.rashi)}</td>
                  <td>${nakName(g.nakshatra)} P${esc(g.pada)}</td>
                  <td style="font-weight:700">${esc(g.house)}</td>
                  <td><span class="badge ${DIGNITY_COLOR[g.dignity] || 'gold'}">${DIGNITY_LABEL[g.dignity] || pretty(g.dignity)}</span></td>
                  <td>${g.combust ? '<span class="badge red">🔥 Combust</span>' : ''}${g.vargottama ? '<span class="badge gold">⭐ Vargottama</span>' : ''}</td>
                </tr>`;
              }).join('')}
              <tr style="background:rgba(212,175,55,0.05)">
                <td><span style="color:#7B1F1F;font-weight:700">${k.meta.lagna_basis === 'moon' ? '⬆ Chandra Lagna' : '⬆ Ascendant'}</span></td>
                <td>${esc(k.lagna.dms)}</td>
                <td>${RASHI_NAMES[lagnaIdx]}</td>
                <td>${nakName(k.lagna.nakshatra)} P${esc(k.lagna.pada)}</td>
                <td style="font-weight:700">1</td>
                <td>—</td>
                <td>—</td>
              </tr>
            </tbody>
          </table>
        </div>
        ${notes}
      </div>
    </div>`;
  document.getElementById('overviewContent').innerHTML = overviewHTML;

  // ---- HOUSES ----
  const housesHTML = `<div class="dashboard-grid">
    <div class="result-card span-3">
      <div class="card-header">
        <div class="card-icon maroon">🏛️</div>
        <div><div class="card-title">Twelve Houses (Bhava Analysis)</div><div class="card-subtitle">Whole-sign house system — Complete analysis of all life areas</div></div>
      </div>
      <div style="overflow-x:auto">
        <table class="house-table">
          <thead><tr><th>House</th><th>Rashi</th><th>Lord</th><th>Lord In</th><th>Occupants</th><th>Karaka</th><th>Signification</th></tr></thead>
          <tbody>
            ${k.bhavas.map((b, i) => `<tr>
                <td style="font-weight:800;font-size:16px;color:var(--maroon)">${esc(b.house)}</td>
                <td>${RASHI_SYMBOLS[b.rashi - 1]} ${rashiName(b.rashi)}</td>
                <td style="font-weight:600">${grahaName(b.lord)}</td>
                <td>House ${esc(b.lord_house)}</td>
                <td>${b.occupants.length ? b.occupants.map(g => `<span class="badge gold" style="margin:2px">${grahaName(g)}</span>`).join('') : '<span style="opacity:0.4">Empty</span>'}</td>
                <td>${b.karakas.map(grahaName).join(' / ')}</td>
                <td style="font-size:11px;max-width:200px;line-height:1.4">${HOUSE_SIGNIFICATIONS[i]}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>

    ${k.bhavas.map((b, i) => {
      const lordG = k.grahas[b.lord];
      return `<div class="result-card" style="animation-delay:${0.1 * i}s">
        <div class="card-header">
          <div class="card-icon ${i < 4 ? 'gold' : i < 8 ? 'maroon' : 'emerald'}">${RASHI_SYMBOLS[b.rashi - 1]}</div>
          <div><div class="card-title">House ${esc(b.house)} — ${rashiName(b.rashi)}</div><div class="card-subtitle">${HOUSE_SIGNIFICATIONS[i].split(',').slice(0, 3).join(',')}</div></div>
        </div>
        <div class="data-row"><span class="data-label">Lord</span><span class="data-value">${grahaName(b.lord)} (in House ${esc(b.lord_house)})</span></div>
        <div class="data-row"><span class="data-label">Lord Dignity</span><span class="data-value"><span class="badge ${DIGNITY_COLOR[lordG.dignity] || 'gold'}">${DIGNITY_LABEL[lordG.dignity] || pretty(lordG.dignity)}</span></span></div>
        <div class="data-row"><span class="data-label">Occupants</span><span class="data-value">${b.occupants.length ? b.occupants.map(grahaName).join(', ') : 'None'}</span></div>
        <div class="data-row"><span class="data-label">Aspected By</span><span class="data-value">${b.aspected_by.length ? b.aspected_by.map(grahaName).join(', ') : 'None'}</span></div>
        <div class="data-row"><span class="data-label">Karaka</span><span class="data-value">${b.karakas.map(grahaName).join(' / ')}</span></div>
      </div>`;
    }).join('')}
  </div>`;
  document.getElementById('housesContent').innerHTML = housesHTML;

  // ---- DASHA ----
  const bal = maha[0];
  const dashaHTML = `<div class="dashboard-grid">
    <div class="result-card span-2" style="animation-delay:0.1s">
      <div class="card-header">
        <div class="card-icon purple">⏳</div>
        <div><div class="card-title">Vimshottari Mahadasha Timeline</div><div class="card-subtitle">120-year planetary period system • Birth Dasha Balance: ${grahaName(bal.lord)} — ${yearsBetween(bal.start_utc, bal.end_utc).toFixed(1)} years remaining</div></div>
      </div>
      ${maha.map((d, idx) => {
        const isActive = now >= ms(d.start_utc) && now < ms(d.end_utc);
        const isPast = ms(d.end_utc) <= now;
        return `<div class="dasha-period ${isActive ? 'active-period' : ''}" data-testid="maha-row" style="opacity:${isPast ? '0.6' : '1'}">
          <div class="dasha-dot" style="background:${isActive ? 'var(--emerald)' : isPast ? '#ccc' : 'var(--gold)'}"></div>
          <div class="dasha-lord">${grahaName(d.lord)}</div>
          <div class="dasha-dates">${esc(localDate(d.start_local))} → ${esc(localDate(d.end_local))} (${yearsBetween(d.start_utc, d.end_utc).toFixed(1)} yrs)</div>
          <div class="dasha-status" style="color:${isActive ? 'var(--emerald)' : isPast ? '#999' : 'var(--gold)'}">${isActive ? '● ACTIVE' : isPast ? 'Past' : 'Upcoming'}</div>
        </div>
        ${isActive && d.children ? `<div style="margin-left:24px;margin-bottom:12px">
          <p style="font-size:11px;color:var(--maroon);font-weight:600;margin:8px 0">Antardasha (Sub-periods):</p>
          ${d.children.map(ad => {
            const adActive = now >= ms(ad.start_utc) && now < ms(ad.end_utc);
            return `<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12px;border-radius:8px;margin:4px 0;background:${adActive ? 'rgba(16,185,129,0.08)' : 'transparent'}">
              <span style="width:6px;height:6px;border-radius:50%;background:${adActive ? 'var(--emerald)' : '#ddd'};flex-shrink:0"></span>
              <span style="font-weight:600;min-width:60px">${grahaName(ad.lord)}</span>
              <span style="color:#888;flex:1">${esc(localDate(ad.start_local))} → ${esc(localDate(ad.end_local))}</span>
              ${adActive ? '<span style="color:var(--emerald);font-weight:700;font-size:10px">● NOW</span>' : ''}
            </div>`;
          }).join('')}
        </div>` : ''}`;
      }).join('')}
    </div>

    <div class="result-card" style="animation-delay:0.2s">
      <div class="card-header">
        <div class="card-icon emerald">🎯</div>
        <div><div class="card-title">Current Period Analysis</div></div>
      </div>
      ${curMaha ? `<div class="data-row"><span class="data-label">Running now</span><span class="data-value">${grahaName(curMaha.lord)}${curAntar ? ' / ' + grahaName(curAntar.lord) : ''}</span></div>` : ''}
      <div id="periodCurrent">${periodCurrentHtml()}</div>
    </div>
  </div>`;
  document.getElementById('dashaContent').innerHTML = dashaHTML;

  // ---- DOSHAS ----
  document.getElementById('doshasContent').innerHTML = doshasHtml(k, now);

  // ---- LIFE ANALYSIS ----
  renderPredictions();
}

function doshasHtml(k, now) {
  const mg = k.doshas.manglik;
  const ks = k.doshas.kaal_sarpa;
  const periods = k.doshas.sade_sati || [];
  const activeSS = periods.find(p => now >= ms(p.start_utc) && now < ms(p.end_utc));
  const nextSS = periods.filter(p => ms(p.start_utc) > now).slice(0, 3);
  const mgCls = mg.level === 'none' ? 'safe' : mg.level === 'low' ? 'warning' : 'danger';
  const mgLevelText = esc(cap(mg.level));
  const yn = v => v == null ? 'n/a' : v ? 'Yes' : 'No';
  const ssIsSade = activeSS && activeSS.kind.startsWith('sade_sati');
  const ssCls = !activeSS ? 'safe' : (activeSS.kind === 'sade_sati_peak' ? 'danger' : 'warning');

  return `<div class="dashboard-grid">
    <div class="result-card span-2" style="animation-delay:0.1s">
      <div class="card-header">
        <div class="card-icon amber">⚠️</div>
        <div><div class="card-title">Dosha Analysis</div><div class="card-subtitle">Comprehensive dosha evaluation for life guidance</div></div>
      </div>
      <div class="dosha-card ${mgCls}">
        <div class="dosha-indicator">${mg.level === 'none' ? '✅' : mg.level === 'low' ? '⚠️' : '🔴'}</div>
        <div>
          <div class="dosha-name">Manglik Dosha — ${mgLevelText}</div>
          <div class="dosha-detail">Mars in houses 1/2/4/7/8/12: From Lagna: ${yn(mg.from_lagna)} | From Moon: ${yn(mg.from_moon)} | From Venus: ${yn(mg.from_venus)}</div>
        </div>
      </div>
      <div class="dosha-card ${!ks ? 'safe' : ks.kind === 'partial' ? 'warning' : 'danger'}">
        <div class="dosha-indicator">${!ks ? '✅' : '🐍'}</div>
        <div>
          <div class="dosha-name">Kaal Sarpa Dosha — ${ks ? esc(cap(ks.kind)) + ' (' + esc(cap(ks.name)) + ')' : 'Not present'}</div>
          <div class="dosha-detail">${ks
            ? `Planets lie between the Rahu-Ketu axis. ${ks.outside.length ? 'Outside: ' + ks.outside.map(grahaName).join(', ') : 'Complete enclosure.'}`
            : 'Planets are distributed on both sides of the Rahu-Ketu axis.'}</div>
        </div>
      </div>
      <div class="dosha-card ${ssCls}">
        <div class="dosha-indicator">${activeSS ? '🪐' : '✅'}</div>
        <div>
          <div class="dosha-name">Sade Sati / Dhaiya — ${activeSS ? pretty(activeSS.kind) : 'Not active now'}</div>
          <div class="dosha-detail">
            ${activeSS ? `Active ${esc(localDate(activeSS.start_local))} → ${esc(localDate(activeSS.end_local))}${ssIsSade ? ". Saturn's 7.5 year transit over natal Moon." : '.'}` : 'Saturn is not currently in a Sade Sati or Dhaiya phase for this chart.'}
            ${nextSS.length ? '<br>Upcoming: ' + nextSS.map(p => `${pretty(p.kind)} (${esc(localDate(p.start_local))} → ${esc(localDate(p.end_local))})`).join('; ') : ''}
          </div>
        </div>
      </div>
    </div>

    <div class="result-card" style="animation-delay:0.2s">
      <div class="card-header">
        <div class="card-icon blue">📊</div>
        <div><div class="card-title">Sarvashtakavarga</div><div class="card-subtitle">Strength per Rashi (total bindus)</div></div>
      </div>
      ${k.ashtakavarga.sav.map((v, i) => `
        <div class="data-row">
          <span class="data-label">${RASHI_SYMBOLS[i]} ${RASHI_SHORT[i]}</span>
          <span class="data-value">
            ${esc(v)} bindus
            <div class="strength-bar" style="width:100px;display:inline-block;margin-left:8px;vertical-align:middle">
              <div class="strength-fill ${v >= 30 ? 'high' : v >= 25 ? 'medium' : 'low'}" style="width:${Math.min(v / 40 * 100, 100)}%"></div>
            </div>
          </span>
        </div>`).join('')}
    </div>
  </div>`;
}

function card(icon, cls, title, body, extra, delay, key) {
  return `<div class="result-card ${extra || ''}" style="animation-delay:${delay}s"${key ? ` data-area="${esc(key)}"` : ''}>
    <div class="card-header"><div class="card-icon ${cls}">${icon}</div><div><div class="card-title">${title}</div></div></div>
    <div data-analysis="${esc(title)}">${body}</div></div>`;
}

function luckyDetails() {
  const n = analysisState.status === 'ok' ? (analysisState.data.lucky || []).length : 0;
  if (!n) return luckyHtml();
  return `<details class="fold" data-testid="lucky"><summary>Colour, gem, day, number, direction, deity and metal (${n} planets)</summary>${luckyHtml()}</details>`;
}

function renderPredictions() {
  if (!kundliData) return;
  const areaCards = AREA_ORDER.map(([key, icon, cls, title, stIcon], i) => areaCard(key, icon, cls, title, stIcon, 0.1 + i * 0.05)).join('');
  const html = `<div class="dashboard-grid">
    <div class="result-card span-3" style="animation-delay:0.05s" data-testid="current-period">
      <div class="card-header"><div class="card-icon emerald">🎯</div><div><div class="card-title">Current Period</div><div class="card-subtitle">Mahadasha › Antardasha › Pratyantar</div></div></div>
      <div data-analysis="Current Period">${periodCurrentHtml()}</div>
    </div>
    ${areaCards}
    ${card('🍀', 'gold', 'Lucky Elements', luckyDetails(), 'span-3', 0.6)}
    <div class="result-card span-3" style="animation-delay:0.7s" data-testid="timeline-card">
      <div class="card-header"><div class="card-icon purple">🔮</div><div><div class="card-title">24-Month Timeline</div><div class="card-subtitle">Tap a month to see why</div></div></div>
      <div data-analysis="Timeline">${timelineHtml()}</div>
    </div>
    <div class="result-card span-3" style="animation-delay:0.8s" data-testid="today-card">
      <div class="card-header"><div class="card-icon amber">🕐</div><div><div class="card-title">Today's Guidance</div><div class="card-subtitle">Vaar and the 24 horas</div></div></div>
      <div class="form-group today-place"><label for="todayPlace">Where are you today? (optional)</label>
        <div class="place-wrap"><input type="text" id="todayPlace" data-testid="today-place" placeholder="Defaults to your birth place" value="${esc(todayPlaceText)}" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="todayPlaceList"><ul class="place-list" id="todayPlaceList" role="listbox" style="display:none"></ul></div></div>
      <div data-analysis="Today">${todayHtml()}</div>
    </div>
    ${card('🎨', 'blue', 'Colour & Body Language', dailyColourHtml(), '', 0.9)}
    ${card('🎯', 'maroon', 'Decision Guidance', decisionsHtml(), '', 1.0)}
  </div>`;
  document.getElementById('predictionsContent').innerHTML = html;
  const pc = document.getElementById('periodCurrent');
  if (pc) pc.innerHTML = periodCurrentHtml();
  wireTodayPlace();
  renderHonesty();
  translateDom(document.body);
}

function rerenderAll() {
  if (!kundliData) return;
  const active = document.querySelector('.section-panel.active');
  renderResults();
  if (active) showSection(active.id.replace('section-', ''));
}

// ---- API ---------------------------------------------------------------------
function formatApiError(status, body) {
  if (body && Array.isArray(body.detail)) {
    return body.detail.map(d => {
      const where = (d.loc || []).filter(x => x !== 'body').join('.');
      return (where ? where + ': ' : '') + d.msg;
    }).join('; ');
  }
  if (body && typeof body.detail === 'string') return body.detail + (body.error_id ? ` (ref ${body.error_id})` : '');
  return `Request failed (HTTP ${status})`;
}

async function postJson(path, payload) {
  let res;
  try {
    res = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  } catch (e) {
    throw Object.assign(new Error('Cannot reach the server. Check your connection and try again.'), { network: true });
  }
  let body = null;
  try { body = await res.json(); } catch (_) { /* non-JSON body */ }
  if (!res.ok) throw Object.assign(new Error(formatApiError(res.status, body)), { status: res.status });
  return body;
}

/** Calendar date (YYYY-MM-DD) of an instant in the chart's own zone (IANA name or fixed offset). */
function chartDate(payload, atMs) {
  try {
    if (payload.tz) {
      return new Intl.DateTimeFormat('en-CA', { timeZone: payload.tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(atMs);
    }
    const m = /^([+-])(\d\d):(\d\d)$/.exec(payload.utc_offset || '');
    if (m) return new Date(atMs + (m[1] === '-' ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3])) * 60000).toISOString().slice(0, 10);
  } catch (_) { /* fall through to the browser's date */ }
  return new Date(atMs).toISOString().slice(0, 10);
}
function previousDate(ymd) {
  const [y, m, d] = ymd.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d - 1)).toISOString().slice(0, 10);
}
/** The place today's guidance is for: the chosen current place, else the birth place. Returns
 * {body, place} (body = current_* fields, {} for the birth place/zone) or null when the birth
 * zone is only a manual offset and no IANA zone is known (the user must pick a place). */
function dailyWhere(payload) {
  if (currentPlace) {
    return { body: { current_lat: currentPlace.lat, current_lon: currentPlace.lon, current_tz: currentPlace.tz }, tz: currentPlace.tz, place: currentPlace.label };
  }
  const place = birthMeta ? birthMeta.place : '';
  if (payload.tz) return { body: {}, tz: payload.tz, place };
  if (birthIana) {
    return { body: { current_lat: payload.lat, current_lon: payload.lon, current_tz: birthIana }, tz: birthIana, place };
  }
  return null;
}
/** Today's guidance for the chosen place; before local sunrise the Vedic day is still yesterday's. */
async function loadDaily(payload, setState) {
  const where = dailyWhere(payload);
  if (!where) { setState({ status: 'needplace' }); return; }
  try {
    const today = chartDate({ tz: where.tz }, nowMs());
    let data = await postJson('/daily', { ...payload, ...where.body, today });
    let beforeSunrise = false;
    if (nowMs() < ms(data.sunrise_utc)) {
      data = await postJson('/daily', { ...payload, ...where.body, today: previousDate(today) });
      beforeSunrise = true;
    }
    setState({ status: 'ok', data, beforeSunrise, place: where.place });
  } catch (e) {
    setState({ status: 'error', message: e.message });
  }
}

async function loadSecondary(path, payload, setState) {
  try {
    setState({ status: 'ok', data: await postJson(path, payload) });
  } catch (e) {
    setState({ status: 'error', message: e.message });
  }
}

let offsetInvalid = false;
function buildPayload() {
  offsetInvalid = false;
  const timeUnknown = document.getElementById('timeUnknown').checked;
  const payload = {
    date: document.getElementById('dob').value,
    lat: parseFloat(document.getElementById('lat').value),
    lon: parseFloat(document.getElementById('lon').value),
    settings: { ayanamsa: document.getElementById('ayanamsa').value },
  };
  const name = document.getElementById('name').value.trim();
  if (name) payload.name = name;
  if (timeUnknown) payload.time_known = false;
  else payload.time = document.getElementById('tob').value;

  const tz = document.getElementById('tzName').value;
  const useOffset = document.getElementById('useOffset').checked;
  if (useOffset) {
    const h = parseFloat(document.getElementById('tz').value);
    if (isNaN(h)) { offsetInvalid = true; return payload; }
    const sign = h < 0 ? '-' : '+';
    const mins = Math.round(Math.abs(h) * 60);
    payload.utc_offset = `${sign}${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
  } else if (tz) {
    payload.tz = tz;
  }   // otherwise no zone key: the caller refuses to submit (no silent default timezone)
  return payload;
}

function showFormError(msg) {
  const el = document.getElementById('formError');
  el.textContent = msg || '';
  el.style.display = msg ? 'block' : 'none';
}

document.getElementById('birthForm').addEventListener('submit', async function (e) {
  e.preventDefault();
  showFormError('');
  await configReady;
  const payload = buildPayload();
  if (offsetInvalid) {
    const adv = document.querySelector('.adv-box');
    if (adv) adv.open = true;
    showFormError('Choose a UTC offset under Advanced, or untick "Use this UTC offset".');
    return;
  }
  if (!payload.tz && !payload.utc_offset) {
    document.getElementById('placeHint').style.display = 'block';
    showFormError('Pick a place from the list, or open Advanced and set a UTC offset.');
    return;
  }
  if (!payload.date || isNaN(payload.lat) || isNaN(payload.lon)) {
    showFormError('Please fill in the date, place and coordinates.');
    return;
  }
  document.getElementById('loading').style.display = 'flex';
  document.getElementById('submitBtn').disabled = true;
  try {
    kundliData = await postJson('/kundli', payload);
    birthMeta = {
      name: document.getElementById('name').value.trim(),
      dob: payload.date,
      place: document.getElementById('birthPlace').value.trim(),
    };
    analysisState = { status: 'idle' };
    dailyState = { status: 'idle' };
    lastPayload = payload;
    currentPlace = null;
    todayPlaceText = '';
    birthIana = document.getElementById('tzName').value || '';
    renderResults();
    showSection('overview');
    // Interpretation endpoints: rendered independently so the chart never waits on them.
    const gender = document.getElementById('gender').value;
    const analysisBody = { ...payload, now_utc: FORCED_NOW || new Date().toISOString() };
    if (gender === 'male' || gender === 'female') analysisBody.gender = gender;
    Promise.all([
      loadSecondary('/analysis', analysisBody, s => { analysisState = s; }),
      loadDaily(payload, s => { dailyState = s; }),
    ]).then(rerenderAll);
  } catch (err) {
    showFormError(err.message || 'Something went wrong computing the Kundli.');
  } finally {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('submitBtn').disabled = false;
  }
});

// ---- place search --------------------------------------------------------------
/** Autocomplete on /places for ``input`` + ``list``; ``onPick(place, text)`` when one is chosen,
 * ``onType()`` whenever the user edits the text. */
function attachPlaceSearch(input, list, onPick, onType) {
  let timer = null, seq = 0, results = [], sel = -1;

  function close() { list.style.display = 'none'; input.setAttribute('aria-expanded', 'false'); sel = -1; }
  function pick(p) {
    const text = p.admin1 ? `${p.name}, ${p.admin1}, ${p.country}` : `${p.name}, ${p.country}`;
    input.value = text;
    close();
    onPick(p, text);
  }
  function paint() {
    list.innerHTML = results.map((p, i) =>
      `<li role="option" data-i="${i}" class="${i === sel ? 'sel' : ''}">${esc(p.name)}<small>${esc([p.admin1, p.country].filter(Boolean).join(', '))} • ${esc(p.tz)}</small></li>`).join('');
    list.style.display = results.length ? 'block' : 'none';
    input.setAttribute('aria-expanded', results.length ? 'true' : 'false');
  }

  input.addEventListener('input', () => {
    onType();
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { results = []; close(); return; }
    timer = setTimeout(async () => {
      const mine = ++seq;
      try {
        const res = await fetch(`${API}/places?q=${encodeURIComponent(q)}`);
        if (!res.ok) throw new Error('places');
        const data = await res.json();
        if (mine !== seq) return;
        results = Array.isArray(data) ? data : [];
        sel = -1;
        paint();
      } catch (_) {
        results = []; close();
      }
    }, 200);
  });
  input.addEventListener('keydown', ev => {
    if (list.style.display === 'none') return;
    if (ev.key === 'ArrowDown') { sel = Math.min(sel + 1, results.length - 1); paint(); ev.preventDefault(); }
    else if (ev.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); paint(); ev.preventDefault(); }
    else if (ev.key === 'Enter' && sel >= 0) { pick(results[sel]); ev.preventDefault(); }
    else if (ev.key === 'Escape') close();
  });
  list.addEventListener('mousedown', ev => {
    const li = ev.target.closest('li');
    if (li) { pick(results[Number(li.dataset.i)]); ev.preventDefault(); }
  });
  document.addEventListener('click', ev => { if (!ev.target.closest('.place-wrap')) close(); });
}

attachPlaceSearch(
  document.getElementById('birthPlace'),
  document.getElementById('placeList'),
  p => {
    document.getElementById('lat').value = p.lat;
    document.getElementById('lon').value = p.lon;
    document.getElementById('tzName').value = p.tz;
    document.getElementById('placeHint').style.display = 'none';
  },
  () => {
    const hadTz = document.getElementById('tzName').value !== '';
    document.getElementById('tzName').value = '';   // typed text no longer matches the chosen place
    if (hadTz) document.getElementById('placeHint').style.display = 'block';
  },
);

/** The Today card is re-created by every render, so its place input is wired again each time. */
async function refreshDaily() {
  if (!lastPayload) return;
  dailyState = { status: 'idle' };
  const holder = document.querySelector('[data-analysis="Today"]');
  if (holder) holder.innerHTML = statusHtml(dailyState);
  await loadDaily(lastPayload, s => { dailyState = s; });
  rerenderAll();
}
function wireTodayPlace() {
  const input = document.getElementById('todayPlace');
  const list = document.getElementById('todayPlaceList');
  if (!input || !list || input.dataset.wired) return;
  input.dataset.wired = '1';
  attachPlaceSearch(input, list, (p, text) => {
    currentPlace = { label: text, lat: p.lat, lon: p.lon, tz: p.tz };
    todayPlaceText = text;
    refreshDaily();
  }, () => {
    todayPlaceText = input.value;
    if (input.value.trim() === '' && currentPlace) { currentPlace = null; refreshDaily(); }
  });
}

// ---- Hindi labels (UI chrome only; analysis text comes from the API as text_hi) -------------
const HI = {
  'Birth Data': 'जन्म विवरण', 'Overview': 'सारांश', 'Houses': 'भाव', 'Dasha': 'दशा', 'Doshas': 'दोष',
  'Life Analysis': 'जीवन विश्लेषण', 'Input': 'इनपुट', 'Chart': 'कुंडली', 'Life': 'जीवन',
  'Enter Birth Details': 'जन्म विवरण दर्ज करें', 'Full Name': 'पूरा नाम', 'Date of Birth': 'जन्म तिथि',
  'Time of Birth': 'जन्म समय', 'Birth time unknown': 'जन्म समय अज्ञात', 'Birth City / Place': 'जन्म स्थान',
  'Gender': 'लिंग', 'Male': 'पुरुष', 'Female': 'महिला', 'Other': 'अन्य', 'Latitude': 'अक्षांश', 'Longitude': 'देशांतर',
  'Timezone': 'समय क्षेत्र', 'Ayanamsa': 'अयनांश',
  'Birth Chart (Kundli)': 'जन्म कुंडली', 'Birth Details': 'जन्म विवरण', 'Panchang': 'पंचांग',
  'Planetary Positions (Graha Sthiti)': 'ग्रह स्थिति', 'Twelve Houses (Bhava Analysis)': 'द्वादश भाव विश्लेषण',
  'Vimshottari Mahadasha Timeline': 'विंशोत्तरी महादशा समयरेखा', 'Current Period Analysis': 'वर्तमान अवधि विश्लेषण',
  'Dosha Analysis': 'दोष विश्लेषण', 'Sarvashtakavarga': 'सर्वाष्टकवर्ग',
  'Current Period': 'वर्तमान अवधि', 'Mahadasha › Antardasha › Pratyantar': 'महादशा › अंतर्दशा › प्रत्यंतर',
  'Mahadasha': 'महादशा', 'Antardasha': 'अंतर्दशा', 'Pratyantar': 'प्रत्यंतर',
  '24-Month Timeline': '24 माह की समयरेखा', 'Tap a month to see why': 'कारण देखने के लिए माह चुनें',
  "Today's Guidance": 'आज का मार्गदर्शन', 'Vaar and the 24 horas': 'वार और 24 होरा',
  'Best windows': 'श्रेष्ठ अवधियाँ', 'Challenging windows': 'कठिन अवधियाँ', 'Why': 'क्यों',
  'Calculation details': 'गणना विवरण', 'Favourable': 'अनुकूल', 'Mixed': 'मिश्रित', 'Challenging': 'कठिन',
  'Avoid': 'बचें', 'Neutral': 'सामान्य', 'Now': 'अभी', 'Lucky Elements': 'शुभ तत्व',
  'Colour & Body Language': 'रंग और हाव-भाव', 'Decision Guidance': 'निर्णय मार्गदर्शन',
  'Personality & Self': 'व्यक्तित्व', 'Career': 'करियर', 'Income': 'आय', 'Marriage & Relationships': 'विवाह व संबंध',
  'Health': 'स्वास्थ्य', 'Wealth & Finance': 'धन व वित्त', 'Children': 'संतान', 'Education': 'शिक्षा',
  'Income sources (ranked)': 'आय के स्रोत (क्रमानुसार)', 'Show all 24': 'सभी 24 दिखाएँ', 'Show fewer': 'कम दिखाएँ',
  'Hora': 'होरा', 'Time': 'समय', 'Guidance': 'मार्गदर्शन', 'Vaar': 'वार', 'Sunrise': 'सूर्योदय', 'Sunset': 'सूर्यास्त',
  'Colour today': 'आज का रंग', 'Colour to avoid': 'बचने का रंग', 'Loading…': 'लोड हो रहा है…',
  'Graha': 'ग्रह', 'Longitude ': 'देशांतर', 'Rashi': 'राशि', 'Nakshatra': 'नक्षत्र', 'House': 'भाव', 'Dignity': 'गरिमा',
  'Status': 'स्थिति', 'Lord': 'स्वामी', 'Lord In': 'स्वामी की स्थिति', 'Occupants': 'स्थित ग्रह', 'Karaka': 'कारक',
  'Signification': 'कारकत्व', 'Chandra Lagna (Moon)': 'चंद्र लग्न (चंद्रमा)', '⬆ Chandra Lagna': '⬆ चंद्र लग्न', 'Running now': 'अभी चल रही', 'Period Ends': 'अवधि समाप्ति',
};
const HI_PATTERNS = [
  [/^Show (\d+) more$/, (m) => `और ${m[1]} दिखाएँ`],
  [/^Top (\d+) of (\d+) reasons$/, (m) => `${m[2]} में से शीर्ष ${m[1]} कारण`],
  [/^Top 3 of (\d+) sources$/, (m) => `${m[1]} में से शीर्ष 3 स्रोत`],
];
function toHindi(text) {
  const m = /^([^A-Za-z0-9(]*)([\s\S]*?)(\s*)$/.exec(text);
  const core = m[2];
  if (!core) return text;
  let out = HI[core];
  if (out === undefined) {
    for (const [re, fn] of HI_PATTERNS) { const x = re.exec(core); if (x) { out = fn(x); break; } }
  }
  if (out === undefined) {   // "Colour today: black" -> translate the head only
    const i = core.indexOf(': ');
    if (i > 0 && HI[core.slice(0, i)]) out = HI[core.slice(0, i)] + core.slice(i);
  }
  return out === undefined ? text : m[1] + out + m[3];
}
/** Switch UI chrome text nodes under `root` to the current language (originals are remembered). */
function translateDom(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: n => (n.parentElement && !n.parentElement.closest('script,style,textarea,#langBtn,[data-api-text]')) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(n => {
    if (n.__en === undefined) n.__en = n.nodeValue;
    const want = lang === 'hi' ? toHindi(n.__en) : n.__en;
    if (n.nodeValue !== want) n.nodeValue = want;
  });
}

// ---- birth time unknown + language ------------------------------------------------
document.getElementById('timeUnknown').addEventListener('change', function () {
  const tob = document.getElementById('tob');
  tob.disabled = this.checked;
  tob.required = !this.checked;
});

document.getElementById('langBtn').addEventListener('click', () => {
  lang = lang === 'en' ? 'hi' : 'en';
  document.getElementById('langBtn').textContent = lang === 'en' ? '🌐 EN' : '🌐 हिं';
  document.documentElement.lang = lang;
  rerenderAll();
  translateDom(document.body);
});

document.getElementById('predictionsContent').addEventListener('click', ev => {
  const tg = ev.target.closest('#horaToggle');
  if (tg) {
    const tbl = document.querySelector('#predictionsContent .hora-table');
    const open = tbl.classList.toggle('collapsed');
    tg.textContent = open ? 'Show all 24' : 'Show fewer';
    translateDom(tg.parentElement);
    return;
  }
  const b = ev.target.closest('button.month');
  if (!b || analysisState.status !== 'ok') return;
  selectedMonth = Number(b.dataset.i);
  document.querySelectorAll('#predictionsContent button.month').forEach(x => {
    const on = x === b;
    x.classList.toggle('sel', on);
    x.setAttribute('aria-pressed', String(on));
  });
  document.getElementById('monthDetail').innerHTML = monthDetailHtml(selectedMonth);
  translateDom(document.getElementById('monthDetail'));
});
