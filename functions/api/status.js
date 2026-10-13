export async function onRequestGet(context) {
    const { env, request } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const statusRaw = await env.BOT_EVENTS.get('bot_status');
    if (!statusRaw) {
        return jsonResponse({
            online: false,
            last_heartbeat: null,
            healthcheck_ok: false,
            ping: null,
            api_ping: null,
            site_ping: null,
        });
    }

    const status = JSON.parse(statusRaw);
    const age = Date.now() - (status.last_heartbeat || 0);
    const online = age < 90000;

    return jsonResponse({
        online: online,
        last_heartbeat: status.last_heartbeat,
        ping: status.ping || status.api_ping || null,
        api_ping: status.api_ping || null,
        site_ping: status.site_ping || null,
        healthcheck_ok: status.healthcheck_ok !== false,
        age_seconds: Math.floor(age / 1000),
    });
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
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Password',
        },
    });
}
