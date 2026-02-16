/**
 * Parent dashboard + child today's progress views.
 */
const ParentTodayView = (() => {
    async function renderDashboard($el, user) {
        const data = await API.get('/api/children');
        window.appUpdateApprovalBadge(data.pending_approvals);

        let html = '<div class="page-header">CHILD CONTROL</div>';

        if (data.children.length === 0) {
            html += '<div class="empty-state"><div class="emoji">👶</div><p>В семье пока нет детей.<br>Отправьте ребёнку инвайт-код.</p></div>';
            $el.innerHTML = html;
            return;
        }

        for (const child of data.children) {
            const pct = child.total_tasks > 0 ? Math.round((child.done / child.total_tasks) * 100) : 0;
            const fillClass = pct >= 80 ? '' : (pct >= 50 ? 'warning' : 'danger');
            const pendingText = child.pending > 0 ? `, ${child.pending} на проверке` : '';
            html += `
                <div class="child-card" data-child-id="${child.id}">
                    <div class="progress-pct">${pct}%</div>
                    <div class="name">${child.name}</div>
                    <div class="stats">${child.done} из ${child.total_tasks} задач${pendingText}</div>
                    <div class="progress-bar"><div class="fill ${fillClass}" style="width:${pct}%"></div></div>
                </div>
            `;
        }

        // Action grid per child
        for (const child of data.children) {
            html += `<div class="section-header">${child.name}</div>`;
            html += `
                <div class="action-grid">
                    <button class="action-card" data-action="report" data-child-id="${child.id}">
                        <span class="action-icon">📊</span>
                        <span class="action-label">Отчёт</span>
                    </button>
                    <button class="action-card" data-action="history" data-child-id="${child.id}">
                        <span class="action-icon">📜</span>
                        <span class="action-label">История</span>
                    </button>
                    <button class="action-card" data-action="extras" data-child-id="${child.id}">
                        <span class="action-icon">⭐</span>
                        <span class="action-label">Доп. задание</span>
                    </button>
                    <button class="action-card" data-action="tasks" data-child-id="${child.id}">
                        <span class="action-icon">📝</span>
                        <span class="action-label">Задачи</span>
                    </button>
                </div>
            `;
        }

        // Invite + Reset buttons
        html += `
            <div class="card text-center">
                <button class="btn btn-outline btn-sm" id="show-invite">🔗 Показать инвайт-код</button>
                <div id="invite-display"></div>
            </div>
            <div class="card text-center">
                <button class="btn btn-outline btn-sm" id="reset-family-btn" style="color:var(--destructive);border-color:var(--destructive)">⚠️ Сбросить семью</button>
            </div>
        `;

        $el.innerHTML = html;

        // Events — child cards
        $el.querySelectorAll('.child-card').forEach(card => {
            card.addEventListener('click', () => {
                haptic('light');
                window.appNavigate('child-today', { childId: parseInt(card.dataset.childId) });
            });
        });

        // Events — action buttons
        $el.querySelectorAll('.action-card').forEach(btn => {
            btn.addEventListener('click', () => {
                haptic('light');
                const childId = parseInt(btn.dataset.childId);
                const routes = { report: 'child-report', history: 'child-history', extras: 'child-extras', tasks: 'child-tasks' };
                window.appNavigate(routes[btn.dataset.action], { childId });
            });
        });

        // Invite
        document.getElementById('show-invite').addEventListener('click', async () => {
            haptic('light');
            const inv = await API.get('/api/invite');
            document.getElementById('invite-display').innerHTML = `<div class="invite-code">${inv.invite_code}</div>`;
        });

        // Reset family
        document.getElementById('reset-family-btn').addEventListener('click', () => {
            haptic('warning');
            const doReset = async () => {
                await API.post('/api/family/reset');
                haptic('success');
                if (window.Telegram?.WebApp) {
                    window.Telegram.WebApp.showAlert('Семья удалена. Все участники должны заново пройти /start.', () => {
                        window.Telegram.WebApp.close();
                    });
                } else {
                    alert('Семья удалена.');
                    location.reload();
                }
            };
            if (window.Telegram?.WebApp) {
                window.Telegram.WebApp.showConfirm(
                    'Удалить семью и все данные? Все участники должны будут заново зарегистрироваться.',
                    (confirmed) => { if (confirmed) doReset(); }
                );
            } else {
                if (confirm('Удалить семью и все данные?')) doReset();
            }
        });
    }

    async function renderChild($el, user, childId) {
        const data = await API.get(`/api/today/${childId}`);

        const scoreText = data.shower_missing ? '0' : `${data.points}`;
        const maxText = data.max_points;

        let html = `
            <div class="back-row"><button class="back-btn" id="back-btn">\u2190 Назад</button></div>
            <div class="page-header">${data.child_name}<div class="subtitle">${formatDate(data.date)}</div></div>
            <div class="card score-summary">
                <div class="score-big">${scoreText}<span style="font-size:20px;opacity:0.5">/${maxText}</span></div>
                <div class="score-label">баллов за сегодня</div>
                ${data.shower_missing ? '<div class="text-sm mt-8" style="color:var(--destructive)">Душ не принят — баллы за день: 0</div>' : ''}
                ${data.extra_points ? `<div class="text-sm mt-8">⭐ Доп. задания: +${data.extra_points}</div>` : ''}
            </div>
            <div class="card">
        `;

        const GROUP_HEADERS = { morning: '🌅 Утро', evening: '🌙 Вечер', sunday: '🧹 Воскресенье', custom: '📝 Свои задачи' };
        let currentGroup = null;

        for (const task of data.tasks) {
            if (task.group !== currentGroup) {
                currentGroup = task.group;
                html += `<div class="task-group-header">${GROUP_HEADERS[currentGroup] || currentGroup}</div>`;
            }
            const icons = { todo: '⬜', pending: '🕐', done: '✅' };
            const statusClass = task.status === 'done' ? ' done' : (task.status === 'pending' ? ' pending' : '');
            html += `<div class="task-item${statusClass}"><span class="task-icon">${icons[task.status]}</span><span class="task-label">${task.label}</span></div>`;
        }

        if (data.extras.length > 0) {
            html += '<div class="task-group-header">⭐ Доп. задания</div>';
            for (const et of data.extras) {
                const icons = { todo: '⬜', pending: '🕐', done: '✅' };
                const statusClass = et.status === 'done' ? ' done' : (et.status === 'pending' ? ' pending' : '');
                html += `<div class="task-item${statusClass}"><span class="task-icon">${icons[et.status]}</span><span class="task-label">${et.title} (+${et.points} б.)</span></div>`;
            }
        }
        html += '</div>';

        $el.innerHTML = html;
        document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));
    }

    function formatDate(isoDate) {
        const d = new Date(isoDate + 'T00:00:00');
        return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    function haptic(style) {
        if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred(style);
        }
    }

    return { renderDashboard, renderChild };
})();
