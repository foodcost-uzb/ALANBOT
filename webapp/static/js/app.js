/**
 * ALANBOT Mini App — main router and initialization.
 */
const App = (() => {
    let currentUser = null;
    let currentRoute = null;

    const $content = document.getElementById('content');
    const $loading = document.getElementById('loading');
    const $nav = document.getElementById('nav');

    // ── Telegram WebApp init ─────────────────────────────

    function initTelegram() {
        if (window.Telegram && window.Telegram.WebApp) {
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            tg.enableClosingConfirmation();
        }
    }

    // ── Navigation ───────────────────────────────────────

    function setupNav(role) {
        let navHTML = '';
        if (role === 'child') {
            navHTML = `
                <button class="nav-btn active" data-route="checklist">
                    <span class="nav-icon">📋</span>
                    <span class="nav-label">Чеклист</span>
                </button>
            `;
        } else {
            navHTML = `
                <button class="nav-btn active" data-route="home">
                    <span class="nav-icon">🏠</span>
                    <span class="nav-label">Главная</span>
                </button>
                <button class="nav-btn" data-route="approvals">
                    <span class="nav-icon">👁</span>
                    <span class="nav-label">Проверка</span>
                    <span class="badge" id="approval-badge" style="display:none">0</span>
                </button>
            `;
        }
        $nav.innerHTML = navHTML;
        $nav.style.display = 'flex';

        $nav.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                navigate(btn.dataset.route);
            });
        });
    }

    function setActiveNav(route) {
        $nav.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.route === route);
        });
    }

    function updateApprovalBadge(count) {
        const badge = document.getElementById('approval-badge');
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }

    // ── Router ───────────────────────────────────────────

    async function navigate(route, params = {}) {
        currentRoute = route;
        setActiveNav(route);
        $content.innerHTML = '';
        $content.className = 'fade-in';

        try {
            switch (route) {
                // Child
                case 'checklist':
                    await ChecklistView.render($content, currentUser);
                    break;

                // Parent
                case 'home':
                    await ParentTodayView.renderDashboard($content, currentUser);
                    break;
                case 'approvals':
                    await ParentApprovalsView.render($content, currentUser);
                    break;
                case 'child-today':
                    await ParentTodayView.renderChild($content, currentUser, params.childId);
                    break;
                case 'child-report':
                    await ParentReportView.render($content, currentUser, params.childId);
                    break;
                case 'child-history':
                    await ParentHistoryView.render($content, currentUser, params.childId);
                    break;
                case 'child-extras':
                    await ParentExtrasView.render($content, currentUser, params.childId);
                    break;
                case 'child-tasks':
                    await ParentTasksView.render($content, currentUser, params.childId);
                    break;

                default:
                    $content.innerHTML = '<div class="empty-state"><div class="emoji">🤷</div><p>Страница не найдена</p></div>';
            }
        } catch (err) {
            console.error('Route error:', err);
            $content.innerHTML = `<div class="empty-state"><div class="emoji">😵</div><p>Ошибка: ${err.message}</p></div>`;
        }
    }

    // Expose navigate globally for views
    window.appNavigate = navigate;
    window.appUpdateApprovalBadge = updateApprovalBadge;

    // ── Init ─────────────────────────────────────────────

    async function init() {
        initTelegram();

        try {
            currentUser = await API.get('/api/me');
        } catch (err) {
            $loading.innerHTML = `
                <div class="empty-state">
                    <div class="emoji">🔒</div>
                    <p>Не удалось авторизоваться.<br>Откройте приложение через Telegram.</p>
                </div>
            `;
            return;
        }

        $loading.style.display = 'none';
        $content.style.display = 'block';

        setupNav(currentUser.role);

        if (currentUser.role === 'child') {
            navigate('checklist');
        } else {
            navigate('home');
        }
    }

    // Start
    document.addEventListener('DOMContentLoaded', init);

    return { navigate, currentUser: () => currentUser };
})();
