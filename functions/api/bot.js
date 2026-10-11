export async function onRequestPost(context) {
    const { request, env } = context;

    try {
        const body = await request.json();
        const { action, data } = body;

        // Проверка секретного ключа (чтобы только твой бот мог стучаться)
        const botSecret = env.BOT_SECRET || 'change-me';

        // Простая логика: сохраняем данные в KV (если настроишь) или просто возвращаем
        // Для начала можно сделать заглушку

        if (action === 'ping') {
            return new Response(JSON.stringify({
                status: 'ok',
                message: 'API работает',
                timestamp: Date.now()
            }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        if (action === 'save_data') {
            // Здесь можно сохранять данные в KV или D1
            // Пока просто возвращаем эхо
            return new Response(JSON.stringify({
                status: 'ok',
                received: data
            }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            });
        }

        return new Response(JSON.stringify({ status: 'error', message: 'Unknown action' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json' }
        });
    } catch (err) {
        return new Response(JSON.stringify({ status: 'error', error: err.message }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

export async function onRequestOptions() {
    return new Response(null, {
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
    });
}
