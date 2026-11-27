/* The offline calculations mirror docs/methodology.md and scenario.tmdl. */
globalThis.ElectionEngine = (() => {
  'use strict';

  const parties = Object.freeze(['APC', 'PDP', 'LP', 'NNPP']);
  const candidates = Object.freeze({
    APC: 'Bola Tinubu', PDP: 'Atiku Abubakar', LP: 'Peter Obi', NNPP: 'Rabiu Kwankwaso',
  });
  const zones = Object.freeze({
    NC: 'North Central and Abuja', NE: 'North East', NW: 'North West',
    SE: 'South East', SS: 'South South', SW: 'South West',
  });
  const defaults = Object.freeze({
    candidate: 'APC', turnout: 0, nationalSwing: 0,
    zoneSwings: Object.freeze({NC: 0, NE: 0, NW: 0, SE: 0, SS: 0, SW: 0}),
    rule: 25, coalition: false, leadA: 'LP', partnerA: 'NNPP', followA: 100,
    leadB: 'APC', partnerB: 'NONE', followB: 100, comebackA: 100, comebackB: 100, zone: '', state: '',
  });
  const swingRange = Object.freeze({min: -20, max: 20, step: 0.5});
  const ranges = Object.freeze({
    turnout: Object.freeze({min: -50, max: 50, step: 1}), nationalSwing: swingRange, zoneSwing: swingRange,
    follow: Object.freeze({min: 0, max: 100, step: 5}), comeback: Object.freeze({min: 0, max: 100, step: 5}), rule: Object.freeze([25, 24]),
  });
  const status = Object.freeze({secured: 'Secured', within: 'Within reach', out: 'Out of reach'});
  const scenarioMargin = 1e-12;
  const number = new Intl.NumberFormat('en-US');
  const compare = (a, b) => (a < b ? -1 : Number(a > b));
  const sum = (rows, get) => rows.reduce((total, row) => total + (get(row) ?? 0), 0);
  const ratio = (top, bottom) => bottom > 0 ? top / bottom : null;
  const value = entry => entry == null || entry === '' || !Number.isFinite(Number(entry)) ? null : Number(entry);
  const vote = (row, party) => value(row.partyVotes[party]);
  const signed = (val, places) => `${val > 0 ? '+' : ''}${val.toFixed(places)}`;

  function normalizeStates(states) {
    return states.map(({votes, ...row}) => ({
      ...row,
      code: row.code ?? row.state_pcode,
      name: row.name ?? row.state_name,
      zoneCode: row.zoneCode ?? row.zone_code,
      stateCode: row.stateCode ?? row.state_code,
      tileRow: value(row.tileRow ?? row.tile_row),
      tileCol: value(row.tileCol ?? row.tile_col),
      baseValid: value(row.valid ?? row.total_valid),
      partyVotes: votes ?? row.partyVotes ?? {},
    }));
  }

  function candidateNames(source) {
    const entries = Array.isArray(source) ? source.map(row => [row.party, row]) : Object.entries(source ?? {});
    const names = {...candidates};
    for (const [party, row] of entries) names[party] = row?.candidate ?? row?.name ?? names[party];
    return names;
  }

  function partyLabel(party, names) {
    return `${names[party]} (${party})`;
  }

  function coalitionInfo(lead, partner, names, source) {
    if (partner === 'NONE') return {name: partyLabel(lead, names)};
    const row = Array.isArray(source)
      ? source.find(item => item.lead === lead && item.partner === partner)
      : source?.[`${lead}+${partner}`];
    const isNdc = lead === 'LP' && partner === 'NNPP';
    return {
      name: row?.display_name ?? row?.displayName ?? (isNdc ? 'NDC (Obi + Kwankwaso)' : `${lead} + ${partner} (what-if)`),
      real: row?.status ? row.status === 'real' : isNdc,
      source: row?.source_label ?? (isNdc ? 'Nigeria Democratic Congress, 31 May 2026' : row?.source_publisher),
    };
  }

  function coalitionMessage(lead, partner, follow, names, info, comeback = 100) {
    if (partner === 'NONE') return comeback === 100 ? `${info.name} alone, with all of their 2023 votes.`
      : `${info.name} alone, ${comeback}% of their 2023 voters come back; the rest stay home.`;
    const description = info.real ? `A real joint ticket (${info.source}).` : 'A what-if pairing: no such joint ticket exists.';
    return `${info.name}: ${partyLabel(lead, names)} leads, ${partyLabel(partner, names)} is the partner. ${description} ${follow}% of ${names[partner]}'s 2023 voters follow.`;
  }

  function coalitionSelection(s, names, source) {
    const {leadA, partnerA, followA, leadB, partnerB, followB} = s;
    let errorA = '';
    let errorB = '';
    if (!parties.includes(leadA)) errorA = "Choose Side A's lead party (top of the ticket).";
    else if (!parties.includes(partnerA)) errorA = "Choose Side A's partner party.";
    else if (leadA === partnerA) errorA = "Side A's lead and partner are the same party: choose two different parties.";
    if (!parties.includes(leadB)) errorB = "Choose Side B's main party.";
    else if (partnerB !== 'NONE' && !parties.includes(partnerB)) errorB = "Choose Side B's partner, or Nobody.";
    else if ([leadA, partnerA].includes(leadB)) errorB = `${leadB} is already on Side A: choose another party for Side B.`;
    else if (leadB === partnerB) errorB = "Side B's main party and partner are the same: choose two different parties, or Nobody.";
    else if ([leadA, partnerA].includes(partnerB)) errorB = `${partnerB} is already on Side A: choose another partner for Side B, or Nobody.`;

    const infoA = errorA ? null : coalitionInfo(leadA, partnerA, names, source);
    const infoB = errorB ? null : coalitionInfo(leadB, partnerB, names, source);
    return {
      validA: !errorA, validBoth: !errorA && !errorB, error: errorA || errorB,
      nameA: infoA?.name ?? null, nameB: errorA ? null : (infoB?.name ?? null),
      messageA: errorA || coalitionMessage(leadA, partnerA, followA, names, infoA),
      messageB: errorB || coalitionMessage(leadB, partnerB, followB, names, infoB, s.comebackB),
    };
  }

  // v1.1: the simulator names its rival under the candidate's party today (party_now.csv; rename only)
  function nowLabel(code, names, now) {
    const r = now?.find(row => row.party_2023 === code);
    if (!r || r.party_now === code) return partyLabel(code, names);
    return `${r.candidate} — ${r.party_now} now${r.role ? `, ${r.role}` : ''} (${code} in 2023${r.note_short ? `; ${r.note_short}` : ''})`;
  }

  function nowShort(code, now) {
    const r = now?.find(row => row.party_2023 === code);
    if (!r) return code;
    return `${r.candidate.split(' ').at(-1)} (${r.party_now})`;   // card label says "party now"
  }

  function entities(s, useCoalition, names, selected, now = null) {
    const used = useCoalition ? [s.leadA, s.partnerA, s.leadB, s.partnerB] : [s.candidate];
    const rivals = parties.filter(party => !used.includes(party))
      .map(code => ({code, label: code, name: now ? nowLabel(code, names, now) : partyLabel(code, names)}));
    if (useCoalition) rivals.push({
      code: s.leadB, label: s.partnerB === 'NONE' ? s.leadB : `${s.leadB}+${s.partnerB}`,
      name: selected.nameB,
    });
    return rivals;
  }

  // comeback (v1.1, Head to head only): % of each lead party's 2023 voters who vote for that side again
  function coalitionVotes(row, s, both, comeback = false) {
    const ra = comeback ? s.comebackA : 100;
    const rb = comeback ? s.comebackB : 100;
    const leadA = vote(row, s.leadA);
    const partnerA = vote(row, s.partnerA);
    const leadB = both ? vote(row, s.leadB) : 0;
    const partnerB = both && s.partnerB !== 'NONE' ? vote(row, s.partnerB) : 0;
    if ([row.baseValid, leadA, partnerA, leadB, partnerB].includes(null)) return null;
    // Integer vote hundredths preserve exact threshold and lead comparisons.
    return {
      a: ra * leadA + s.followA * partnerA,
      b: rb * leadB + s.followB * partnerB,
      valid: 100 * row.baseValid - (100 - ra) * leadA - (100 - s.followA) * partnerA
        - (100 - rb) * leadB - (100 - s.followB) * partnerB,
    };
  }

  function emptyRow(row) {
    return {
      ...row, baseVotes: null, validVotes: null, votes: null, share: null, status: null,
      pointsFrom25: null, pointsNeeded: null, votesNeeded: null, votesToSpare: null,
      capped: null, rank: null,
    };
  }

  function metrics(row, baseVotes, validVotes, votes, share, rawShare, exactStatus, quarterVoteGap = validVotes / 4 - votes) {
    const label = exactStatus ?? (share >= 0.25 - scenarioMargin ? status.secured
      : share >= 0.20 - scenarioMargin ? status.within : status.out);
    const gap = (share - 0.25) * 100;
    return {
      ...row, baseVotes, validVotes, votes, share, rawShare, status: label,
      pointsFrom25: gap, pointsNeeded: Math.max(0, -gap),
      votesNeeded: label === status.secured ? 0 : Math.ceil(Math.max(0, quarterVoteGap)),
      votesToSpare: Math.floor(Math.max(0, -quarterVoteGap) + 1e-6),
      capped: rawShare <= 0 || rawShare >= 1, rank: null,
    };
  }

  function exactLabel(votes, valid) {
    return 4 * votes >= valid ? status.secured : 5 * votes >= valid ? status.within : status.out;
  }

  function baselineRow(row, party) {
    const votes = vote(row, party);
    if (votes === null || !(row.baseValid > 0)) return emptyRow(row);
    const share = votes / row.baseValid;
    return metrics(row, votes, row.baseValid, votes, share, share, exactLabel(votes, row.baseValid));
  }

  function scenarioRow(row, s, rivals) {
    const coalition = s.coalition ? coalitionVotes(row, s, true) : null;
    const candidate = s.coalition ? coalition?.a / 100 : vote(row, s.candidate);
    const valid = s.coalition ? coalition?.valid / 100 : row.baseValid;
    if (!Number.isFinite(candidate) || !(valid > 0)) return emptyRow(row);
    const turnout = s.turnout / 100;
    const validVotes = valid + candidate * turnout;
    const shareAfterTurnout = candidate * (1 + turnout) / validVotes;
    const swing = s.nationalSwing + (s.zoneSwings[row.zoneCode] ?? 0);
    const rawShare = shareAfterTurnout + swing / 100;
    const share = Math.min(1, Math.max(0, rawShare));
    const scale = shareAfterTurnout < 1 ? (1 - share) / (1 - shareAfterTurnout) : 0;
    const rivalVotes = Object.fromEntries([...rivals, {code: 'OTHERS'}].map(({code}) => {
      const base = s.coalition && code === s.leadB ? coalition.b / 100 : vote(row, code);
      return [code, base === null ? null : base * scale];
    }));
    // Turnout is in whole percent and swing in half points. Keep their vote gap exact
    // until rounding so a floating-point error cannot add a vote to a whole-number gap.
    const c100 = coalition?.a ?? 100 * candidate;
    const v100 = coalition?.valid ?? 100 * valid;
    const turnoutValid = 100 * v100 + c100 * s.turnout;
    const turnoutVotes = c100 * (100 + s.turnout);
    const adjustedVotes = Math.min(200 * turnoutValid,
      Math.max(0, 200 * turnoutVotes + 2 * swing * turnoutValid));
    const quarterVoteGap = (50 * turnoutValid - adjustedVotes) / 2_000_000;
    return {
      ...metrics(row, candidate, validVotes, share * validVotes, share, rawShare, undefined, quarterVoteGap),
      shareAfterTurnout, rivalVotes,
    };
  }

  function tally(rows) {
    return {
      secured: rows.filter(row => row.status === status.secured).length,
      withinReach: rows.filter(row => row.status === status.within).length,
      outOfReach: rows.filter(row => row.status === status.out).length,
      capped: rows.filter(row => row.capped).length,
      computable: rows.filter(row => row.share != null).length,
    };
  }

  function collect(rows, s, valid = true, message = '') {
    const ranked = rows.filter(row => row.share != null).sort((a, b) => b.share - a.share || compare(a.code, b.code));
    ranked.forEach((row, index) => { row.rank = index + 1; });
    const filteredRows = rows.filter(row => (!s.zone || s.zone === row.zoneCode || s.zone === row.zone)
      && (!s.state || [row.code, row.stateCode, row.name].includes(s.state)));
    const totals = tally(rows);
    const votes = sum(ranked, row => row.votes);
    const validVotes = sum(ranked, row => row.validVotes);
    return {
      valid, message, rows, filteredRows, ranked, counts: valid ? tally(filteredRows) : null,
      tipping: ranked[s.rule - 1] ?? null,
      national: valid ? {
        votes, validVotes, share: ratio(votes, validVotes), secured: totals.secured, unitsNeeded: s.rule,
        stillNeeded: Math.max(0, s.rule - totals.secured), clears: totals.secured >= s.rule,
        computable: totals.computable, capped: totals.capped,
      } : null,
    };
  }

  function closestCalls(ranked, name) {
    const margin = row => 4 * row.votes - row.validVotes;
    const narrowest = rows => rows.sort((a, b) => Math.abs(margin(a)) - Math.abs(margin(b)) || compare(a.code, b.code))[0];
    const won = narrowest(ranked.filter(row => margin(row) >= 0));
    const missed = narrowest(ranked.filter(row => margin(row) < 0));
    const a = won ? `${won.name}, the narrowest state won, was about ${number.format(Math.floor(margin(won) / 4))} votes above a quarter of the vote.` : 'No state reached a quarter of the vote.';
    const b = missed ? `${missed.name}, the narrowest miss, needed about ${number.format(Math.ceil(-margin(missed) / 4))} more votes switching to ${name} from other candidates.` : 'Every state reached a quarter of the vote.';
    return `${name} in 2023: ${a} ${b}`;
  }

  function decidingSentence(row, name) {
    if (!row) return '';
    const prefix = `${row.name} is the deciding state. ${name} is `;
    return row.status === status.secured
      ? `${prefix}${Math.max(0, row.pointsFrom25).toFixed(1)} points above a quarter of the vote there: about ${number.format(row.votesToSpare)} votes could switch to other candidates before the state is lost.`
      : `${prefix}${row.pointsNeeded.toFixed(1)} points short of a quarter of the vote there: about ${number.format(row.votesNeeded)} more votes would need to switch to them from other candidates.`;
  }

  function resultSummary(page, name, rivals, getVotes, getValid, scale = 1) {
    const rankedRivals = rivals.map(rival => ({
      ...rival, votes: sum(page.ranked, row => getVotes(row, rival.code)),
      secured: page.ranked.filter(row => {
        const votes = getVotes(row, rival.code);
        return votes != null && 4 * votes >= getValid(row);
      }).length,
    })).sort((a, b) => b.votes - a.votes || compare(a.code, b.code));
    const rival = rankedRivals[0];
    if (!rival || !page.ranked.length) return '';
    const total = page.national;
    const comparison = compare(scale === 1 ? total.votes : sum(page.ranked, row => row.aHundredths), rival.votes);
    const mostVotes = comparison > 0 ? 'Yes' : comparison === 0 ? 'Tied' : 'No';
    const rivalClears = rival.secured >= total.unitsNeeded;
    Object.assign(total, {
      leadingRival: rival.label, leadingRivalCode: rival.code, leadingRivalName: rival.name,
      leadingRivalVotes: rival.votes / scale, leadingRivalSecured: rival.secured, mostVotes,
    });
    const {secured: k, unitsNeeded: n} = total;
    if (comparison > 0 && total.clears) {
      total.verdict = 'Outright win';
      return `${name} wins outright: the most votes nationwide and a quarter of the vote in ${k} states (${n} needed).`;
    }
    if (comparison > 0) {
      total.verdict = 'No outright winner: run-off (most votes, but not 25% in enough states)';
      return `No outright winner: ${name} has the most votes but a quarter of the vote in only ${k} states (${n} needed). This would go to a run-off.`;
    }
    if (comparison === 0) {
      total.verdict = 'Tie on votes: no outright winner';
      return `${total.verdict}.`;
    }
    if (rivalClears) {
      total.verdict = `Loses: ${rival.label} wins outright`;
      return `${name} loses: ${rival.name} has the most votes and a quarter of the vote in enough states.`;
    }
    total.verdict = `No outright winner: run-off (${rival.label} has most votes)`;
    return `No outright winner: ${rival.name} has the most votes but not a quarter of the vote in enough states. This would go to a run-off.`;
  }

  function assumptions(s) {
    const parts = [];
    if (s.nationalSwing) parts.push(`${signed(s.nationalSwing, 1)} points everywhere`);
    const adjustedZones = Object.keys(zones).filter(code => s.zoneSwings[code]);
    if (adjustedZones.length) parts.push(adjustedZones.map(code => `${signed(s.zoneSwings[code], 1)} in the ${zones[code]}`).join(', '));
    if (s.turnout) parts.push(`${signed(s.turnout, 0)}% turnout among the ${s.coalition ? "coalition's" : "candidate's"} 2023 voters`);
    return `${parts.join('; ') || 'No changes: this is the 2023 result'}. ${s.rule} states needed to win.`;
  }

  function calculate(data, settings = {}) {
    const s = {...defaults, ...settings};
    for (const key of ['turnout', 'nationalSwing', 'rule', 'followA', 'followB', 'comebackA', 'comebackB']) s[key] = value(s[key]) ?? defaults[key];
    s.zoneSwings = Object.fromEntries(Object.keys(zones).map(code => [code, value(settings.zoneSwings?.[code]) ?? 0]));
    s.coalition = s.coalition === true || s.coalition === 'On';
    const states = normalizeStates(Array.isArray(data) ? data : data.states);
    const names = candidateNames(data.parties);
    const selected = coalitionSelection(s, names, data.coalitionNames);
    const validCandidate = parties.includes(s.candidate);
    const candidateName = names[s.candidate];
    const chooseCandidate = validCandidate ? '' : 'Choose a candidate.';
    const fixedRule = {...s, rule: defaults.rule};

    const overview = collect(states.map(row => baselineRow(row, s.candidate)), fixedRule, validCandidate, chooseCandidate);
    const path = {...overview};
    const spread = {...overview};
    path.decidingSentence = decidingSentence(path.tipping, candidateName);
    overview.closestCalls = validCandidate ? closestCalls(overview.ranked, candidateName) : '';
    overview.zoneSummary = Object.keys(zones).map(code => {
      const rows = overview.filteredRows.filter(row => row.zoneCode === code && row.share != null);
      const votes = sum(rows, row => row.votes);
      const validVotes = sum(rows, row => row.validVotes);
      const counts = tally(rows);
      return {code, name: rows[0]?.zone ?? zones[code], votes, validVotes, share: ratio(votes, validVotes),
        secured: counts.secured, computable: counts.computable};
    });
    if (overview.national) {
      overview.national.rank = 1 + parties.filter(party => party !== s.candidate
        && sum(states, row => vote(row, party)) > overview.national.votes).length;
    }

    const mergeRows = states.map(row => {
      const total = selected.validA ? coalitionVotes(row, s, false) : null;
      if (!(total?.valid > 0)) return emptyRow(row);
      const share = total.a / total.valid;
      const leadVotes = vote(row, s.leadA);
      const leadShare = ratio(leadVotes, row.baseValid);
      return {...metrics(row, leadVotes, total.valid / 100, total.a / 100, share, share,
        exactLabel(total.a, total.valid), (total.valid - 4 * total.a) / 400),
        leadVotes, leadShare, changePoints: (share - leadShare) * 100};
    });
    const merge = collect(mergeRows, fixedRule, selected.validA, selected.messageA);
    merge.sideAName = selected.nameA;
    if (merge.national) {
      const leadVotes = sum(merge.ranked, row => row.leadVotes);
      Object.assign(merge.national, {leadVotes,
        leadShare: ratio(leadVotes, sum(merge.ranked, row => row.baseValid)),
        leadSecured: merge.ranked.filter(row => 4 * row.leadVotes >= row.baseValid).length});
    }

    const headRivals = entities(s, true, names, selected);
    const headVotes = (row, code) => {
      if (code === s.leadB) return row.bHundredths;
      const votes = vote(row, code);
      return votes === null ? null : 100 * votes;
    };
    const headRows = states.map(row => {
      const total = selected.validBoth ? coalitionVotes(row, s, true, true) : null;
      if (!(total?.valid > 0)) return emptyRow(row);
      const share = total.a / total.valid;
      const other = headRivals.filter(rival => rival.code !== s.leadB)
        .map(rival => ({code: rival.code, votes: headVotes(row, rival.code)})).filter(rival => rival.votes != null)
        .sort((a, b) => b.votes - a.votes || compare(a.code, b.code))[0];
      const otherVotes = other?.votes ?? -1;
      const leaderCode = total.a > Math.max(total.b, otherVotes) ? 'A'
        : total.b > Math.max(total.a, otherVotes) ? 'B' : otherVotes > Math.max(total.a, total.b) ? 'O' : 'T';
      const labels = {A: 'Side A', B: 'Side B', O: `${other?.code} (on neither side)`, T: 'Tie'};
      return {
        ...metrics(row, total.a / 100, total.valid / 100, total.a / 100, share, share,
          exactLabel(total.a, total.valid), (total.valid - 4 * total.a) / 400),
        aHundredths: total.a, bHundredths: total.b, validHundredths: total.valid,
        bVotes: total.b / 100, bShare: total.b / total.valid,
        aSecured: 4 * total.a >= total.valid, bSecured: 4 * total.b >= total.valid, leaderCode, leader: labels[leaderCode],
      };
    });
    const headToHead = collect(headRows, fixedRule, selected.validBoth, selected.error);
    Object.assign(headToHead, {sideAName: selected.nameA, sideBName: selected.nameB,
      messageA: selected.messageA, messageB: selected.messageB, resultSentence: ''});
    if (headToHead.national) {
      const aVotes = sum(headToHead.ranked, row => row.aHundredths) / 100;
      const bVotes = sum(headToHead.ranked, row => row.bHundredths) / 100;
      const validVotes = sum(headToHead.ranked, row => row.validHundredths) / 100;
      Object.assign(headToHead.national, {votes: aVotes, validVotes, share: ratio(aVotes, validVotes),
        bVotes, bShare: ratio(bVotes, validVotes), bSecured: headToHead.ranked.filter(row => row.bSecured).length,
        aLed: headToHead.ranked.filter(row => row.leaderCode === 'A').length,
        bLed: headToHead.ranked.filter(row => row.leaderCode === 'B').length});
      headToHead.resultSentence = resultSummary(headToHead, selected.nameA, headRivals, headVotes, row => row.validHundredths, 100);
    }

    const simValid = s.coalition ? selected.validBoth : validCandidate;
    const simName = s.coalition ? selected.nameA : candidateName;
    const simRivals = entities(s, s.coalition, names, selected, data.partyNow);
    const simulator = collect(states.map(row => simValid ? scenarioRow(row, s, simRivals) : emptyRow(row)),
      s, simValid, s.coalition ? selected.error : chooseCandidate);
    simulator.candidateName = simName;
    simulator.resultSentence = simValid ? resultSummary(simulator, simName, simRivals,
      (row, code) => row.rivalVotes[code], row => row.validVotes) : '';
    simulator.assumptions = simValid ? assumptions(s) : '';
    simulator.decidingSentence = decidingSentence(simulator.tipping, simName);
    if (simulator.national?.leadingRival) {
      const r = simulator.national.leadingRival;
      simulator.national.leadingRivalNow = parties.includes(r) ? nowShort(r, data.partyNow) : r;
    }
    const followB = s.partnerB === 'NONE' ? '' : ` (${s.followB}% follow)`;
    simulator.coalitionSentence = !s.coalition ? 'Off: uses the candidate at the top. Coalitions: see Head to head.'
      : simValid ? `On: ${selected.nameA}, ${s.followA}% follow, vs ${selected.nameB}${followB}.`
      : `On, but not complete: ${selected.error} Fix it on Head to head.`;
    simulator.headerLine = !s.coalition ? '' : simValid ? `Coalition On: results are for ${simName}, not the candidate above.`
      : 'Coalition On, but not complete: fix it on Head to head.';

    return {overview, path, spread, simulator, merge, headToHead};
  }

  return Object.freeze({calculate, defaults, ranges, parties, zones});
})();
