export async function onRequestGet(context) {
    const { env, request } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const pendingRaw = await env.BOT_EVENTS.get('pending_command');
    if (!pendingRaw) {
        return jsonResponse({ status: 'ok', command: null });
    }

    const pending = JSON.parse(pendingRaw);
    // Удаляем команду после прочтения, чтобы не выполнить дважды
    await env.BOT_EVENTS.delete('pending_command');

    return jsonResponse({ status: 'ok', command: pending.command });
}

export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { result, status } = await request.json();
    await env.BOT_EVENTS.put('command_result', JSON.stringify({
        result: result,
        status: status || 'ok',
        timestamp: Date.now(),
    }));

    return jsonResponse({ status: 'ok' });
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
