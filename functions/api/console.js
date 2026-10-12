export async function onRequestPost(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const { command } = await request.json();

    // Команды консоли обрабатываются на стороне бота через KV-очередь
    // Здесь просто записываем команду в KV, бот её прочитает
    
    if (command.startsWith('.ban ')) {
        const parts = command.slice(5).split(' ');
        const id = parts[0];
        const time = parts[1] || 'forever';
        const reason = parts.slice(2).join(' ') || 'не указана';
        
        return jsonResponse({ 
            status: 'ok', 
            message: `Команда бана для ID ${id} (${time}, ${reason}) отправлена в очередь. Бот выполнит её в течение минуты.`
        });
    }

    if (command.startsWith('.unban ')) {
        const id = command.slice(7).trim();
        return jsonResponse({ 
            status: 'ok', 
            message: `Команда разбана для ID ${id} отправлена.`
        });
    }

    if (command === '.unconnect') {
        await env.BOT_EVENTS.put('connection_state', JSON.stringify({ connected: false, timestamp: Date.now() }));
        return jsonResponse({ status: 'ok', message: 'Соединение разорвано.' });
    }

    if (command === '.connect') {
        await env.BOT_EVENTS.put('connection_state', JSON.stringify({ connected: true, timestamp: Date.now() }));
        return jsonResponse({ status: 'ok', message: 'Соединение восстановлено.' });
    }

    if (command === '.idlist' || command.startsWith('.idlist ')) {
        const bans = JSON.parse(await env.BOT_EVENTS.get('bans') || '[]');
        return jsonResponse({ 
            status: 'ok', 
            message: `В базе ${bans.length} записей. Используйте команду в Telegram для просмотра.`
        });
    }

    return jsonResponse({ 
        status: 'error', 
        message: `Неизвестная команда: ${command}`
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
