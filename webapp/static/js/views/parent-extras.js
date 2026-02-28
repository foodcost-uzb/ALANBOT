/**
 * Parent extras view — assign bonus task to a child.
 */
const ParentExtrasView = (() => {
    async function render($el, user, childId) {
        if (!childId) {
            const data = await API.get('/api/children');
            if (data.children.length === 1) {
                childId = data.children[0].id;
            } else {
                renderPicker($el, data.children);
                return;
            }
        }

        const children = (await API.get('/api/children')).children;
        const child = children.find(c => c.id === childId);
        const childName = child ? child.name : 'Ребёнок';

        let html = `
            <div class="back-row"><button class="back-btn" id="back-btn">\u2190 Назад</button></div>
            <div class="page-header">⭐ Доп. задание<div class="subtitle">${childName}</div></div>
            <div class="card">
                <div class="form-group">
                    <label>Название задания</label>
                    <input type="text" class="form-input" id="extra-title" placeholder="Например: помыть посуду">
                </div>
                <div class="form-group">
                    <label>Бонусные баллы</label>
                    <input type="number" class="form-input" id="extra-points" value="1" min="1" max="50">
                </div>
                <button class="btn btn-primary mt-12" id="submit-extra">Назначить задание</button>
                <div id="extra-result" class="mt-12 text-center"></div>
            </div>
        `;

        $el.innerHTML = html;

        document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));

        document.getElementById('submit-extra').addEventListener('click', async () => {
            const title = document.getElementById('extra-title').value.trim();
            const points = parseInt(document.getElementById('extra-points').value) || 1;

            if (!title) {
                showAlert('Введите название задания');
                return;
            }

            const btn = document.getElementById('submit-extra');
            btn.disabled = true;
            btn.textContent = 'Отправка...';

            try {
                await API.post('/api/extras', { child_id: childId, title, points });
                haptic('success');
                document.getElementById('extra-result').innerHTML = `<div class="text-success">✅ «${title}» (+${points} б.) назначено!</div>`;
                document.getElementById('extra-title').value = '';
                document.getElementById('extra-points').value = '1';
            } catch (err) {
                document.getElementById('extra-result').innerHTML = `<div style="color:var(--destructive)">Ошибка: ${err.message}</div>`;
            }
            btn.disabled = false;
            btn.textContent = 'Назначить задание';
        });
    }

    function renderPicker($el, children) {
        let html = `
            <div class="back-row"><button class="back-btn" id="back-btn">\u2190 Назад</button></div>
            <div class="page-header">⭐ Доп. задание<div class="subtitle">Выберите ребёнка</div></div>
        `;
        for (const child of children) {
            html += `<div class="child-card" data-child-id="${child.id}"><div class="name">${child.name}</div></div>`;
        }
        $el.innerHTML = html;

        document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));
        $el.querySelectorAll('.child-card').forEach(card => {
            card.addEventListener('click', () => {
                window.appNavigate('child-extras', { childId: parseInt(card.dataset.childId) });
            });
        });
    }

    function haptic(style) {
        if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred(style);
        }
    }

    function showAlert(text) {
        if (window.Telegram?.WebApp) {
            window.Telegram.WebApp.showAlert(text);
        } else {
            alert(text);
        }
    }

    return { render };
})();
