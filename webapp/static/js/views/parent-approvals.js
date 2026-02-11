/**
 * Parent approvals view — pending task confirmations with media.
 */
const ParentApprovalsView = (() => {
    async function render($el, user) {
        const data = await API.get('/api/approvals');
        window.appUpdateApprovalBadge(data.approvals.length);

        let html = '<div class="page-header">Проверка</div>';

        if (data.approvals.length === 0) {
            html += '<div class="empty-state"><div class="emoji">✨</div><p>Все задачи проверены!</p></div>';
            $el.innerHTML = html;
            return;
        }

        html += `<div class="section-header">${data.approvals.length} на проверке</div>`;

        for (const a of data.approvals) {
            const mediaUrl = a.photo_file_id ? API.mediaUrl(a.photo_file_id) : '';
            const isVideo = a.media_type === 'video';

            html += `
                <div class="approval-card" id="approval-${a.type}-${a.id}">
                    ${mediaUrl ? `<div class="media-wrap">${isVideo
                        ? `<video src="${mediaUrl}" controls playsinline></video>`
                        : `<img src="${mediaUrl}" alt="" loading="lazy">`
                    }</div>` : ''}
                    <div class="info">
                        <div class="child-name">${a.child_name}</div>
                        <div class="task-name">${a.label}${a.points ? ` (+${a.points} б.)` : ''}</div>
                        <div class="text-sm text-hint mt-4">${a.date}</div>
                        <div class="btn-row">
                            <button class="btn btn-success btn-sm" data-action="approve" data-id="${a.id}" data-type="${a.type}">✅ Одобрить</button>
                            <button class="btn btn-danger btn-sm" data-action="reject" data-id="${a.id}" data-type="${a.type}">✕ Отклонить</button>
                        </div>
                    </div>
                </div>
            `;
        }

        $el.innerHTML = html;
        attachEvents($el, user);
    }

    function attachEvents($el, user) {
        $el.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const action = btn.dataset.action;
                const id = btn.dataset.id;
                const type = btn.dataset.type;

                haptic('medium');
                btn.disabled = true;

                try {
                    await API.post(`/api/approvals/${id}/${action}`, { type });
                    const card = document.getElementById(`approval-${type}-${id}`);
                    if (card) {
                        card.classList.add('processed');
                        const info = card.querySelector('.info');
                        const badge = action === 'approve' ? '✅ Одобрено' : '❌ Отклонено';
                        info.querySelector('.btn-row').innerHTML = `<div class="approval-result">${badge}</div>`;
                    }
                    haptic(action === 'approve' ? 'success' : 'warning');

                    // Update badge
                    const remaining = $el.querySelectorAll('.approval-card:not(.processed)').length;
                    window.appUpdateApprovalBadge(remaining);
                } catch (err) {
                    btn.disabled = false;
                    haptic('error');
                    showAlert('Ошибка: ' + err.message);
                }
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
