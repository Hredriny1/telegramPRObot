import { encrypt } from './crypto.js';

export async function onRequestPost(context) {
    const { request, env } = context;

    try {
        const body = await request.json();
        const { action, data } = body;

        if (action === 'ping') {
            return jsonResponse({ status: 'ok', message: 'API работает', timestamp: Date.now() });
        }

        // Шифруем данные
        const encrypted = await encrypt(env.ENCRYPTION_KEY, {
            action: action,
            data: data,
            timestamp: Date.now(),
        });

        // Читаем список событий
        let events = [];
        try {
            const stored = await env.BOT_EVENTS.get('events');
            if (stored) events = JSON.parse(stored);
        } catch (e) { events = []; }

        events.unshift({
            id: crypto.randomUUID(),
            encrypted: encrypted,
            timestamp: Date.now(),
        });

        if (events.length > 500) events = events.slice(0, 500);

        await env.BOT_EVENTS.put('events', JSON.stringify(events));

        return jsonResponse({ status: 'ok', total: events.length });
    } catch (err) {
        return jsonResponse({ status: 'error', error: err.message }, 500);
    }
}

export async function onRequestOptions() {
    return new Response(null, {
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
    });
}

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
}
