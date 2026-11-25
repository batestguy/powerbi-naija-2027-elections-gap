(() => {
  'use strict';

  const report = JSON.parse(document.getElementById('report-data').textContent);
  const { tables, assets, pages, parameters, soundtrack } = report;
  const parties = tables.dim_party.filter(({ party }) => party !== 'OTHERS');
  const partyByCode = new Map(parties.map(party => [party.party, party]));
  const partyNow = new Map(tables.party_now.map(party => [party.party_2023, party]));
  const turnout = new Map(tables.fact_turnout_2023.map(row => [row.state_pcode, row.total_valid]));
  const votes = new Map(tables.dim_state.map(row => [row.state_pcode, {}]));
  for (const row of tables.fact_result_2023) votes.get(row.state_pcode)[row.party] = row.votes;
  const data = {
    states: tables.dim_state.map(row => ({
      ...row, code: row.state_pcode, name: row.state_name, zoneCode: row.zone_code,
      valid: turnout.get(row.state_pcode), votes: votes.get(row.state_pcode),
    })),
    parties: tables.dim_party,
    coalitionNames: tables.coalition_names,
  };
  const settings = { ...ElectionEngine.defaults, zoneSwings: { ...ElectionEngine.defaults.zoneSwings } };
  const pageKeys = {
    'Candidate overview': 'overview', 'Path to 25': 'path', 'Spread map': 'spread',
    'What-if simulator': 'simulator', 'Merge two parties': 'merge', 'Head to head': 'headToHead',
  };
  const colors = {
    blue: '#0072B2', orange: '#D55E00', gray: '#767676', ink: '#1F1F1F', neutral: '#F2F2F2', white: '#FFFFFF',
  };
  const statusColors = { Secured: colors.blue, 'Within reach': colors.orange, 'Out of reach': colors.gray };
  const leaderColors = { A: colors.blue, B: colors.orange, O: colors.gray, T: colors.gray };
  const number = new Intl.NumberFormat('en-NG', { maximumFractionDigits: 0 });
  const percent = new Intl.NumberFormat('en-NG', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const points = new Intl.NumberFormat('en-NG', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const date = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeZone: 'UTC' });
  const viewport = document.getElementById('viewport');
  const frame = document.getElementById('frame');
  const canvas = document.getElementById('canvas');
  const tabs = document.getElementById('tabs');
  const tabBack = document.getElementById('tab-back');
  const tabNext = document.getElementById('tab-next');
  const tooltip = document.getElementById('tooltip');
  const liveStatus = document.getElementById('status');
  let currentPage;
  let redraw = [];

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content != null) node.textContent = content;
    return node;
  }

  function svgElement(tag, attributes, content) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
    if (content != null) node.textContent = content;
    return node;
  }

  function literal(value) {
    const raw = value?.expr?.Literal?.Value;
    if (raw == null) return undefined;
    if (raw.startsWith("'")) return raw.slice(1, -1).replaceAll("''", "'");
    if (raw === 'false' || raw === 'true') return raw === 'true';
    return Number(raw.replace(/[DL]$/, ''));
  }

  function property(visual, section, key, index = 0) {
    return visual.objects?.[section]?.[index]?.properties?.[key];
  }

  function containerProperty(visual, section, key) {
    return visual.visualContainerObjects?.[section]?.[0]?.properties?.[key];
  }

  function field(expression) {
    return expression?.Measure?.Property ?? expression?.Column?.Property;
  }

  function projections(visual, role) {
    return visual.query?.queryState?.[role]?.projections ?? [];
  }

  function projectionName(projection) {
    return projection.displayName ?? field(projection.field);
  }

  function partyColor() {
    return partyByCode.get(settings.candidate).colour_hex;
  }

  function readColor(expression, fallback) {
    const value = expression?.solid?.color;
    if (field(value?.expr) === 'Party accent colour') return partyColor();
    if (field(value?.expr) === 'Party accent text colour') return contrastingText(partyColor());
    return literal(value) ?? fallback;
  }

  function rgb(hex) {
    return [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
  }

  function contrastingText(hex) {
    const luminance = color => rgb(color).reduce((sum, value, index) => {
      const s = value / 255;
      const linear = s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      return sum + linear * [0.2126, 0.7152, 0.0722][index];
    }, 0) + 0.05;
    const bg = luminance(hex);
    return luminance(colors.white) / bg >= bg / luminance(colors.ink) ? colors.white : colors.ink;
  }

  function spreadColor(row) {
    if (row.pointsFrom25 == null) return colors.neutral;
    const weight = Math.min(Math.abs(row.pointsFrom25) / 25, 1);
    const end = rgb(row.pointsFrom25 < 0 ? colors.orange : colors.blue);
    return '#' + rgb(colors.neutral).map((start, i) =>
      Math.round(start + weight * (end[i] - start)).toString(16).padStart(2, '0')).join('');
  }

  function partyIdentity() {
    const row = partyNow.get(settings.candidate);
    const source = (publisher, day) => `${publisher.split(' (')[0]}, ${date.format(new Date(day))}`;
    const role = row.role ? `, ${row.role}` : '';
    const note = row.note_short ? `. ${row.note_short} (${source(row.note_source_publisher, row.note_date)})` : '';
    return `2023: ${row.party_2023}. Now: ${row.party_now}${role} (${source(row.source_publisher, row.as_of)})${note}`;
  }

  function metric(name, result, row) {
    const national = result?.national;
    const counts = result?.counts;
    const values = {
      'Party identity': partyIdentity,
      'Party badge': () => settings.candidate,
      'Party now badge': () => partyNow.get(settings.candidate).party_now,
      'Candidate votes': () => row?.votes ?? national?.votes,
      'Candidate share': () => row?.share ?? national?.share,
      'Candidate national rank': () => national?.rank,
      'States at 25% or more': () => row?.secured ?? counts?.secured,
      'States with a computable share': () => row?.computable ?? counts?.computable,
      'Closest calls sentence': () => result.closestCalls,
      'Units secured (national)': () => national?.secured,
      'Units needed (rule)': () => national?.unitsNeeded,
      'Units still needed': () => national?.stillNeeded,
      'Clears the rule': () => national?.clears,
      'Tipping-point unit': () => result.tipping?.name,
      'Deciding state sentence': () => result.decidingSentence,
      'Scenario share': () => row?.share,
      'Scenario label': () => row?.status,
      'Baseline label': () => row?.status,
      'Unit rank': () => row?.rank,
      'Points needed': () => row?.pointsNeeded,
      'Votes needed': () => row?.votesNeeded,
      'Points from 25%': () => row?.pointsFrom25,
      'Units secured': () => counts?.secured,
      'Units within reach': () => counts?.withinReach,
      'Units out of reach': () => counts?.outOfReach,
      'Result sentence': () => result.resultSentence,
      'Has most votes': () => national?.mostVotes,
      'Leading rival': () => national?.leadingRival,
      'Scenario national share': () => national?.share,
      'Units at a cap': () => counts?.capped,
      'Assumptions in force': () => result.assumptions,
      'Simulator header line': () => result.headerLine,
      'Simulator coalition sentence': () => result.coalitionSentence,
      'Side A message': () => result.messageA ?? result.message,
      'Side B message': () => result.messageB,
      'Side A states at 25% (merge)': () => national?.secured,
      'Side A lead states at 25%': () => national?.leadSecured,
      'Side A national votes': () => national?.votes,
      'Side A national share (merge)': () => national?.share,
      'Side A share (merge)': () => row?.share,
      'Side A status (merge)': () => row?.status,
      'Side A lead share': () => row?.leadShare,
      'Side A votes': () => row?.votes,
      'Side A change (points)': () => row?.changePoints,
      'Side A national votes (head to head)': () => national?.votes,
      'Side A national share (head to head)': () => national?.share,
      'Side A states at 25% (head to head)': () => national?.secured,
      'States led by Side A': () => national?.aLed,
      'Side B national votes': () => national?.bVotes,
      'Side B national share (head to head)': () => national?.bShare,
      'Side B states at 25% (head to head)': () => national?.bSecured,
      'States led by Side B': () => national?.bLed,
      'Head to head sentence': () => result.resultSentence,
      'Side A share (head to head)': () => row?.share,
      'Side B share (head to head)': () => row?.bShare,
      'Who leads (head to head)': () => row?.leader,
      'Side A at 25% (head to head)': () => row?.aSecured,
      'Side B at 25% (head to head)': () => row?.bSecured,
    };
    if (!Object.hasOwn(values, name)) throw new Error(`Offline measure missing: ${name}`);
    return values[name]();
  }

  function display(value, name) {
    if (value == null) return '—';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value !== 'number') return value;
    if (!name.startsWith('States ') && /\bshare\b/i.test(name)) return percent.format(value);
    if (/points/i.test(name)) return points.format(Object.is(value, -0) ? 0 : value);
    return number.format(value);
  }

  function applyBox(visual, node) {
    const type = visual.visualType;
    if (!['card', 'cardVisual', 'clusteredColumnChart', 'pivotTable', 'shapeMap'].includes(type)) return;
    node.classList.add('box');
    if (literal(containerProperty(visual, 'background', 'show')) === false) node.style.background = 'transparent';
    if (literal(containerProperty(visual, 'border', 'show')) === false) node.style.borderColor = 'transparent';
    const border = readColor(containerProperty(visual, 'border', 'color'));
    if (border) {
      node.style.borderColor = border;
      node.style.borderWidth = `${literal(containerProperty(visual, 'border', 'width')) ?? 1}px`;
    }
    const background = readColor(containerProperty(visual, 'background', 'color'));
    if (background) node.style.backgroundColor = background;
  }

  function buildTextbox(node, visual, title) {
    const paragraphs = property(visual, 'general', 'paragraphs');
    for (const [index, paragraph] of paragraphs.entries()) {
      const firstRun = paragraph.textRuns[0];
      const heading = index === 0 && (title || parseFloat(firstRun.textStyle.fontSize) >= 18);
      const text = element(heading ? 'h1' : 'p');
      if (paragraph.textRuns.every(run => !run.value.trim())) text.style.fontSize = firstRun.textStyle.fontSize;
      for (const run of paragraph.textRuns) {
        const span = element('span', '', run.value);
        span.style.fontSize = run.textStyle.fontSize;
        span.style.color = run.textStyle.color;
        if (run.textStyle.fontFamily.includes('Semibold')) span.style.fontWeight = '600';
        if (/ {2}/.test(run.value) || run.value === ' ') span.style.whiteSpace = 'pre-wrap';
        text.append(span);
      }
      node.append(text);
    }
    if (soundtrack && node.querySelector('h1')?.textContent === 'Data sources') {
      const credit = element('p', 'sound-credit',
        `Soundtrack · “${soundtrack.title}” by ${soundtrack.artist}, from ${soundtrack.album}. ${soundtrack.recordingCredit} `);
      const source = element('a', '', 'Recording credit');
      source.href = soundtrack.creditUrl;
      source.target = '_blank';
      source.rel = 'noopener noreferrer';
      credit.append(source);
      node.append(credit);
    }
  }

  function buildImage(node, visual, alt) {
    const image = element('img');
    const staticName = property(visual, 'image', 'sourceFile')?.image?.url?.expr?.ResourcePackageItem?.ItemName;
    const measure = field(property(visual, 'image', 'sourceUrl')?.expr);
    let name = staticName;
    let label = alt;
    if (measure === 'Candidate photo') {
      name = `candidate_${settings.candidate}.jpg`;
      label = partyByCode.get(settings.candidate).candidate;
    } else if (measure === 'Party logo' || measure === 'Party now logo') {
      const code = measure === 'Party logo' ? settings.candidate : partyNow.get(settings.candidate).party_now;
      name = `logo_${code}`;
      label = `${code} logo`;
    } else if (measure?.startsWith('Side ')) {
      const [, side, group] = /^Side ([AB]) (lead|partner) photo$/.exec(measure);
      const code = settings[`${group}${side}`];
      if (!partyByCode.has(code)) return;
      name = `candidate_${code}.jpg`;
      label = partyByCode.get(code).candidate;
    }
    if (!assets[name]) throw new Error(`Offline report image missing: ${name}`);
    image.src = assets[name];
    image.alt = label ?? '';
    node.append(image);
  }

  function buildCard(node, visual, result) {
    if (visual.visualType === 'card') {
      node.classList.add('classic');
      const name = field(projections(visual, 'Values')[0].field);
      if (name === 'Party identity') node.classList.add('identity');
      const value = metric(name, result);
      const body = element('div', 'card-value', value == null ? '' : display(value, name));
      body.style.fontSize = `${literal(property(visual, 'labels', 'fontSize')) ?? 11}pt`;
      body.style.color = readColor(property(visual, 'labels', 'color'), colors.ink);
      node.append(body);
      return;
    }
    const fields = projections(visual, 'Data');
    const group = element('dl', 'kpis');
    group.style.gridTemplateColumns = `repeat(${fields.length}, minmax(0, 1fr))`;
    for (const projection of fields) {
      const name = field(projection.field);
      const slot = element('div');
      const label = element('dt', '', projectionName(projection));
      label.style.fontSize = `${literal(property(visual, 'label', 'fontSize')) ?? 11}pt`;
      const value = element('dd', '', display(metric(name, result), name));
      value.style.fontSize = `${literal(property(visual, 'value', 'fontSize')) ?? 20}pt`;
      slot.append(label, value);
      group.append(slot);
    }
    node.append(group);
  }

  function settingControl(key) {
    if (key === 'param_turnout') return ['turnout'];
    if (key === 'param_swing_national') return ['nationalSwing'];
    if (key.startsWith('param_swing_')) return ['zoneSwings', key.slice(-2)];
    if (key.startsWith('param_follow_')) return [`follow${key.at(-1).toUpperCase()}`];
    if (key === 'param_rule') return ['rule'];
    if (key === 'coal_switch') return ['coalition'];
    if (key === 'dim_party') return ['candidate'];
    const [, side, role] = /^coal_([ab])_(lead|partner)$/.exec(key);
    return [`${role}${side.toUpperCase()}`];
  }

  function applySetting(key, zone, value) {
    if (zone) settings[key][zone] = value;
    else settings[key] = value;
  }

  function readSavedSettings() {
    const savedTables = new Set();
    for (const page of pages) {
      for (const { visual } of page.visuals) {
        if (visual.visualType !== 'slicer') continue;
        const table = projections(visual, 'Values')[0].field.Column.Expression.SourceRef.Entity;
        if (savedTables.has(table)) continue;
        const condition = property(visual, 'general', 'filter')?.filter?.Where?.[0]?.Condition;
        const initial = literal({ expr: condition?.Comparison?.Right ?? condition?.In?.Values?.[0]?.[0] });
        if (initial == null) continue;
        const [key, zone] = settingControl(table);
        let value = initial;
        if (key === 'candidate') value = parties.find(row => row.candidate === initial)?.party;
        if (table.startsWith('coal_') && table !== 'coal_switch') value = /\(([A-Z]+)\)$/.exec(initial)?.[1] ?? 'NONE';
        if (key === 'coalition') value = initial === 'On';
        if (value != null) applySetting(key, zone, value);
        savedTables.add(table);
      }
    }
  }

  function slider(node, label, range, value, change) {
    const numberInput = element('input');
    const sliderInput = element('input');
    for (const [input, type] of [[numberInput, 'number'], [sliderInput, 'range']]) {
      input.type = type;
      input.min = range.min;
      input.max = range.max;
      input.step = range.step;
      input.value = value;
      input.setAttribute('aria-label', label);
    }
    const showNumber = () => { numberInput.value = sliderInput.valueAsNumber.toFixed(range.step < 1 ? 1 : 0); };
    showNumber();
    const normalize = value => {
      const steps = Math.round((value - range.min) / range.step);
      return Math.max(range.min, Math.min(range.max, range.min + steps * range.step));
    };
    numberInput.addEventListener('input', () => {
      const value = numberInput.valueAsNumber;
      if (!Number.isFinite(value)) return;
      sliderInput.value = normalize(value);
      change(sliderInput.valueAsNumber, false);
    });
    const finishEntry = () => {
      showNumber();
      change(sliderInput.valueAsNumber);
    };
    numberInput.addEventListener('change', finishEntry);
    numberInput.addEventListener('blur', showNumber);
    numberInput.addEventListener('keydown', event => {
      if (event.key === 'Enter') finishEntry();
    });
    sliderInput.addEventListener('input', () => {
      showNumber();
      change(sliderInput.valueAsNumber, false);
    });
    sliderInput.addEventListener('change', () => change(sliderInput.valueAsNumber));
    node.classList.add('slide');
    node.append(numberInput, sliderInput);
  }

  function buildSlicer(node, visual, id) {
    const columns = projections(visual, 'Values');
    const table = columns[0].field.Column.Expression.SourceRef.Entity;
    const [key, zone] = settingControl(table);
    const value = zone ? settings[key][zone] : settings[key];
    const label = literal(property(visual, 'header', 'text'));
    const change = (value, announce = true) => {
      applySetting(key, zone, value);
      renderData(announce);
    };
    if (literal(property(visual, 'data', 'mode')) === 'Single') {
      node.dataset.setting = zone ? `${key}.${zone}` : key;
      if (table.startsWith('param_follow_')) node.classList.add('compact-slide');
      slider(node, label, parameters[table], value, change);
      return;
    }
    const select = element('select');
    select.id = `control-${id}`;
    select.setAttribute('aria-label', label);
    select.dataset.setting = key;
    if (literal(property(visual, 'header', 'show'))) {
      const heading = element('label', '', label);
      heading.htmlFor = select.id;
      node.append(heading);
    }
    let options = parties.map(party => [party.party, key === 'candidate' ? party.candidate : `${party.candidate} (${party.party})`]);
    if (key === 'partnerB') options.push(['NONE', 'Nobody: one party alone']);
    if (key === 'rule') options = [[parameters[table].max, '25'], [parameters[table].min, '24']];
    if (key === 'coalition') options = [['Off', 'Off'], ['On', 'On']];
    for (const [code, text] of options) {
      const option = element('option', '', text);
      option.value = code;
      select.append(option);
    }
    select.value = key === 'coalition' ? (value === true || value === 'On' ? 'On' : 'Off') : value;
    select.addEventListener('change', () => {
      if (key === 'rule') change(Number(select.value));
      else if (key === 'coalition') change(select.value === 'On');
      else change(select.value);
    });
    node.append(select);
  }

  function placeTooltip(x, y) {
    const box = tooltip.getBoundingClientRect();
    tooltip.style.left = `${Math.max(4, Math.min(x + 12, window.innerWidth - box.width - 4))}px`;
    tooltip.style.top = `${Math.max(4, Math.min(y + 12, window.innerHeight - box.height - 4))}px`;
  }

  function addTooltip(node, description, label = description) {
    node.setAttribute('aria-label', label);
    node.addEventListener('pointerenter', event => {
      tooltip.textContent = description;
      tooltip.hidden = false;
      placeTooltip(event.clientX, event.clientY);
    });
    node.addEventListener('pointermove', event => placeTooltip(event.clientX, event.clientY));
    node.addEventListener('pointerleave', () => { tooltip.hidden = true; });
    node.addEventListener('focus', () => {
      const box = node.getBoundingClientRect();
      tooltip.textContent = description;
      tooltip.hidden = false;
      placeTooltip(box.right, box.top);
    });
    node.addEventListener('blur', () => { tooltip.hidden = true; });
    node.addEventListener('keydown', event => {
      if (event.key === 'Escape') tooltip.hidden = true;
    });
  }

  function stateTip(row, headToHead = false) {
    if (row.share == null) return `${row.name}\nNo result for these settings`;
    if (headToHead) return `${row.name}\nSide A: ${display(row.share, 'Share')}\nSide B: ${display(row.bShare, 'Share')}\nWho leads: ${row.leader}`;
    return `${row.name}\nShare of the vote: ${display(row.share, 'Share')}\nStatus: ${row.status}`;
  }

  function emptyVisual(node, result) {
    node.append(element('div', 'empty', result.message || 'No results for these settings.'));
  }

  function buildChart(node, visual, result, position, title) {
    if (!result.ranked.length) return emptyVisual(node, result);
    const value = projections(visual, 'Y')[0];
    const valueName = field(value.field);
    const tooltips = projections(visual, 'Tooltips');
    const fillName = field(property(visual, 'dataPoint', 'fill')?.solid?.color?.expr);
    const width = position.width - 18;
    const height = position.height - 38;
    const left = 34;
    const right = width - 4;
    const top = 7;
    const bottom = height - (width < 900 ? 70 : 76);
    const peak = Math.max(...result.ranked.map(row => metric(valueName, result, row)));
    const ceiling = Math.min(1, Math.max(0.5, Math.ceil(peak * 4) / 4));
    const y = share => bottom - (bottom - top) * share / ceiling;
    const band = (right - left) / result.ranked.length;
    const body = element('div', 'figure');
    const chart = svgElement('svg', { viewBox: `0 0 ${width} ${height}`, role: 'group', 'aria-label': title });
    for (let tick = 0; tick <= ceiling; tick += 0.5) {
      chart.append(svgElement('line', { x1: left, x2: right, y1: y(tick), y2: y(tick), class: 'grid-line' }));
      chart.append(svgElement('text', { x: left - 8, y: y(tick) + 3, 'text-anchor': 'end', 'font-size': 11 }, `${tick * 100}%`));
    }
    for (const [index, row] of result.ranked.entries()) {
      const share = metric(valueName, result, row);
      const x = left + index * band;
      const fill = fillName === 'Path column colour' && row.code === result.tipping?.code
        ? colors.ink : statusColors[row.status];
      const bar = svgElement('rect', {
        x: x + 1, y: y(share), width: band - 3, height: Math.max(1, bottom - y(share)),
        fill, tabindex: '0', 'data-state': row.code,
      });
      const valueText = `${projectionName(value)}: ${display(share, valueName)}`;
      const extra = tooltips.map(({ field: modelField, ...tooltipField }) => {
        const name = field(modelField);
        const label = tooltipField.displayName ?? name;
        return `${label}: ${display(metric(name, result, row), name)}`;
      });
      addTooltip(bar, [row.name, valueText, ...extra].join('\n'));
      const at = x + band / 2;
      chart.append(bar, svgElement('text', {
        x: at, y: bottom + 6, transform: `rotate(-39 ${at} ${bottom + 6})`,
        'text-anchor': 'end', 'font-size': literal(property(visual, 'categoryAxis', 'fontSize')) * 1.25,
        'aria-hidden': 'true',
      }, row.name));
    }
    chart.append(svgElement('line', {
      x1: left, x2: right, y1: y(0.25), y2: y(0.25), class: 'quarter-line', 'stroke-width': 3, 'pointer-events': 'none',
    }));
    chart.append(svgElement('text', {
      x: right - 5, y: y(0.25) - 6, class: 'quarter-label', 'text-anchor': 'end', 'font-size': 12, 'pointer-events': 'none',
    }, literal(property(visual, 'y1AxisReferenceLine', 'displayName'))));
    body.append(chart);
    node.append(body);
  }

  function buildTable(node, visual, result, title) {
    const axes = projections(visual, 'Rows');
    const zoneTable = field(axes[0]?.field) === 'zone';
    const rows = zoneTable ? result.zoneSummary : result.ranked;
    if (!rows.length) return emptyVisual(node, result);
    const columns = projections(visual, 'Values');
    const scroller = element('div', 'matrix-body');
    scroller.setAttribute('tabindex', '0');
    scroller.setAttribute('aria-label', title);
    const table = element('table');
    table.style.fontSize = `${literal(property(visual, 'values', 'fontSize')) ?? 10}pt`;
    const headings = table.createTHead().insertRow();
    for (const projection of [...axes, ...columns]) {
      const heading = element('th', '', projectionName(projection));
      heading.scope = 'col';
      headings.append(heading);
    }
    const body = table.createTBody();
    for (const row of rows) {
      const tr = body.insertRow();
      const heading = element('th', '', row.name);
      heading.scope = 'row';
      tr.append(heading);
      for (const projection of columns) {
        const name = field(projection.field);
        const value = metric(name, result, row);
        tr.append(element('td', typeof value === 'number' ? 'number' : '', display(value, name)));
      }
    }
    scroller.append(table);
    node.append(scroller);
  }

  function buildTiles(node, visual, result, title, position) {
    if (!result.valid) return emptyVisual(node, result);
    const rows = result.rows;
    const rowCount = Math.max(...rows.map(row => row.tileRow)) + 1;
    const columnCount = Math.max(...rows.map(row => row.tileCol)) + 1;
    const headToHead = field(projections(visual, 'Values')[0].field) === 'Head to head tile code';
    const frame = element('div', 'tile-body');
    const grid = element('div', 'tiles');
    grid.setAttribute('role', 'group');
    grid.setAttribute('aria-label', title);
    const size = Math.min((position.width - 32) / columnCount, (position.height - 56) / rowCount);
    grid.style.gridTemplateColumns = `repeat(${columnCount}, ${Math.min((position.width - 32) / columnCount, size * 1.3)}px)`;
    grid.style.gridTemplateRows = `repeat(${rowCount}, ${size}px)`;
    for (const row of rows) {
      const tile = element('span', 'tile', row.stateCode);
      tile.tabIndex = 0;
      tile.dataset.state = row.code;
      tile.style.gridRow = row.tileRow + 1;
      tile.style.gridColumn = row.tileCol + 1;
      const fill = headToHead ? leaderColors[row.leaderCode] ?? colors.neutral : spreadColor(row);
      tile.style.backgroundColor = fill;
      tile.style.color = contrastingText(fill);
      tile.style.fontSize = `${literal(property(visual, 'values', 'fontSize', 1)) ?? 10}pt`;
      addTooltip(tile, stateTip(row, headToHead));
      grid.append(tile);
    }
    frame.append(grid);
    node.append(frame);
  }

  function prepareGeography(topology) {
    const mercator = degrees => -Math.log(Math.tan(Math.PI / 4 + degrees * Math.PI / 360)) * 180 / Math.PI;
    const { scale, translate } = topology.transform;
    const arcs = topology.arcs.map(arc => {
      let x = 0;
      let y = 0;
      return arc.map(([dx, dy]) => {
        x += dx;
        y += dy;
        return [x * scale[0] + translate[0], mercator(y * scale[1] + translate[1])];
      });
    });
    const points = arcs.flat();
    const left = Math.min(...points.map(([x]) => x));
    const top = Math.min(...points.map(([, y]) => y));
    const width = Math.max(...points.map(([x]) => x)) - left;
    const height = Math.max(...points.map(([, y]) => y)) - top;
    const scaleFactor = 100 / Math.max(width, height);
    const paths = Object.values(topology.objects).flatMap(object => object.geometries).map(shape => {
      const rings = shape.type === 'MultiPolygon' ? shape.arcs.flat() : shape.arcs;
      const path = rings.map(ring => {
        const line = ring.flatMap(arc => arc < 0 ? [...arcs[~arc]].reverse() : arcs[arc]);
        const coords = line.map(([x, y]) => `${((x - left) * scaleFactor).toFixed(3)},${((y - top) * scaleFactor).toFixed(3)}`);
        return `M${coords.join(' L')} Z`;
      }).join(' ');
      return [shape.properties.state_pcode, path];
    });
    return { paths: new Map(paths), viewBox: `-1 -1 ${width * scaleFactor + 2} ${height * scaleFactor + 2}` };
  }

  const geography = new Map(Object.entries(report.shapes).map(([name, topology]) => [name, prepareGeography(topology)]));

  function buildMap(node, visual, result, title) {
    const name = literal(property(visual, 'shape', 'map').geoJson.name);
    const map = geography.get(name);
    const body = element('div', 'figure');
    const svg = svgElement('svg', { viewBox: map.viewBox, class: 'geo', role: 'group', 'aria-label': title });
    for (const row of result.rows) {
      const path = svgElement('path', {
        d: map.paths.get(row.code), fill: spreadColor(row), 'fill-rule': 'evenodd',
        'data-state': row.code, tabindex: '0',
      });
      addTooltip(path, stateTip(row));
      svg.append(path);
    }
    body.append(svg);
    node.append(body);
  }

  function buildVisual(node, container, result) {
    const { visual, position, name } = container;
    const type = visual.visualType;
    const title = literal(containerProperty(visual, 'title', 'text'));
    const alt = literal(containerProperty(visual, 'general', 'altText'));
    const scrollPosition = node.querySelector('.matrix-body')?.scrollTop;
    node.replaceChildren();
    applyBox(visual, node);
    if (title) node.append(element('h2', 'visual-title', title));
    if (type === 'textbox') buildTextbox(node, visual, position.y <= 20 && position.x <= 40);
    else if (type === 'image') buildImage(node, visual, alt);
    else if (type === 'card' || type === 'cardVisual') buildCard(node, visual, result);
    else if (type === 'slicer') buildSlicer(node, visual, name);
    else if (type === 'clusteredColumnChart') buildChart(node, visual, result, position, title);
    else if (type === 'shapeMap') buildMap(node, visual, result, title);
    else if (type === 'pivotTable' && projections(visual, 'Columns').length) buildTiles(node, visual, result, title, position);
    else if (type === 'pivotTable') buildTable(node, visual, result, title);
    else throw new Error(`Offline report visual missing: ${type}`);
    if (scrollPosition) {
      const scroller = node.querySelector('.matrix-body');
      if (scroller) scroller.scrollTop = scrollPosition;
    }
  }

  function renderData(announce = false) {
    tooltip.hidden = true;
    const reportPage = pageKeys[currentPage.name];
    const result = ElectionEngine.calculate(data, settings)[reportPage];
    for (const [node, definition] of redraw) buildVisual(node, definition, result);
    if (announce) {
      liveStatus.textContent = result?.resultSentence || result?.message || `${currentPage.name} updated.`;
    }
  }

  function resizeReport() {
    if (!currentPage) return;
    const { width, height } = currentPage;
    const scale = Math.max(0.72, Math.min(viewport.clientWidth / width, viewport.clientHeight / height));
    frame.style.width = `${Math.floor(width * scale)}px`;
    frame.style.height = `${Math.floor(height * scale)}px`;
    canvas.style.transform = `scale(${scale})`;
  }

  function updateTabScroll() {
    tabBack.disabled = tabs.scrollLeft < 1;
    tabNext.disabled = tabs.scrollLeft + tabs.clientWidth >= tabs.scrollWidth - 1;
  }

  function enableSoundtrack() {
    if (!soundtrack) return;
    const audio = document.getElementById('soundtrack');
    const toggle = document.getElementById('sound-toggle');
    toggle.title = `“${soundtrack.title}” by ${soundtrack.artist}`;
    toggle.hidden = false;
    const showState = () => {
      const playing = !audio.paused && !audio.error;
      toggle.setAttribute('aria-pressed', String(playing));
      toggle.textContent = playing ? 'Sound on' : 'Sound off';
    };
    audio.addEventListener('play', showState);
    audio.addEventListener('pause', showState);
    toggle.addEventListener('click', async () => {
      if (!audio.paused) {
        audio.pause();
        showState();
        return;
      }
      if (!audio.hasAttribute('src')) audio.src = soundtrack.audio;
      try {
        await audio.play();
      } catch (error) {
        showState();
        if (error.name !== 'AbortError') liveStatus.textContent = 'The browser could not play the soundtrack.';
      }
    });
  }

  function showPage(page) {
    currentPage = page;
    frame.setAttribute('aria-labelledby', `tab-${page.id}`);
    canvas.style.width = `${page.width}px`;
    canvas.style.height = `${page.height}px`;
    canvas.classList.toggle('source-page', page.name === 'Data sources');
    canvas.replaceChildren();
    redraw = [];
    for (const definition of page.visuals) {
      if (definition.isHidden) continue;
      const { position, visual } = definition;
      const type = visual.visualType;
      const node = element('section', `visual ${type}`);
      node.dataset.visual = definition.name;
      Object.assign(node.style, {
        left: `${position.x}px`, top: `${position.y}px`, width: `${position.width}px`, height: `${position.height}px`,
        zIndex: position.z,
      });
      if (type === 'textbox' || type === 'slicer' ||
          (type === 'image' && property(visual, 'image', 'sourceFile'))) buildVisual(node, definition);
      else redraw.push([node, definition]);
      canvas.append(node);
    }
    renderData();
    viewport.scrollTo(0, 0);
    resizeReport();
    for (const button of tabs.children) {
      const active = button.id === `tab-${page.id}`;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      if (active) button.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
    updateTabScroll();
  }

  for (const [index, page] of pages.entries()) {
    const button = element('button', '', page.name);
    button.type = 'button';
    button.id = `tab-${page.id}`;
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-controls', frame.id);
    button.addEventListener('click', () => showPage(page));
    button.addEventListener('keydown', event => {
      const keys = { ArrowLeft: (index + pages.length - 1) % pages.length, ArrowRight: (index + 1) % pages.length,
        Home: 0, End: pages.length - 1 };
      if (!Object.hasOwn(keys, event.key)) return;
      event.preventDefault();
      const next = keys[event.key];
      showPage(pages[next]);
      tabs.children[next].focus();
    });
    tabs.append(button);
  }
  tabBack.addEventListener('click', () => tabs.scrollBy({ left: -0.75 * tabs.clientWidth }));
  tabNext.addEventListener('click', () => tabs.scrollBy({ left: 0.75 * tabs.clientWidth }));
  tabs.addEventListener('scroll', updateTabScroll);
  viewport.addEventListener('scroll', () => { tooltip.hidden = true; });
  window.addEventListener('resize', () => { resizeReport(); updateTabScroll(); });
  readSavedSettings();
  enableSoundtrack();
  showPage(pages.find(page => page.id === report.activePageId) ?? pages[0]);
})();
