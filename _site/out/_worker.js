export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;

    if (pathname === '/api/login' && request.method === 'POST') {
      try {
        const { password } = await request.json();
        const sitePassword = env.SITE_PASSWORD || 'wenyue2026';

        if (password !== sitePassword) {
          return new Response(JSON.stringify({ error: 'wrong password' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        return new Response(JSON.stringify({ ok: true }), {
          headers: {
            'Content-Type': 'application/json',
            'Set-Cookie': `auth=authenticated; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${60 * 60 * 24 * 30}`,
          },
        });
      } catch {
        return new Response(JSON.stringify({ error: 'bad request' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    const publicPaths = ['/login', '/_next/', '/manifest', '/icon', '/favicon.ico'];
    if (publicPaths.some((p) => pathname === p || pathname.startsWith(p + '/') || pathname.startsWith(p))) {
      return env.ASSETS.fetch(request);
    }

    const cookie = request.headers.get('Cookie') || '';
    if (!cookie.includes('auth=authenticated')) {
      return Response.redirect(new URL('/login', request.url).toString(), 302);
    }

    return env.ASSETS.fetch(request);
  },
};
