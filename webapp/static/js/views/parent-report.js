/**
 * Parent weekly report view.
 */
const ParentReportView = (() => {
    async function render($el, user, childId) {
        const data = await API.get(`/api/report/${childId}`);

        const moneyClass = data.money_percent === 100 ? 'green'
            : data.money_percent >= 70 ? 'yellow'
            : data.money_percent >= 40 ? 'orange'
            : 'red';

        let html = `
            <div class="back-row">
                <button class="back-btn" id="back-btn">← Назад</button>
            </div>
            <div class="page-header">📊 Отчёт — ${data.child_name}<div class="subtitle">${data.days[0]?.display || ''} — ${data.days[data.days.length - 1]?.display || ''}</div></div>
        `;

        // Money %
        html += `
            <div class="card text-center">
                <div class="money-badge ${moneyClass}">${data.money_percent}%</div>
                <div class="score-label mt-8">карманных денег</div>
            </div>
        `;

        // Daily breakdown table
        html += '<div class="card"><table class="report-table">';
        html += '<tr><th>День</th><th>Баллы</th><th>Доп.</th></tr>';
        for (const day of data.days) {
            html += `<tr><td>${day.weekday} ${day.display}</td><td>${day.points}/${data.max_daily}</td><td>${day.extra || ''}</td></tr>`;
        }
        html += `<tr class="total-row"><td>Сумма</td><td>${data.subtotal}</td><td>${data.extra_total || ''}</td></tr>`;
        if (data.penalty) {
            html += `<tr><td colspan="3" style="color:var(--destructive)">Штраф (уборка): -${data.penalty}</td></tr>`;
        }
        html += `<tr class="total-row"><td>Итого</td><td colspan="2">${data.total}${data.extra_total ? ` + ${data.extra_total} доп.` : ''}</td></tr>`;
        html += '</table></div>';

        $el.innerHTML = html;

        document.getElementById('back-btn').addEventListener('click', () => {
            window.appNavigate('home');
        });
    }

    return { render };
})();
