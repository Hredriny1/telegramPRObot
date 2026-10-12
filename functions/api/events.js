import { decrypt } from './crypto.js';

export async function onRequestGet(context) {
    const { env, request } = context;

    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    try {
        const stored = await env.BOT_EVENTS.get('events');
        const encryptedEvents = stored ? JSON.parse(stored) : [];

        const events = [];
        for (const ev of encryptedEvents) {
            try {
                const decrypted = await decrypt(env.ENCRYPTION_KEY, ev.encrypted);
                events.push({ id: ev.id, ...decrypted });
            } catch (e) { /* пропускаем битые */ }
        }

        return jsonResponse({ status: 'ok', events });
    } catch (err) {
        return jsonResponse({ status: 'error', error: err.message, events: [] }, 500);
    }
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

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
}
