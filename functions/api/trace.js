export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { request_id, steps, timestamp } = await request.json();

    if (!request_id) {
        return jsonResponse({ status: 'error', message: 'No request_id' }, 400);
    }

    // Храним последние 100 трассировок
    let traces = {};
    try {
        const stored = await env.BOT_EVENTS.get('traces');
        traces = stored ? JSON.parse(stored) : {};
    } catch (e) {
        traces = {};
    }

    traces[request_id] = { steps, timestamp };

    // Ограничиваем 100 записями
    const keys = Object.keys(traces);
    if (keys.length > 100) {
        const sorted = keys.sort((a, b) => (traces[a].timestamp || 0) - (traces[b].timestamp || 0));
        for (let i = 0; i < keys.length - 100; i++) {
            delete traces[sorted[i]];
        }
    }

    await env.BOT_EVENTS.put('traces', JSON.stringify(traces));
    return jsonResponse({ status: 'ok' });
}

export async function onRequestGet(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const url = new URL(request.url);
    const request_id = url.searchParams.get('id');

    if (!request_id) {
        return jsonResponse({ status: 'error', message: 'No id' }, 400);
    }

    let traces = {};
    try {
        const stored = await env.BOT_EVENTS.get('traces');
        traces = stored ? JSON.parse(stored) : {};
    } catch (e) {
        traces = {};
    }

    return jsonResponse({ status: 'ok', trace: traces[request_id] || null });
}

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
}

export async function onRequestOptions() {
    return new Response(null, {
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Password',
        },
    });
}
