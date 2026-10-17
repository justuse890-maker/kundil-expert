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
let birthMeta = null;       // what the user typed (display only)
let lang = 'en';

// ---- small helpers ---------------------------------------------------------
function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function cap(s) { s = String(s ?? ''); return s.charAt(0).toUpperCase() + s.slice(1); }
function pretty(key) { return String(key ?? '').split('_').map(cap).join(' '); }
function grahaName(key) { return cap(key); }
function rashiName(i1) { return RASHI_NAMES[i1 - 1]; }   // i1 is the API's 1-based rashi
function nakName(i1) { return NAKSHATRAS[i1 - 1]; }

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
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString('en-IN', { year: 'numeric', month: 'short', day: 'numeric' });
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
const PENDING_HTML = '<div class="analysis-pending" data-pending="1">Detailed analysis is being prepared</div>';

function pendingOrError(state) {
  if (state.status === 'error') {
    return `<div class="analysis-pending" data-pending="1">Detailed analysis is unavailable right now (${esc(state.message)})</div>`;
  }
  return PENDING_HTML;
}

function whyText(w) {
  if (w == null) return '';
  if (typeof w === 'string' || typeof w === 'number') return String(w);
  return loc(w, 'text') || loc(w, 'label') || w.fact || w.name || '';
}

function chipsHtml(why, ref) {
  const chips = (Array.isArray(why) ? why : (why ? [why] : [])).map(whyText).filter(Boolean)
    .map(t => `<span class="chip">${esc(t)}</span>`).join('');
  const badge = ref ? `<span class="badge purple" title="Source">📖 ${esc(ref)}</span>` : '';
  return chips || badge ? `<div class="chips">${chips}${badge}</div>` : '';
}

function statementHtml(st, icon) {
  const text = typeof st === 'string' ? st : loc(st, 'text');
  if (!text) return '';
  return `<div class="life-item"><div class="life-item-icon">${icon || '✦'}</div><div class="life-item-content">
    <div class="life-item-desc">${esc(text)}</div>${typeof st === 'object' ? chipsHtml(st.why, st.ref) : ''}</div></div>`;
}

function areaBody(area, icon) {
  if (!area) return '';
  const scoreRow = area.score != null
    ? `<div class="data-row"><span class="data-label">Score</span><span class="data-value">${esc(area.score)}</span></div>` : '';
  const sts = (area.statements || []).map(s => statementHtml(s, icon)).join('');
  return scoreRow + sts;
}

function analysisCardBody(areaKeys, icon) {
  if (analysisState.status !== 'ok') return pendingOrError(analysisState);
  const areas = analysisState.data.areas || {};
  const html = areaKeys.map(k => areaBody(areas[k], icon)).join('');
  return html || PENDING_HTML;
}

function incomeSourcesHtml() {
  if (analysisState.status !== 'ok') return '';
  const src = analysisState.data.income_sources || [];
  if (!src.length) return '';
  return `<p style="font-size:11px;color:var(--maroon);font-weight:600;margin:12px 0 4px">Income sources</p>` + src.map(s => `
    <div class="life-item"><div class="life-item-icon">💰</div><div class="life-item-content">
      <div class="life-item-title">${esc(loc(s, 'label') || pretty(s.type))}${s.score != null ? ` <span class="badge gold">${esc(s.score)}</span>` : ''}</div>
      ${chipsHtml(s.why, s.ref)}</div></div>`).join('');
}

function luckyHtml() {
  if (analysisState.status !== 'ok') return pendingOrError(analysisState);
  const items = analysisState.data.lucky || [];
  if (!items.length) return PENDING_HTML;
  return items.map(it => {
    if (typeof it === 'string') return `<div class="data-row"><span class="data-value">${esc(it)}</span></div>`;
    const label = pretty(it.type || it.kind || '');
    const val = loc(it, 'label') || loc(it, 'text') || loc(it, 'value') || (Array.isArray(it.values) ? it.values.join(', ') : '');
    return `<div class="data-row"><span class="data-label">${esc(label)}</span><span class="data-value">${esc(val)}</span></div>${chipsHtml(it.why, it.ref)}`;
  }).join('');
}

