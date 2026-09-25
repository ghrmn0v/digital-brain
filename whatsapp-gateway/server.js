const { Client, LocalAuth } = require('whatsapp-web.js');
const axios = require('axios');
const qrcode = require('qrcode-terminal');

// Backend URL via env — never hardcode secrets/endpoints
const BACKEND_URL = process.env.FLY_BACKEND_URL || 'http://localhost:8080/api/v1/whatsapp/webhook';
const CHROMIUM_PATH = process.env.CHROMIUM_PATH || '/usr/bin/chromium';

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        executablePath: CHROMIUM_PATH,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.on('qr', (qr) => {
    console.log('\nScan this QR with WhatsApp:\n');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('\nWhatsApp Gateway ready. Forwarding events to ' + BACKEND_URL + '\n');
});

client.on('message', async (msg) => {
    if (msg.from === 'status@broadcast' || msg.from.endsWith('@g.us')) return;

    const contact = await msg.getContact();
    const senderName = contact.name || contact.pushname || 'unknown';

    const messageType = msg.type;
    let content = msg.body;

    if (msg.hasMedia) {
        if (msg.type === 'ptt' || msg.type === 'audio') content = '[voice message]';
        else if (msg.type === 'image') content = '[image]';
        else if (msg.type === 'sticker') content = '[sticker]';
        else if (msg.type === 'video') content = '[video]';
    }

    console.log(`[${messageType}] ${senderName} (${msg.from})`);

    try {
        await axios.post(BACKEND_URL, {
            sender: msg.from,
            senderName,
            body: content,
            type: messageType,
            timestamp: msg.timestamp
        }, { timeout: 5000 });
        console.log('Event forwarded to connectome.');
    } catch (error) {
        console.error('Backend forward failed:', error.message);
    }
});

client.initialize();