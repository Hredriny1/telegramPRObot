export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { type, message, timestamp } = await request.json();

    // Читаем состояние алертов
    let alertState = {};
    try {
        const stored = await env.BOT_EVENTS.get('alert_state');
        alertState = stored ? JSON.parse(stored) : {};
    } catch (e) {
        alertState = {};
    }

    // Дедупликация: не спамим один и тот же алерт
    const lastAlert = alertState[type];
    if (lastAlert && (timestamp - lastAlert) < 600000) { // 10 минут
        return jsonResponse({ status: 'ok', message: 'Suppressed (dedup)' });
    }

    alertState[type] = timestamp;
    await env.BOT_EVENTS.put('alert_state', JSON.stringify(alertState));

    // Сохраняем алерт в историю
    let alerts = [];
    try {
        const stored = await env.BOT_EVENTS.get('alerts');
        alerts = stored ? JSON.parse(stored) : [];
    } catch (e) {
        alerts = [];
    }

    alerts.unshift({ type, message, timestamp, sent: true });
    if (alerts.length > 50) alerts = alerts.slice(0, 50);
    await env.BOT_EVENTS.put('alerts', JSON.stringify(alerts));

    return jsonResponse({ status: 'ok', message: 'Alert recorded' });
}

export async function onRequestGet(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    let alerts = [];
    try {
        const stored = await env.BOT_EVENTS.get('alerts');
        alerts = stored ? JSON.parse(stored) : [];
    } catch (e) {
        alerts = [];
    }

    return jsonResponse({ status: 'ok', alerts });
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
