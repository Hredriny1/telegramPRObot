const ALLOWED_COMMANDS = [
    '.ping', '.me', '.id', '.business', '.data',
    '.ban', '.unban', '.idlist', '.banlist', '.checkban',
    '.ai', '.mute', '.unmute', '.antimat',
    '.nomute', '.unnomute', '.connect', '.unconnect'
];

export async function onRequestPost(context) {
    const { request, env } = context;

    // Проверка Origin
    const origin = request.headers.get('Origin');
    if (origin && !origin.includes('pages.dev') && !origin.includes('botsave')) {
        return jsonResponse({ status: 'error', message: 'Forbidden' }, 403);
    }

    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { command } = await request.json();

    if (!command || typeof command !== 'string') {
        return jsonResponse({ status: 'error', message: 'Пустая команда' }, 400);
    }

    const cmdName = command.trim().split(' ')[0];
    if (!ALLOWED_COMMANDS.includes(cmdName)) {
        return jsonResponse({
            status: 'error',
            message: `Команда ${cmdName} не разрешена`
        }, 400);
    }

    if (command === '.unconnect') {
        await env.BOT_EVENTS.put('connection_state', JSON.stringify({ connected: false, timestamp: Date.now() }));
        return jsonResponse({ status: 'ok', message: '✅ Соединение разорвано.' });
    }
    if (command === '.connect') {
        await env.BOT_EVENTS.put('connection_state', JSON.stringify({ connected: true, timestamp: Date.now() }));
        return jsonResponse({ status: 'ok', message: '✅ Соединение восстановлено.' });
    }

    const pending = {
        command: command,
        timestamp: Date.now(),
        id: crypto.randomUUID(),
    };
    await env.BOT_EVENTS.put('pending_command', JSON.stringify(pending));

    return jsonResponse({
        status: 'ok',
        message: `⏳ Команда "${command}" отправлена боту.`
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

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    });
}
