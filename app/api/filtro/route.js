// app/api/filtro/route.js
import { NextResponse } from 'next/server';

const API_KEY = process.env.API_FOOTBALL_KEY;
const API_HOST = process.env.API_FOOTBALL_HOST || 'v3.football.api-sports.io';
const BASE = `https://${API_HOST}`;

async function fetcher(path, params = {}) {
  const url = new URL(BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) url.searchParams.append(k, v);
  });
  const res = await fetch(url.toString(), {
    headers: { 'x-apisports-key': API_KEY },
  });
  if (!res.ok) {
    const txt = await res.text().catch(()=>'');
    throw new Error(`Fetch ${url.toString()} -> ${res.status} ${res.statusText} ${txt}`);
  }
  return res.json();
}

async function getFixturesByDate(date){ const r = await fetcher('/fixtures', { date }); return r.response ?? r.data ?? []; }
async function getLastFixturesForTeam(teamId, last=10){ const r = await fetcher('/fixtures', { team: String(teamId), last: String(last) }); return r.response ?? r.data ?? []; }
async function getStatisticsForFixture(fixtureId){ try{ const r = await fetcher('/fixtures/statistics', { fixture: String(fixtureId) }); return r.response ?? r.data ?? []; }catch(e){return [];} }

function computeHtGoalPctFromLastFixtures(lastFixtures = [], teamId){ if(!Array.isArray(lastFixtures)||lastFixtures.length===0) return 0; let c=0,t=0; for(const f of lastFixtures){ const score = f.score ?? f.goals ?? f; let htHome, htAway; if(score && score.halftime){ htHome = score.halftime.home; htAway = score.halftime.away; } const isHome = Number(f.teams?.home?.id) === Number(teamId); const htGoals = isHome ? (htHome ?? 0) : (htAway ?? 0); if(htGoals>0) c++; t++; } return t ? (c/t) : 0; }
function estimateAvgShotsHTFromFixtures(lastFixtures=[],teamId){ if(!Array.isArray(lastFixtures)||lastFixtures.length===0) return 0; let sum=0,cnt=0; for(const f of lastFixtures){ if(f.statistics && Array.isArray(f.statistics)){ const teamStats = f.statistics.find(s=>Number(s.team?.id)===Number(teamId)); if(teamStats && teamStats.statistics){ const shotsObj = teamStats.statistics.find(x=>/shot/i.test(x.type||x.name||'')); if(shotsObj && typeof shotsObj.value==='number'){ sum += shotsObj.value/2; cnt++; continue; } } } } return cnt ? (sum/cnt) : 0; }

function computeMatchPercentagesAndFilter(match){ const home=match.home||{}, away=match.away||{}; const home_pct = Number(home.ht_goal_pct ?? 0); const away_pct = Number(away.ht_goal_pct ?? 0); const home_shots = Number(home.avg_shots_ht ?? 0); const away_shots = Number(away.avg_shots_ht ?? 0); const home_xg = Number(home.xG_ht ?? 0); const away_xg = Number(away.xG_ht ?? 0); const max_pct = Math.max(home_pct, away_pct); const total_shots = home_shots + away_shots; const avg_xg = (home_xg + away_xg) / ((home_xg || away_xg) ? 2 : 1); const score = Number((max_pct * 100).toFixed(2)) + Number((avg_xg * 10).toFixed(2)) + Number(total_shots.toFixed(2)); const pass = (max_pct >= 0.25) || (total_shots >= 2.5 && avg_xg >= 0.2); return { ...match, _filter: { pass, score, reason: pass ? 'Atende critérios' : 'Não atende', derived: { max_pct, total_shots, avg_xg, home_pct, away_pct, home_shots, away_shots, home_xg, away_xg } } }; }

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const date = searchParams.get('date');
    const lastN = Number(searchParams.get('last') || '10');
    if (!date) return NextResponse.json({ error: 'Parâmetro `date` obrigatório. Formato YYYY-MM-DD' }, { status: 400 });
    if (!API_KEY) return NextResponse.json({ error: 'API key não configurada (API_FOOTBALL_KEY).' }, { status: 500 });

    const fixtures = await getFixturesByDate(date);
    const out = [];

    for (const f of fixtures) {
      const fixtureId = f.fixture?.id ?? f.id ?? null;
      const homeTeam = f.teams?.home ?? f.home ?? {};
      const awayTeam = f.teams?.away ?? f.away ?? {};

      const [homeLast, awayLast] = await Promise.all([
        getLastFixturesForTeam(homeTeam.id, lastN).catch(()=>[]),
        getLastFixturesForTeam(awayTeam.id, lastN).catch(()=>[]),
      ]);

      const home_ht_pct = computeHtGoalPctFromLastFixtures(homeLast, homeTeam.id);
      const away_ht_pct = computeHtGoalPctFromLastFixtures(awayLast, awayTeam.id);

      const home_avg_shots_ht = estimateAvgShotsHTFromFixtures(homeLast, homeTeam.id);
      const away_avg_shots_ht = estimateAvgShotsHTFromFixtures(awayLast, awayTeam.id);

      const stats = fixtureId ? await getStatisticsForFixture(fixtureId).catch(()=>[]) : [];
      let home_xg_ht = 0, away_xg_ht = 0;
      if (Array.isArray(stats) && stats.length > 0) {
        for (const s of stats) {
          const tid = s.team?.id ?? null;
          if (!s.statistics) continue;
          const xgObj = s.statistics.find(st => /xg/i.test(st.type || st.name || ''));
          if (xgObj) {
            if (Number(tid) === Number(homeTeam.id)) home_xg_ht = Number(xgObj.value ?? 0);
            if (Number(tid) === Number(awayTeam.id)) away_xg_ht = Number(xgObj.value ?? 0);
          } else {
            const shotsObj = s.statistics.find(st => /shot/i.test(st.type || st.name || ''));
            if (shotsObj) {
              if (Number(tid) === Number(homeTeam.id)) home_xg_ht = home_xg_ht || (Number(shotsObj.value || 0) / 2);
              if (Number(tid) === Number(awayTeam.id)) away_xg_ht = away_xg_ht || (Number(shotsObj.value || 0) / 2);
            }
          }
        }
      }

      const matchObj = {
        id: fixtureId ?? `${homeTeam.id}-${awayTeam.id}-${new Date().toISOString().split('T')[0]}`,
        date: new Date().toISOString().split('T')[0],
        league: f.league ?? null,
        home: { id: homeTeam.id, name: homeTeam.name ?? null, ht_goal_pct: Number(home_ht_pct), avg_shots_ht: Number(home_avg_shots_ht.toFixed(2)), xG_ht: Number(home_xg_ht) },
        away: { id: awayTeam.id, name: awayTeam.name ?? null, ht_goal_pct: Number(away_ht_pct), avg_shots_ht: Number(away_avg_shots_ht.toFixed(2)), xG_ht: Number(away_xg_ht) },
        raw: f,
      };

      out.push(computeMatchPercentagesAndFilter(matchObj));
    }

    out.sort((a,b) => (b._filter.score ?? 0) - (a._filter.score ?? 0));
    return NextResponse.json(out);
  } catch (err) {
    console.error('Erro /api/filtro', err);
    return NextResponse.json({ error: String(err?.message ?? err) }, { status: 500 });
  }
}