function windowHtml(w, tone) {
  if (!w || typeof w !== 'object') return '';
  const title = loc(w, 'label') || loc(w, 'title') || [w.maha, w.antar].filter(Boolean).map(grahaName).join(' – ') || (w.lord ? grahaName(w.lord) : '');
  const start = w.start_local || w.start_utc, end = w.end_local || w.end_utc;
  const dates = start ? `${localDate(start)}${end ? ' → ' + localDate(end) : ''}` : '';
  const text = loc(w, 'text') || loc(w, 'advice');
  const cls = tone === 'good' ? 'safe' : tone === 'bad' ? 'danger' : 'warning';
  const ind = tone === 'good' ? '🟢' : tone === 'bad' ? '🔴' : '🟡';
  const stmts = Array.isArray(w.statements) ? w.statements.map(s => statementHtml(s)).join('') : '';
  return `<div class="dosha-card ${cls}"><div class="dosha-indicator">${ind}</div><div>
    <div class="dosha-name">${esc(title)}</div>
    <div class="dosha-detail">${esc(dates)}${text ? '<br>' + esc(text) : ''}${stmts}${chipsHtml(w.why, w.ref)}</div></div></div>`;
}

function periodCurrentHtml() {
  if (analysisState.status !== 'ok') return pendingOrError(analysisState);
  const cur = (analysisState.data.periods || {}).current;
  if (!cur || typeof cur !== 'object') return PENDING_HTML;
  let h = '';
  if (cur.maha) h += `<div class="data-row"><span class="data-label">Mahadasha</span><span class="data-value" style="font-size:16px">${esc(grahaName(cur.maha))}</span></div>`;
  if (cur.antar) h += `<div class="data-row"><span class="data-label">Antardasha</span><span class="data-value">${esc(grahaName(cur.antar))}</span></div>`;
  if (cur.end_local || cur.end_utc) h += `<div class="data-row"><span class="data-label">Period Ends</span><span class="data-value">${esc(localDate(cur.end_local || cur.end_utc))}</span></div>`;
  const text = loc(cur, 'text');
  const sts = (cur.statements || []).map(s => statementHtml(s)).join('');
  if (text || sts) h += `<div class="prediction-section"><div class="prediction-title">🔮 Period Effect</div>${text ? `<p class="prediction-text">${esc(text)}</p>` : ''}${sts}</div>`;
  return h || PENDING_HTML;
}

function upcomingHtml() {
  if (analysisState.status !== 'ok') return pendingOrError(analysisState);
  const p = analysisState.data.periods || {};
  const best = (p.best_windows || []).map(w => windowHtml(w, 'good')).join('');
  const hard = (p.challenging_windows || []).map(w => windowHtml(w, 'bad')).join('');
  const rest = best || hard ? '' : (p.timeline || []).map(w => windowHtml(w, 'mid')).join('');
  return (best + hard + rest) || PENDING_HTML;
}

function dailyColourHtml() {
  if (dailyState.status !== 'ok') return pendingOrError(dailyState);
  const d = dailyState.data;
  let h = '';
  if (d.vaar) h += `<div class="data-row"><span class="data-label">Vaar</span><span class="data-value">${esc(VAAR_NAMES[d.vaar] || pretty(d.vaar))}</span></div>`;
  const colour = v => (v && typeof v === 'object') ? loc(v, 'label') || loc(v, 'name') || loc(v, 'colour') : v;
  if (d.colour_today) h += `<div class="life-item"><div class="life-item-icon">🎨</div><div class="life-item-content"><div class="life-item-title">Colour Today</div><div class="life-item-desc">${esc(Array.isArray(d.colour_today) ? d.colour_today.map(colour).join(', ') : colour(d.colour_today))}</div></div></div>`;
  if (d.colour_avoid) h += `<div class="life-item"><div class="life-item-icon">🚫</div><div class="life-item-content"><div class="life-item-title">Avoid</div><div class="life-item-desc">${esc(Array.isArray(d.colour_avoid) ? d.colour_avoid.map(colour).join(', ') : colour(d.colour_avoid))}</div></div></div>`;
  (d.horas || []).forEach(hr => {
    h += `<div class="data-row"><span class="data-label">${esc(grahaName(hr.lord))} hora ${esc(localTime(hr.start_local))}–${esc(localTime(hr.end_local))}</span>
      <span class="data-value"><span class="badge ${hr.favourable ? 'green' : 'amber'}">${esc(loc(hr, 'colour'))}</span></span></div>`;
  });
  (d.body_language || []).forEach(b => { h += statementHtml(b, '🤝'); });
  return h || PENDING_HTML;
}

