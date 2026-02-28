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

        // Count stats
        const total = data.tasks.length + data.extras.length;
        const done = data.tasks.filter(t => t.status === 'done').length + data.extras.filter(e => e.status === 'done').length;
        const pending = data.tasks.filter(t => t.status === 'pending').length + data.extras.filter(e => e.status === 'pending').length;
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;

        let html = `
            <div class="page-header">
                📋 Чеклист
                <div class="subtitle">${formatDate(data.date)}</div>
            </div>
            <div class="card score-summary">
                <div class="score-big">${done}<span style="font-size:20px;opacity:0.5">/${total}</span></div>
                <div class="score-label">${pending > 0 ? `${pending} на проверке` : 'выполнено задач'}</div>
                <div class="progress-bar mt-8"><div class="fill" style="width:${pct}%"></div></div>
            </div>
            <div class="card">
        `;

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
        $el.innerHTML = html;
        attachEvents($el, user);
    }

    function taskItemHTML(task, type) {
        const icons = { todo: '⬜', pending: '🕐', done: '✅' };
        const icon = icons[task.status] || '⬜';
        const statusClass = task.status === 'done' ? ' done' : (task.status === 'pending' ? ' pending' : '');
        const dataAttr = type === 'extra'
            ? `data-extra-id="${task.extraId}"`
            : `data-task-key="${task.key}"`;

        return `
            <div class="task-item${statusClass}" ${dataAttr} data-status="${task.status}" data-type="${type}">
                <span class="task-icon">${icon}</span>
                <span class="task-label">${task.label}</span>
            </div>
        `;
    }

    function attachEvents($el, user) {
        $el.querySelectorAll('.task-item').forEach(item => {
            item.addEventListener('click', () => {
                haptic('light');
                handleTaskClick(item, $el, user);
            });
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
            if (type === 'extra') {
                uncompleteExtra(item.dataset.extraId, $el, user);
            } else {
                uncompleteTask(item.dataset.taskKey, $el, user);
            }
            return;
        }

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
        cancelBtn.addEventListener('click', () => {
            haptic('light');
            overlay.remove();
        });

        input.addEventListener('change', async () => {
            if (!input.files.length) return;
            const file = input.files[0];

            haptic('medium');
            overlay.innerHTML = '<div class="upload-indicator"><div class="spinner"></div><p>Загрузка...</p></div>';

            try {
                const formData = new FormData();
                formData.append('file', file);

                let result;
                if (extraId) {
                    result = await API.post(`/api/extras/${extraId}/complete`, formData);
                } else {
                    result = await API.post(`/api/checklist/${taskKey}/complete`, formData);
                }

                haptic('success');
                overlay.remove();

                if (result && result.late) {
                    showAlert('⚠️ Задача сдана после 22:00');
                }

                await render($el, user);
            } catch (err) {
                overlay.remove();
                haptic('error');
                showAlert('Ошибка: ' + err.message);
            }
        });
    }

    async function uncompleteTask(taskKey, $el, user) {
        try {
            await API.post(`/api/checklist/${taskKey}/uncomplete`);
            haptic('light');
            await render($el, user);
        } catch (err) {
            showAlert('Ошибка: ' + err.message);
        }
    }

    async function uncompleteExtra(extraId, $el, user) {
        try {
            await API.post(`/api/extras/${extraId}/uncomplete`);
            haptic('light');
            await render($el, user);
        } catch (err) {
            showAlert('Ошибка: ' + err.message);
        }
    }

    function formatDate(isoDate) {
        const [year, month, day] = isoDate.split('-').map(Number);
        const dayNames = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
        const d = new Date(year, month - 1, day);
        return `${dayNames[d.getDay()]}, ${day}.${String(month).padStart(2, '0')}`;
    }

    function haptic(style) {
        if (window.Telegram?.WebApp?.HapticFeedback) {
            if (style === 'success' || style === 'error') {
                window.Telegram.WebApp.HapticFeedback.notificationOccurred(style);
            } else {
                window.Telegram.WebApp.HapticFeedback.impactOccurred(style);
            }
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
