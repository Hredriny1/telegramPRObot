const ENCODER = new TextEncoder();
const DECODER = new TextDecoder();

async function getKey(secret) {
    const keyMaterial = await crypto.subtle.importKey(
        'raw',
        ENCODER.encode(secret),
        { name: 'PBKDF2' },
        false,
        ['deriveKey']
    );
    return crypto.subtle.deriveKey(
        {
            name: 'PBKDF2',
            salt: ENCODER.encode('bot-salt-v1'),
            iterations: 100000,
            hash: 'SHA-256',
        },
        keyMaterial,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt']
    );
}

export async function encrypt(secret, data) {
    const key = await getKey(secret);
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = ENCODER.encode(JSON.stringify(data));
    const ciphertext = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv },
        key,
        encoded
    );
    const ivB64 = btoa(String.fromCharCode(...iv));
    const ctB64 = btoa(String.fromCharCode(...new Uint8Array(ciphertext)));
    return `${ivB64}.${ctB64}`;
}

export async function decrypt(secret, encrypted) {
    const [ivB64, ctB64] = encrypted.split('.');
    const iv = Uint8Array.from(atob(ivB64), c => c.charCodeAt(0));
    const ct = Uint8Array.from(atob(ctB64), c => c.charCodeAt(0));
    const key = await getKey(secret);
    const plaintext = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv },
        key,
        ct
    );
    return JSON.parse(DECODER.decode(plaintext));
}
