export async function onRequestPost(context) {
    const { request, env } = context;
    try {
        const body = await request.json();
        const { password } = body;
        const expectedPassword = env.ADMIN_PASSWORD || 'ADMIN';

        if (password === expectedPassword) {
            return jsonResponse({ success: true });
        }
        return jsonResponse({ success: false });
    } catch (err) {
        return jsonResponse({ success: false, error: err.message }, 500);
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

function jsonResponse(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status: status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
}
