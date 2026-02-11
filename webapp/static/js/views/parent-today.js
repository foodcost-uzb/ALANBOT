/**
 * Parent dashboard + child today's progress views.
 */
const ParentTodayView = (() => {
    // ── Dashboard — list of children ────────────────────

    async function renderDashboard($el, user) {
        const data = await API.get('/api/children');
        window.appUpdateApprovalBadge(data.pending_approvals);

        let html = '<div class="page-header">👨‍👩‍👧‍👦 Семья</div>';

        if (data.children.length === 0) {
            html += '<div class="empty-state"><div class="emoji">👶</div><p>В семье пока нет детей</p></div>';
            $el.innerHTML = html;
            return;
        }

        for (const child of data.children) {
            const pct = child.total_tasks > 0 ? Math.round((child.done / child.total_tasks) * 100) : 0;
            const fillClass = pct >= 80 ? '' : (pct >= 50 ? 'warning' : 'danger');
            html += `
                <div class="child-card" data-child-id="${child.id}">
                    <div class="name">${child.name}</div>
                    <div class="stats">${child.done}/${child.total_tasks} задач выполнено${child.pending ? ` (${child.pending} на проверке)` : ''}</div>
                    <div class="progress-bar"><div class="fill ${fillClass}" style="width:${pct}%"></div></div>
                </div>
            `;
        }

        // Quick action buttons
        html += `
            <div class="card">
                <div style="display:flex;flex-wrap:wrap;gap:8px">
        `;
        for (const child of data.children) {
            html += `
                <button class="btn btn-outline btn-sm" data-action="report" data-child-id="${child.id}">📊 Отчёт ${child.name}</button>
                <button class="btn btn-outline btn-sm" data-action="history" data-child-id="${child.id}">📜 История ${child.name}</button>
                <button class="btn btn-outline btn-sm" data-action="extras" data-child-id="${child.id}">⭐ Доп. ${child.name}</button>
                <button class="btn btn-outline btn-sm" data-action="tasks" data-child-id="${child.id}">📝 Задачи ${child.name}</button>
            `;
        }
        html += '</div></div>';

        // Invite code
        html += `<div class="card text-center"><button class="btn btn-outline btn-sm" id="show-invite">🔗 Инвайт-код</button><div id="invite-display"></div></div>`;

        $el.innerHTML = html;

        // Events
        $el.querySelectorAll('.child-card').forEach(card => {
            card.addEventListener('click', () => {
                window.appNavigate('child-today', { childId: parseInt(card.dataset.childId) });
            });
        });

        $el.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const childId = parseInt(btn.dataset.childId);
                const action = btn.dataset.action;
                const routes = { report: 'child-report', history: 'child-history', extras: 'child-extras', tasks: 'child-tasks' };
                window.appNavigate(routes[action], { childId });
            });
        });

        document.getElementById('show-invite').addEventListener('click', async () => {
            const inv = await API.get('/api/invite');
            document.getElementById('invite-display').innerHTML = `<div class="invite-code">${inv.invite_code}</div>`;
        });
    }

    // ── Child today detail ──────────────────────────────

    async function renderChild($el, user, childId) {
        const data = await API.get(`/api/today/${childId}`);

        let html = `
            <div class="back-row">
                <button class="back-btn" id="back-btn">← Назад</button>
            </div>
            <div class="page-header">${data.child_name}<div class="subtitle">${formatDate(data.date)}</div></div>
        `;

        // Score
        const scoreText = data.shower_missing ? '0 ⚠️' : `${data.points}/${data.max_points}`;
        html += `
            <div class="card score-summary">
                <div class="score-big">${scoreText}</div>
                <div class="score-label">баллов за сегодня</div>
                ${data.shower_missing ? '<div class="text-sm text-hint mt-8">Душ не принят — баллы за день: 0</div>' : ''}
                ${data.extra_points ? `<div class="text-sm mt-8">⭐ Доп. задания: +${data.extra_points} б.</div>` : ''}
            </div>
        `;

        // Tasks
        html += '<div class="card">';
        const GROUP_HEADERS = { morning: '🌅 Утро', evening: '🌙 Вечер', sunday: '🧹 Воскресенье', custom: '📝 Свои задачи' };
        let currentGroup = null;
        for (const task of data.tasks) {
            if (task.group !== currentGroup) {
                currentGroup = task.group;
                html += `<div class="task-group-header">${GROUP_HEADERS[currentGroup] || currentGroup}</div>`;
            }
            const icons = { todo: '⬜', pending: '🕐', done: '✅' };
            const icon = icons[task.status] || '⬜';
            const doneClass = task.status === 'done' ? ' done' : '';
            html += `<div class="task-item${doneClass}"><span class="task-icon">${icon}</span><span class="task-label">${task.label}</span></div>`;
        }

        if (data.extras.length > 0) {
            html += '<div class="task-group-header">⭐ Доп. задания</div>';
            for (const et of data.extras) {
                const icons = { todo: '⬜', pending: '🕐', done: '✅' };
                const icon = icons[et.status] || '⬜';
                const doneClass = et.status === 'done' ? ' done' : '';
                html += `<div class="task-item${doneClass}"><span class="task-icon">${icon}</span><span class="task-label">${et.title} (+${et.points} б.)</span></div>`;
            }
        }
        html += '</div>';

        $el.innerHTML = html;

        document.getElementById('back-btn').addEventListener('click', () => {
            window.appNavigate('home');
        });
    }

    function formatDate(isoDate) {
        const d = new Date(isoDate + 'T00:00:00');
        return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
    }

    return { renderDashboard, renderChild };
})();