function decisionsHtml() {
  if (dailyState.status !== 'ok') return pendingOrError(dailyState);
  const ds = dailyState.data.decisions || [];
  if (!ds.length) return PENDING_HTML;
  return ds.map(d => `<div class="life-section"><h4>📌 ${esc(loc(d, 'area') || loc(d, 'title') || pretty(d.type || ''))}</h4>
    <p class="prediction-text">${esc(loc(d, 'text') || loc(d, 'advice'))}</p>${chipsHtml(d.why, d.ref)}</div>`).join('');
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
  const now = Date.now();
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
      <div class="stat-card"><div class="stat-emoji">🌅</div><div class="stat-value" data-testid="lagna">${RASHI_NAMES[lagnaIdx]}</div><div class="stat-label">Ascendant (Lagna)</div></div>
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
        <div class="data-row"><span class="data-label">Tithi</span><span class="data-value">${cap(pc.paksha)} ${tithiLabel(pc.tithi.index)}</span></div>
        <div class="data-row"><span class="data-label">Nakshatra</span><span class="data-value">${nakName(pc.nakshatra.index)} (Pada ${pc.nakshatra.pada})</span></div>
        <div class="data-row"><span class="data-label">Nakshatra Lord</span><span class="data-value">${NAKSHATRA_LORDS[pc.nakshatra.index - 1]}</span></div>
        <div class="data-row"><span class="data-label">Yoga</span><span class="data-value">${YOGAS[pc.yoga.index - 1]}</span></div>
        <div class="data-row"><span class="data-label">Karana</span><span class="data-value">${karanaName(pc.karana.index)}</span></div>
        <div class="data-row"><span class="data-label">Vaar</span><span class="data-value">${esc(VAAR_NAMES[pc.vaar] || pretty(pc.vaar))}</span></div>
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
                  <td>${nakName(g.nakshatra)} P${g.pada}</td>
                  <td style="font-weight:700">${g.house}</td>
                  <td><span class="badge ${DIGNITY_COLOR[g.dignity] || 'gold'}">${DIGNITY_LABEL[g.dignity] || pretty(g.dignity)}</span></td>
                  <td>${g.combust ? '<span class="badge red">🔥 Combust</span>' : ''}${g.vargottama ? '<span class="badge gold">⭐ Vargottama</span>' : ''}</td>
                </tr>`;
              }).join('')}
              <tr style="background:rgba(212,175,55,0.05)">
                <td><span style="color:#7B1F1F;font-weight:700">⬆ Ascendant</span></td>
                <td>${esc(k.lagna.dms)}</td>
                <td>${RASHI_NAMES[lagnaIdx]}</td>
                <td>${nakName(k.lagna.nakshatra)} P${k.lagna.pada}</td>
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
  const housePending = analysisState.status === 'ok' ? '' : pendingOrError(analysisState);
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
                <td style="font-weight:800;font-size:16px;color:var(--maroon)">${b.house}</td>
                <td>${RASHI_SYMBOLS[b.rashi - 1]} ${rashiName(b.rashi)}</td>
                <td style="font-weight:600">${grahaName(b.lord)}</td>
                <td>House ${b.lord_house}</td>
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
          <div><div class="card-title">House ${b.house} — ${rashiName(b.rashi)}</div><div class="card-subtitle">${HOUSE_SIGNIFICATIONS[i].split(',').slice(0, 3).join(',')}</div></div>
        </div>
        <div class="data-row"><span class="data-label">Lord</span><span class="data-value">${grahaName(b.lord)} (in House ${b.lord_house})</span></div>
        <div class="data-row"><span class="data-label">Lord Dignity</span><span class="data-value"><span class="badge ${DIGNITY_COLOR[lordG.dignity] || 'gold'}">${DIGNITY_LABEL[lordG.dignity] || pretty(lordG.dignity)}</span></span></div>
        <div class="data-row"><span class="data-label">Occupants</span><span class="data-value">${b.occupants.length ? b.occupants.map(grahaName).join(', ') : 'None'}</span></div>
        <div class="data-row"><span class="data-label">Aspected By</span><span class="data-value">${b.aspected_by.length ? b.aspected_by.map(grahaName).join(', ') : 'None'}</span></div>
        <div class="data-row"><span class="data-label">Karaka</span><span class="data-value">${b.karakas.map(grahaName).join(' / ')}</span></div>
        <div class="prediction-section">
          <div class="prediction-title">📖 House ${b.house} Reading</div>
          ${housePending || houseReadingHtml(b.house)}
        </div>
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
          <div class="dasha-dates">${localDate(d.start_local)} → ${localDate(d.end_local)} (${yearsBetween(d.start_utc, d.end_utc).toFixed(1)} yrs)</div>
          <div class="dasha-status" style="color:${isActive ? 'var(--emerald)' : isPast ? '#999' : 'var(--gold)'}">${isActive ? '● ACTIVE' : isPast ? 'Past' : 'Upcoming'}</div>
        </div>
        ${isActive && d.children ? `<div style="margin-left:24px;margin-bottom:12px">
          <p style="font-size:11px;color:var(--maroon);font-weight:600;margin:8px 0">Antardasha (Sub-periods):</p>
          ${d.children.map(ad => {
            const adActive = now >= ms(ad.start_utc) && now < ms(ad.end_utc);
            return `<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;font-size:12px;border-radius:8px;margin:4px 0;background:${adActive ? 'rgba(16,185,129,0.08)' : 'transparent'}">
              <span style="width:6px;height:6px;border-radius:50%;background:${adActive ? 'var(--emerald)' : '#ddd'};flex-shrink:0"></span>
              <span style="font-weight:600;min-width:60px">${grahaName(ad.lord)}</span>
              <span style="color:#888;flex:1">${localDate(ad.start_local)} → ${localDate(ad.end_local)}</span>
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

function houseReadingHtml(house) {
  const byHouse = (analysisState.data && analysisState.data.houses) || {};
  const entry = byHouse[house] || byHouse[String(house)];
  if (entry) return (entry.statements || []).map(s => statementHtml(s)).join('') || PENDING_HTML;
  return PENDING_HTML;
}

function doshasHtml(k, now) {
  const mg = k.doshas.manglik;
  const ks = k.doshas.kaal_sarpa;
  const periods = k.doshas.sade_sati || [];
  const activeSS = periods.find(p => now >= ms(p.start_utc) && now < ms(p.end_utc));
  const nextSS = periods.filter(p => ms(p.start_utc) > now).slice(0, 3);
  const mgCls = mg.level === 'none' ? 'safe' : mg.level === 'low' ? 'warning' : 'danger';
  const mgLevelText = cap(mg.level);
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
          <div class="dosha-name">Kaal Sarpa Dosha — ${ks ? cap(ks.kind) + ' (' + cap(ks.name) + ')' : 'Not present'}</div>
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
            ${activeSS ? `Active ${localDate(activeSS.start_local)} → ${localDate(activeSS.end_local)}${ssIsSade ? ". Saturn's 7.5 year transit over natal Moon." : '.'}` : 'Saturn is not currently in a Sade Sati or Dhaiya phase for this chart.'}
            ${nextSS.length ? '<br>Upcoming: ' + nextSS.map(p => `${pretty(p.kind)} (${localDate(p.start_local)} → ${localDate(p.end_local)})`).join('; ') : ''}
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
            ${v} bindus
            <div class="strength-bar" style="width:100px;display:inline-block;margin-left:8px;vertical-align:middle">
              <div class="strength-fill ${v >= 30 ? 'high' : v >= 25 ? 'medium' : 'low'}" style="width:${Math.min(v / 40 * 100, 100)}%"></div>
            </div>
          </span>
        </div>`).join('')}
    </div>
  </div>`;
}

function card(icon, cls, title, body, extra, delay) {
  return `<div class="result-card ${extra || ''}" style="animation-delay:${delay}s">
    <div class="card-header"><div class="card-icon ${cls}">${icon}</div><div><div class="card-title">${title}</div></div></div>
    <div data-analysis="${esc(title)}">${body}</div></div>`;
}

function renderPredictions() {
  if (!kundliData) return;
  const html = `<div class="dashboard-grid">
    ${card('🧬', 'gold', 'Personality & Self', analysisCardBody(['personality'], '🌟'), '', 0.1)}
    ${card('💼', 'emerald', 'Career & Income', analysisCardBody(['career', 'income'], '🎯') + incomeSourcesHtml(), '', 0.2)}
    ${card('💍', 'purple', 'Marriage & Relationships', analysisCardBody(['marriage'], '💑'), '', 0.3)}
    ${card('💎', 'amber', 'Wealth & Finance', analysisCardBody(['wealth'], '📈'), '', 0.4)}
    ${card('❤️', 'emerald', 'Health Analysis', analysisCardBody(['health'], '💪'), '', 0.5)}
    ${card('👶', 'gold', 'Children', analysisCardBody(['children'], '🧸'), '', 0.55)}
    ${card('📚', 'blue', 'Education', analysisCardBody(['education'], '📖'), '', 0.58)}
    ${card('🍀', 'gold', 'Lucky Elements', luckyHtml(), '', 0.6)}
    ${card('🎨', 'blue', 'Color & Body Language Guide', dailyColourHtml(), '', 0.7)}
    <div class="result-card span-2" style="animation-delay:0.8s">
      <div class="card-header">
        <div class="card-icon maroon">🎯</div>
        <div><div class="card-title">Decision Making Guidance</div><div class="card-subtitle">What decisions to take and when based on your current planetary period</div></div>
      </div>
      <div data-analysis="Decision Making Guidance">${decisionsHtml()}</div>
    </div>
    <div class="result-card span-3" style="animation-delay:0.9s">
      <div class="card-header">
        <div class="card-icon purple">🔮</div>
        <div><div class="card-title">Upcoming Life Periods — Best & Challenging Times</div><div class="card-subtitle">Prepare in advance based on planetary periods</div></div>
      </div>
      <div data-analysis="Upcoming Life Periods">${upcomingHtml()}</div>
    </div>
  </div>`;
  document.getElementById('predictionsContent').innerHTML = html;
  const pc = document.getElementById('periodCurrent');
  if (pc) pc.innerHTML = periodCurrentHtml();
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

async function loadSecondary(path, payload, setState) {
  try {
    setState({ status: 'ok', data: await postJson(path, payload) });
  } catch (e) {
    setState(e.status === 501 ? { status: 'pending' } : { status: 'error', message: e.message });
  }
}

function buildPayload() {
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
  if (tz && !document.getElementById('useOffset').checked) {
    payload.tz = tz;
  } else {
    const h = parseFloat(document.getElementById('tz').value);
    const sign = h < 0 ? '-' : '+';
    const mins = Math.round(Math.abs(h) * 60);
    payload.utc_offset = `${sign}${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;
  }
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
  const payload = buildPayload();
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
    renderResults();
    showSection('overview');
    // Interpretation endpoints: rendered independently so the chart never waits on them.
    const secondary = { ...payload };
    Promise.all([
      loadSecondary('/analysis', secondary, s => { analysisState = s; }),
      loadSecondary('/daily', secondary, s => { dailyState = s; }),
    ]).then(rerenderAll);
  } catch (err) {
    showFormError(err.message || 'Something went wrong computing the Kundli.');
  } finally {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('submitBtn').disabled = false;
  }
});

