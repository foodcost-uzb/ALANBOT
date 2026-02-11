/**
 * Parent history view — last 4 weeks.
 */
const ParentHistoryView = (() => {
    async function render($el, user, childId) {
        const data = await API.get(`/api/history/${childId}`);

        let html = `
            <div class="back-row">
                <button class="back-btn" id="back-btn">← Назад</button>
            </div>
            <div class="page-header">📜 История — ${data.child_name}</div>
        `;

        if (data.weeks.length === 0) {
            html += '<div class="empty-state"><div class="emoji">📭</div><p>Пока нет данных</p></div>';
            $el.innerHTML = html;
            document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));
            return;
        }

        for (const week of data.weeks) {
            const moneyClass = week.money_percent === 100 ? 'green'
                : week.money_percent >= 70 ? 'yellow'
                : week.money_percent >= 40 ? 'orange'
                : 'red';

            html += `
                <div class="card">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                        <strong>${week.start_display} — ${week.end_display}</strong>
                        <span class="money-badge ${moneyClass}" style="font-size:14px;padding:2px 8px">${week.money_percent}%</span>
                    </div>
                    <table class="report-table">
                        <tr><th>День</th><th>Баллы</th></tr>
            `;
            for (const day of week.days) {
                html += `<tr><td>${day.weekday} ${day.display}</td><td>${day.points}/${week.max_daily}</td></tr>`;
            }
            html += `
                        <tr class="total-row"><td>Итого</td><td>${week.total}${week.extra_total ? ` + ${week.extra_total} доп.` : ''}</td></tr>
                    </table>
                    ${week.penalty ? `<div class="text-sm text-hint mt-8">Штраф: -${week.penalty}</div>` : ''}
                </div>
            `;
        }

        $el.innerHTML = html;
        document.getElementById('back-btn').addEventListener('click', () => window.appNavigate('home'));
    }

    return { render };
})();
