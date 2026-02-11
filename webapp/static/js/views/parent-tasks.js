/**
 * Parent task management view — toggle, add, delete, reset tasks.
 */
const ParentTasksView = (() => {
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
        await renderTasks($el, user, childId);
    }

    async function renderTasks($el, user, childId) {
        const data = await API.get(`/api/tasks/${childId}`);

        let html = `
            <div class="back-row"><button class="back-btn" id="back-btn">\u2190 Назад</button></div>
            <div class="page-header">📝 Задачи — ${data.child_name}</div>
            <div class="card">
        `;

        for (const task of data.tasks) {
            html += `
                <div class="toggle-item">
                    <span class="label">${task.label}</span>
                    ${!task.is_standard ? `<button class="delete-btn" data-key="${task.key}" title="Удалить">✕</button>` : ''}
                    <label class="toggle-switch">
                        <input type="checkbox" ${task.enabled ? 'checked' : ''} data-key="${task.key}">
                        <span class="slider"></span>
                    </label>
                </div>
            `;
        }

        html += `
            </div>
            <div class="card">
                <div class="form-group">
                    <label>Новая задача</label>
                    <input type="text" class="form-input" id="new-task-label" placeholder="Название задачи">
                </div>
                <button class="btn btn-primary" id="add-task-btn">Добавить задачу</button>
            </div>
            <div class="card text-center">
                <button class="btn btn-outline" id="reset-btn">↩ Сбросить к стандартным</button>
            </div>
        `;

        $el.innerHTML = html;

        document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));

        // Toggles
        $el.querySelectorAll('.toggle-switch input').forEach(input => {
            input.addEventListener('change', async () => {
                haptic('light');
                await API.post(`/api/tasks/${childId}/toggle`, {
                    task_key: input.dataset.key,
                    enabled: input.checked,
                });
            });
        });

        // Delete
        $el.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async () => {
                haptic('medium');
                await API.post(`/api/tasks/${childId}/delete`, { task_key: btn.dataset.key });
                await renderTasks($el, user, childId);
            });
        });

        // Add
        document.getElementById('add-task-btn').addEventListener('click', async () => {
            const label = document.getElementById('new-task-label').value.trim();
            if (!label) {
                showAlert('Введите название задачи');
                return;
            }
            haptic('success');
            await API.post(`/api/tasks/${childId}/add`, { label });
            await renderTasks($el, user, childId);
        });

        // Reset
        document.getElementById('reset-btn').addEventListener('click', async () => {
            if (window.Telegram?.WebApp) {
                window.Telegram.WebApp.showConfirm('Сбросить задачи к стандартным?', async (confirmed) => {
                    if (confirmed) {
                        await API.post(`/api/tasks/${childId}/reset`);
                        await renderTasks($el, user, childId);
                    }
                });
            } else {
                if (confirm('Сбросить задачи к стандартным?')) {
                    await API.post(`/api/tasks/${childId}/reset`);
                    await renderTasks($el, user, childId);
                }
            }
        });
    }

    function renderPicker($el, children) {
        let html = `
            <div class="back-row"><button class="back-btn" id="back-btn">\u2190 Назад</button></div>
            <div class="page-header">📝 Задачи<div class="subtitle">Выберите ребёнка</div></div>
        `;
        for (const child of children) {
            html += `<div class="child-card" data-child-id="${child.id}"><div class="name">${child.name}</div></div>`;
        }
        $el.innerHTML = html;

        document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));
        $el.querySelectorAll('.child-card').forEach(card => {
            card.addEventListener('click', () => {
                window.appNavigate('child-tasks', { childId: parseInt(card.dataset.childId) });
            });
        });
    }

    function haptic(style) {
        if (window.Telegram?.WebApp?.HapticFeedback) {
            if (['success', 'error', 'warning'].includes(style)) {
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
