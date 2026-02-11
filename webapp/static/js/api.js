/**
 * API client — fetch wrapper with Telegram WebApp authorization.
 * Auto-detects base path (works both at / and /alanbot/).
 */
const API = (() => {
    // Determine base path from current page URL
    const BASE = (() => {
        const path = window.location.pathname;
        // If page is at /alanbot/ or /alanbot/index.html, base is /alanbot
        const idx = path.lastIndexOf('/');
        const dir = path.substring(0, idx) || '';
        return dir;
    })();

    function getInitData() {
        if (window.Telegram && window.Telegram.WebApp) {
            return window.Telegram.WebApp.initData;
        }
        return '';
    }

    async function request(path, options = {}) {
        const headers = options.headers || {};
        headers['Authorization'] = 'tma ' + getInitData();

        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = headers['Content-Type'] || 'application/json';
        }

        const url = BASE + path;
        const resp = await fetch(url, { ...options, headers });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ error: 'Unknown error' }));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }

        return resp.json();
    }

    function get(path) {
        return request(path, { method: 'GET' });
    }

    function post(path, body) {
        if (body instanceof FormData) {
            return request(path, { method: 'POST', body, headers: {} });
        }
        return request(path, {
            method: 'POST',
            body: JSON.stringify(body),
        });
    }

    function mediaUrl(fileId) {
        if (!fileId) return '';
        if (fileId.startsWith('uploads/')) {
            return BASE + '/' + fileId;
        }
        return BASE + '/api/media/' + encodeURIComponent(fileId);
    }

    return { get, post, mediaUrl, BASE };
})();
