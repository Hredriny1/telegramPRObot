export async function onRequestGet(context) {
    const { request, env } = context;
    const auth = request.headers.get('X-Admin-Password');
    if (auth !== env.ADMIN_PASSWORD) {
        return jsonResponse({ status: 'error', message: 'Unauthorized' }, 401);
    }

    const commands = [
        '.ping', '.me', '.id', '.business', '.data',
        '.ban', '.unban', '.idlist', '.banlist', '.checkban',
        '.ai', '.mute', '.unmute', '.antimat',
        '.nomute', '.unnomute', '.connect', '.unconnect'
    ];

    return jsonResponse({ status: 'ok', commands });
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
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, X-Admin-Password',
        },
    });
}
