/**
 * Puente CORS + Disparador Cron Puntual (Cloudflare Workers gratis) para b3TNvjWd®
 *
 * 1) fetch(): Puente CORS seguro para escuchar Audio Guías (Previews_*) directo en https://b3tnvjwd.web.app/
 * 2) scheduled(): Disparador automático puntual hacia GitHub Actions (workflow_dispatch)
 *    sin las demoras/saltos de cola del cron nativo de GitHub.
 *
 * Configuración en Cloudflare Dashboard (Workers & Pages -> b3tnvjwd-bridge -> Settings):
 * - Variables and Secrets -> Add -> Secret: Name = GITHUB_PAT, Value = tu GitHub PAT (permiso workflow/actions)
 * - Trigger Events -> Cron Triggers -> Add estos 5 horarios (UTC, en Cloudflare usar letras de día):
 *     1) 25 16 * * MON-FRI  (Lun-Vie 11:25 AM Lima -> daytime_12)
 *     2) 25 19 * * FRI      (Viernes 02:25 PM Lima -> daytime_15)
 *     3) 25 23 * * FRI,SAT  (Vie-Sáb 06:25 PM Lima -> viva_night + Sáb night_early_20)
 *     4) 20 22 * * SAT,SUN  (Sáb-Dom 05:20 PM Lima -> night)
 *     5) 25 0,2 * * SAT,SUN (Vie 07:25 PM Lima -> night + night_mid_24 | Sáb 09:25 PM Lima -> night_mid_24)
 */

const ALLOWED_REPO = 'jordantfarfan-cmd/grabador-radios-cloud';
const WORKFLOW_FILE = 'record_scheduled.yml';
const ALLOWED_ORIGINS = new Set([
  'https://b3tnvjwd.web.app',
  'https://b3tnvjwd.firebaseapp.com',
  'http://localhost:8008',
  'http://127.0.0.1:8008',
]);

function corsHeaders(origin) {
  const allowOrigin = ALLOWED_ORIGINS.has(origin) ? origin : 'https://b3tnvjwd.web.app';
  return {
    'Access-Control-Allow-Origin': allowOrigin,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Expose-Headers': 'Content-Length, Content-Type',
    'Vary': 'Origin',
  };
}

function ghHeaders(pat) {
  return {
    Authorization: `Bearer ${pat}`,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'b3tnvjwd-cf-bridge',
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

const WINDOW_JOB_NAMES = {
  daytime_12: ['daytime_12'],
  daytime_15: ['daytime_15'],
  viva_night: ['viva_night'],
  night_early_20: ['night_early_20'],
  night_mid_24: ['night_mid_24'],
  night: ['night_block_1', 'night_block_2'],
};

async function isWindowAlreadyActive(pat, windowName) {
  const expectedJobs = WINDOW_JOB_NAMES[windowName] || [windowName];
  const runsRes = await fetch(
    `https://api.github.com/repos/${ALLOWED_REPO}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=8`,
    { headers: ghHeaders(pat) }
  );
  if (!runsRes.ok) return false;
  const runsData = await runsRes.json();
  const activeRuns = (runsData.workflow_runs || []).filter(
    r => r.status === 'in_progress' || r.status === 'queued' || r.status === 'waiting'
  );
  for (const r of activeRuns) {
    const jRes = await fetch(
      `https://api.github.com/repos/${ALLOWED_REPO}/actions/runs/${r.id}/jobs`,
      { headers: ghHeaders(pat) }
    );
    if (!jRes.ok) continue;
    const jData = await jRes.json();
    if ((jData.jobs || []).some(j => expectedJobs.includes(j.name) && (j.status === 'in_progress' || j.status === 'queued'))) {
      return true;
    }
  }
  return false;
}

async function dispatchWindow(pat, windowName) {
  if (await isWindowAlreadyActive(pat, windowName)) {
    console.log(`[SKIP] Ventana '${windowName}' ya activa en GitHub Actions.`);
    return;
  }
  const res = await fetch(
    `https://api.github.com/repos/${ALLOWED_REPO}/actions/workflows/${WORKFLOW_FILE}/dispatches`,
    {
      method: 'POST',
      headers: { ...ghHeaders(pat), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ref: 'main',
        inputs: { window: windowName, override_day: '-1' },
      }),
    }
  );
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(`Dispatch '${windowName}' falló: HTTP ${res.status} ${txt}`);
  }
  console.log(`[OK] Ventana '${windowName}' lanzada puntualmente vía Cloudflare Cron.`);
}

function getWindowsForSchedule(scheduledTimeMs) {
  const dt = new Date(scheduledTimeMs || Date.now());
  const utcDay = dt.getUTCDay();   // JS getUTCDay(): 0=Dom, 1=Lun .. 5=Vie, 6=Sáb
  const utcHour = dt.getUTCHours();

  if (utcHour === 16 && utcDay >= 1 && utcDay <= 5) return ['daytime_12'];
  if (utcHour === 19 && utcDay === 5) return ['daytime_15'];
  if (utcHour === 23 && (utcDay === 5 || utcDay === 6)) {
    return utcDay === 6 ? ['viva_night', 'night_early_20'] : ['viva_night'];
  }
  if (utcHour === 22 && (utcDay === 6 || utcDay === 0)) return ['night'];
  if (utcHour === 0 && utcDay === 6) return ['night', 'night_mid_24']; // Vie 7:25 PM Lima
  if (utcHour === 2 && utcDay === 0) return ['night_mid_24'];          // Sáb 9:25 PM Lima
  return [];
}

export default {
  async fetch(request) {
    const origin = request.headers.get('Origin') || '';
    const cors = corsHeaders(origin);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== 'GET') {
      return new Response('Method not allowed', { status: 405, headers: cors });
    }

    const url = new URL(request.url);
    const id = (url.searchParams.get('id') || '').trim();
    if (!/^\d+$/.test(id)) {
      return new Response('Missing or invalid artifact id', { status: 400, headers: cors });
    }

    const auth = request.headers.get('Authorization') || '';
    if (!auth) {
      return new Response('Missing Authorization header', { status: 401, headers: cors });
    }

    const ghRes = await fetch(
      `https://api.github.com/repos/${ALLOWED_REPO}/actions/artifacts/${id}/zip`,
      {
        headers: {
          Authorization: auth,
          Accept: 'application/vnd.github+json',
          'User-Agent': 'b3tnvjwd-cf-bridge',
        },
        redirect: 'manual',
      }
    );

    const upstream =
      ghRes.status >= 300 && ghRes.status < 400 && ghRes.headers.get('location')
        ? await fetch(ghRes.headers.get('location'))
        : ghRes;

    const headers = new Headers(cors);
    const ct = upstream.headers.get('content-type');
    const cl = upstream.headers.get('content-length');
    if (ct) headers.set('Content-Type', ct);
    if (cl) headers.set('Content-Length', cl);

    return new Response(upstream.body, {
      status: upstream.status,
      headers,
    });
  },

  async scheduled(event, env, ctx) {
    const pat = (env.GITHUB_PAT || '').trim();
    if (!pat) {
      console.error('Falta el secreto GITHUB_PAT en el Worker de Cloudflare.');
      return;
    }
    const windows = getWindowsForSchedule(event.scheduledTime);
    if (!windows.length) return;

    ctx.waitUntil(
      Promise.all(windows.map(w => dispatchWindow(pat, w)))
    );
  },
};
