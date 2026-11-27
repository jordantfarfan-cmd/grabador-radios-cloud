/**
 * Puente CORS gratuito en Cloudflare Workers para reproducir Audio Guías (Previews_*)
 * de GitHub Actions directamente en https://b3tnvjwd.web.app/ sin descargar archivos al disco.
 *
 * Despliegue rápido (gratis, sin tarjeta):
 * 1. Entra a https://dash.cloudflare.com -> Workers & Pages -> Create -> Create Worker.
 * 2. Pega este código completo y pulsa "Deploy".
 * 3. Copia la URL del Worker (ej. https://b3tnvjwd-bridge.tuusuario.workers.dev)
 *    y pégala 1 sola vez dentro del cajón "🔑 Token GitHub / Puente" en el Cortador Cloud.
 */

const ALLOWED_REPO = 'jordantfarfan-cmd/grabador-radios-cloud';
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
};
