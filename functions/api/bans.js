export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const body = await request.json();
    const { action, ban } = body;

    let bans = [];
    try {
        const stored = await env.BOT_EVENTS.get('bans');
        bans = stored ? JSON.parse(stored) : [];
    } catch (e) {
        bans = [];
    }

    if (action === 'add') {
        // Проверка на дубликат
        const exists = bans.find(b => b.id === ban.id || (ban.username && b.username === ban.username));
        if (exists) {
            return jsonResponse({ status: 'error', message: 'Уже в бане' }, 400);
        }
        bans.push(ban);
    } else if (action === 'remove') {
        bans = bans.filter(b => b.id !== ban.id && b.username !== ban.username);
    } else if (action === 'list') {
        return jsonResponse({ status: 'ok', bans: bans });
    } else if (action === 'check') {
        const found = bans.find(b => b.id === ban.id || b.username === ban.username);
        return jsonResponse({ status: 'ok', banned: !!found, ban: found || null });
    }

    await env.BOT_EVENTS.put('bans', JSON.stringify(bans));
    return jsonResponse({ status: 'ok', total: bans.length });
}

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
    });
}

export async function onRequestOptions() {
    return new Response(null, {
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Password',
        },
    });
}
