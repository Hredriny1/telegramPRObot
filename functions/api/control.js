export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { action } = await request.json();

    let state = { connected: true, last_action: action, timestamp: Date.now() };

    if (action === 'disconnect') {
        state.connected = false;
        await env.BOT_EVENTS.put('connection_state', JSON.stringify(state));
        return jsonResponse({ status: 'ok', message: 'Соединение разорвано' });
    }

    if (action === 'connect') {
        state.connected = true;
        await env.BOT_EVENTS.put('connection_state', JSON.stringify(state));
        return jsonResponse({ status: 'ok', message: 'Соединение установлено' });
    }

    if (action === 'restart') {
        state.connected = true;
        await env.BOT_EVENTS.put('connection_state', JSON.stringify(state));
        return jsonResponse({ status: 'ok', message: 'Перезапуск выполнен' });
    }

    return jsonResponse({ status: 'error', message: 'Unknown action' }, 400);
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

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
}
