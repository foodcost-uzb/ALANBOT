/**
 * Child checklist view — tasks grouped, photo upload, statuses.
 */
const ChecklistView = (() => {
    const GROUP_HEADERS = {
        morning: '🌅 Утро',
        evening: '🌙 Вечер',
        sunday: '🧹 Воскресенье',
        custom: '📝 Свои задачи',
    };

    async function render($el, user) {
        const data = await API.get('/api/checklist');
        $el.innerHTML = buildHTML(data);
        attachEvents($el, user, data);
    }

    function buildHTML(data) {
        let html = `<div class="page-header">📋 Чеклист<div class="subtitle">${formatDate(data.date)}</div></div>`;
        html += '<div class="card">';

        let currentGroup = null;
        for (const task of data.tasks) {
            if (task.group !== currentGroup) {
                currentGroup = task.group;
                html += `<div class="task-group-header">${GROUP_HEADERS[currentGroup] || currentGroup}</div>`;
            }
            html += taskItemHTML(task, 'task');
        }

        if (data.extras.length > 0) {
            html += '<div class="task-group-header">⭐ Доп. задания</div>';
            for (const et of data.extras) {
                html += taskItemHTML({
                    key: 'extra_' + et.id,
                    label: `${et.title} (+${et.points} б.)`,
                    status: et.status,
                    extraId: et.id,
                }, 'extra');
            }
        }

        html += '</div>';
        return html;
    }

    function taskItemHTML(task, type) {
        const icons = { todo: '⬜', pending: '🕐', done: '✅' };
        const icon = icons[task.status] || '⬜';
        const doneClass = task.status === 'done' ? ' done' : '';
        const dataAttr = type === 'extra'
            ? `data-extra-id="${task.extraId}"`
            : `data-task-key="${task.key}"`;

        return `
            <div class="task-item${doneClass}" ${dataAttr} data-status="${task.status}" data-type="${type}">
                <span class="task-icon">${icon}</span>
                <span class="task-label">${task.label}</span>
            </div>
        `;
    }

    function attachEvents($el, user, data) {
        $el.querySelectorAll('.task-item').forEach(item => {
            item.addEventListener('click', () => handleTaskClick(item, $el, user));
        });
    }

    function handleTaskClick(item, $el, user) {
        const status = item.dataset.status;
        const type = item.dataset.type;

        if (status === 'pending') {
            showAlert('🕐 Ожидает проверки родителем');
            return;
        }

        if (status === 'done') {
            // Uncomplete
            if (type === 'extra') {
                uncompleteExtra(item.dataset.extraId, $el, user);
            } else {
                uncompleteTask(item.dataset.taskKey, $el, user);
            }
            return;
        }

        // Todo — open photo capture
        if (type === 'extra') {
            openPhotoCapture(item.querySelector('.task-label').textContent, null, item.dataset.extraId, $el, user);
        } else {
            openPhotoCapture(item.querySelector('.task-label').textContent, item.dataset.taskKey, null, $el, user);
        }
    }

    function openPhotoCapture(label, taskKey, extraId, $el, user) {
        const overlay = document.createElement('div');
        overlay.className = 'photo-overlay';
        overlay.innerHTML = `
            <div class="task-title">📸 ${label}</div>
            <input type="file" accept="image/*,video/*" capture="environment" class="hidden-input" id="photo-input">
            <button class="capture-btn" id="capture-btn">📷</button>
            <button class="cancel-btn" id="capture-cancel">Отмена</button>
        `;
        document.body.appendChild(overlay);

        const input = overlay.querySelector('#photo-input');
        const captureBtn = overlay.querySelector('#capture-btn');
        const cancelBtn = overlay.querySelector('#capture-cancel');

        captureBtn.addEventListener('click', () => input.click());
        cancelBtn.addEventListener('click', () => overlay.remove());

        input.addEventListener('change', async () => {
            if (!input.files.length) return;
            const file = input.files[0];
            overlay.innerHTML = '<div class="spinner"></div><p style="color:#fff;margin-top:12px">Загрузка...</p>';

            try {
                const formData = new FormData();
                formData.append('file', file);

                if (extraId) {
                    await API.post(`/api/extras/${extraId}/complete`, formData);
                } else {
                    await API.post(`/api/checklist/${taskKey}/complete`, formData);
                }

                overlay.remove();
                await render($el, user);
            } catch (err) {
                overlay.remove();
                showAlert('Ошибка: ' + err.message);
            }
        });
    }

    async function uncompleteTask(taskKey, $el, user) {
        try {
            await API.post(`/api/checklist/${taskKey}/uncomplete`);
            await render($el, user);
        } catch (err) {
            showAlert('Ошибка: ' + err.message);
        }
    }

    async function uncompleteExtra(extraId, $el, user) {
        try {
            await API.post(`/api/extras/${extraId}/uncomplete`);
            await render($el, user);
        } catch (err) {
            showAlert('Ошибка: ' + err.message);
        }
    }

    function formatDate(isoDate) {
        const d = new Date(isoDate + 'T00:00:00');
        const days = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
        return `${days[d.getDay()]}, ${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    function showAlert(text) {
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.showAlert(text);
        } else {
            alert(text);
        }
    }

    return { render };
})();
