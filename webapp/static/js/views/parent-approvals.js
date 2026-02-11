/**
 * Parent approvals view — pending task confirmations.
 */
const ParentApprovalsView = (() => {
    async function render($el, user) {
        const data = await API.get('/api/approvals');
        window.appUpdateApprovalBadge(data.approvals.length);

        let html = '<div class="page-header">👁 Проверка</div>';

        if (data.approvals.length === 0) {
            html += '<div class="empty-state"><div class="emoji">✨</div><p>Нет задач на проверке</p></div>';
            $el.innerHTML = html;
            return;
        }

        for (const a of data.approvals) {
            const mediaUrl = a.photo_file_id ? API.mediaUrl(a.photo_file_id) : '';
            const isVideo = a.media_type === 'video';

            html += `
                <div class="approval-card" id="approval-${a.type}-${a.id}">
                    ${mediaUrl ? (isVideo
                        ? `<video src="${mediaUrl}" controls playsinline></video>`
                        : `<img src="${mediaUrl}" alt="Фото" loading="lazy">`)
                    : ''}
                    <div class="info">
                        <div class="child-name">${a.child_name}</div>
                        <div class="task-name">${a.label}${a.points ? ` (+${a.points} б.)` : ''}</div>
                        <div class="text-sm text-hint">${a.date}</div>
                        <div class="btn-row">
                            <button class="btn btn-primary btn-sm" data-action="approve" data-id="${a.id}" data-type="${a.type}">✅ Одобрить</button>
                            <button class="btn btn-danger btn-sm" data-action="reject" data-id="${a.id}" data-type="${a.type}">❌ Отклонить</button>
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

                btn.disabled = true;
                btn.textContent = '...';

                try {
                    await API.post(`/api/approvals/${id}/${action}`, { type });
                    const card = document.getElementById(`approval-${type}-${id}`);
                    if (card) {
                        card.style.opacity = '0.4';
                        card.style.pointerEvents = 'none';
                        const info = card.querySelector('.info');
                        const badge = action === 'approve' ? '✅ Одобрено' : '❌ Отклонено';
                        info.querySelector('.btn-row').innerHTML = `<div class="text-sm" style="text-align:center;width:100%">${badge}</div>`;
                    }
                    // Update badge count
                    const remaining = $el.querySelectorAll('.approval-card:not([style*="opacity"])').length;
                    window.appUpdateApprovalBadge(Math.max(0, remaining - 1));
                } catch (err) {
                    btn.disabled = false;
                    btn.textContent = action === 'approve' ? '✅ Одобрить' : '❌ Отклонить';
                    showAlert('Ошибка: ' + err.message);
                }
            });
        });
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