// ---- place search --------------------------------------------------------------
(function placeSearch() {
  const input = document.getElementById('birthPlace');
  const list = document.getElementById('placeList');
  let timer = null, seq = 0, results = [], sel = -1;

  function close() { list.style.display = 'none'; input.setAttribute('aria-expanded', 'false'); sel = -1; }
  function pick(p) {
    input.value = p.admin1 ? `${p.name}, ${p.admin1}, ${p.country}` : `${p.name}, ${p.country}`;
    document.getElementById('lat').value = p.lat;
    document.getElementById('lon').value = p.lon;
    document.getElementById('tzName').value = p.tz;
    close();
  }
  function paint() {
    list.innerHTML = results.map((p, i) =>
      `<li role="option" data-i="${i}" class="${i === sel ? 'sel' : ''}">${esc(p.name)}<small>${esc([p.admin1, p.country].filter(Boolean).join(', '))} • ${esc(p.tz)}</small></li>`).join('');
    list.style.display = results.length ? 'block' : 'none';
    input.setAttribute('aria-expanded', results.length ? 'true' : 'false');
  }

  input.addEventListener('input', () => {
    document.getElementById('tzName').value = '';   // typed text no longer matches the chosen place
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
})();

// ---- birth time unknown + language ------------------------------------------------
document.getElementById('timeUnknown').addEventListener('change', function () {
  const tob = document.getElementById('tob');
  tob.disabled = this.checked;
  tob.required = !this.checked;
});

document.getElementById('langBtn').addEventListener('click', () => {
  lang = lang === 'en' ? 'hi' : 'en';
  document.documentElement.lang = lang;
  rerenderAll();
});
