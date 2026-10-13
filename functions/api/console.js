export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { command } = await request.json();

    if (!command) {
        return jsonResponse({ status: 'error', message: 'Пустая команда' }, 400);
    }

    // Команды, которые можно выполнить сразу на сайте (управление подключением)
    if (command === '.unconnect') {
        await env.BOT_EVENTS.put('connection_state', JSON.stringify({ connected: false, timestamp: Date.now() }));
        return jsonResponse({ status: 'ok', message: '✅ Соединение разорвано.' });
    }
    if (command === '.connect') {
        await env.BOT_EVENTS.put('connection_state', JSON.stringify({ connected: true, timestamp: Date.now() }));
        return jsonResponse({ status: 'ok', message: '✅ Соединение восстановлено.' });
    }

    // Остальные команды пишем в KV, бот их подхватит
    const pending = {
        command: command,
        timestamp: Date.now(),
        id: crypto.randomUUID(),
    };
    await env.BOT_EVENTS.put('pending_command', JSON.stringify(pending));

    return jsonResponse({
        status: 'ok',
        message: `⏳ Команда "${command}" отправлена боту. Результат появится в течение 10 секунд.`
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
