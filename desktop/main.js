const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fetch = require('node-fetch');
const Store = require('electron-store');

const store = new Store({
  defaults: {
    siteApiUrl: '',
    adminPassword: ''
  }
});

function createWindow() {
  const win = new BrowserWindow({
    width: 920,
    height: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true
    }
  });
  win.loadFile('index.html');
}

app.whenReady().then(createWindow);

ipcMain.handle('save-settings', (event, settings) => {
  store.set('siteApiUrl', settings.siteApiUrl || '');
  store.set('adminPassword', settings.adminPassword || '');
  return { ok: true };
});

ipcMain.handle('get-settings', () => ({
  siteApiUrl: store.get('siteApiUrl'),
  adminPassword: store.get('adminPassword')
}));

ipcMain.handle('send-command', async (event, command) => {
  const siteApiUrl = store.get('siteApiUrl');
  const adminPassword = store.get('adminPassword');

  if (!siteApiUrl || !adminPassword) {
    return { ok: false, error: 'SITE API URL или ADMIN_PASSWORD не настроены' };
  }

  try {
    const sendUrl = `${siteApiUrl.replace(/\/$/, '')}/api/console`;
    const resultUrl = `${siteApiUrl.replace(/\/$/, '')}/api/console_result`;

    const response = await fetch(sendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Password': adminPassword
      },
      body: JSON.stringify({ command })
    });

    const body = await response.json();

    if (!response.ok) {
      return { ok: false, error: body.message || 'Ошибка API' };
    }

    const start = Date.now();
    const timeoutMs = 30000;

    while (Date.now() - start < timeoutMs) {
      await new Promise(r => setTimeout(r, 1200));

      const poll = await fetch(resultUrl, {
        method: 'GET',
        headers: {
          'X-Admin-Password': adminPassword
        }
      });

      if (!poll.ok) continue;

      const pollBody = await poll.json();
      if (pollBody && pollBody.result) {
        return {
          ok: true,
          message: body.message,
          result: pollBody.result
        };
      }
    }

    return { ok: false, error: 'Таймаут ожидания результата (30s)' };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});
