// ================================================================
        // 1. ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
        // ================================================================
        let JWT_TOKEN = null;
        let THRESHOLDS = {};
        let PARAMS = [];
        let PARAM_IDS = [];
        let currentData = [];
        let charts = {};
        let currentMode = 'separate';
        let chartAlarmsByDay = null;
        let previousOverallStatus = 'NORMAL';
        let lastAddedTimestamp = null;
        const MAX_CHART_POINTS = 200;
        const MAX_TABLE_ROWS = 20;

        // ================================================================
        // 2. АУТЕНТИФИКАЦИЯ
        // ================================================================
        function getAuthHeader() {
            return { 'Authorization': 'Bearer ' + JWT_TOKEN };
        }

        function apiRequest(url, options = {}) {
            options.headers = options.headers || {};
            options.headers['Authorization'] = 'Bearer ' + JWT_TOKEN;
            options.headers['Content-Type'] = 'application/json';
            return fetch(url, options);
        }

        async function login(event) {
            event.preventDefault();
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;
            const errorEl = document.getElementById('login-error');
            const btn = document.getElementById('login-btn');

            errorEl.classList.remove('show');
            btn.disabled = true;
            btn.textContent = '⏳ Вход...';

            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });

                if (!response.ok) {
                    errorEl.textContent = '❌ Неверные учетные данные';
                    errorEl.classList.add('show');
                    btn.disabled = false;
                    btn.textContent = 'Войти';
                    return;
                }

                const data = await response.json();
                JWT_TOKEN = data.access_token;
                localStorage.setItem('opc_token', JWT_TOKEN);

                document.getElementById('login-overlay').classList.add('hidden');
                document.getElementById('app-container').style.display = 'block';

                await initApp();

            } catch (err) {
                errorEl.textContent = '❌ Ошибка подключения к серверу';
                errorEl.classList.add('show');
            }

            btn.disabled = false;
            btn.textContent = 'Войти';
        }

        function logout() {
            JWT_TOKEN = null;
            localStorage.removeItem('opc_token');
            document.getElementById('login-overlay').classList.remove('hidden');
            document.getElementById('app-container').style.display = 'none';
            location.reload();
        }

        function checkAuth() {
            const token = localStorage.getItem('opc_token');
            if (token) {
                try {
                    const decoded = jwt_decode(token);
                    if (decoded.exp * 1000 > Date.now()) {
                        JWT_TOKEN = token;
                        document.getElementById('login-overlay').classList.add('hidden');
                        document.getElementById('app-container').style.display = 'block';
                        return true;
                    }
                } catch (e) {
                    localStorage.removeItem('opc_token');
                }
            }
            return false;
        }

        // ================================================================
        // 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
        // ================================================================
        function formatLocalTime(ts, withDate = true) {
            if (!ts) return '';
            const dt = new Date(ts);
            if (isNaN(dt)) return ts;
            return withDate ? dt.toLocaleString() : dt.toLocaleTimeString();
        }

        function convertTemp(v, u) { return u === 'F' ? v * 9/5 + 32 : v; }
        function convertPress(v, u) {
            if (u === 'bar') return v / 100;
            if (u === 'psi') return v * 0.1450377;
            return v;
        }
        function getTempUnitLabel(u) { return u === 'F' ? '°F' : '°C'; }
        function getPressUnitLabel(u) {
            if (u === 'bar') return 'бар';
            if (u === 'psi') return 'psi';
            return 'кПа';
        }
        function getParamValue(row, id) { return row[id] !== undefined ? row[id] : 0; }

        function getParamStatus(value, id) {
            const t = THRESHOLDS[id];
            if (!t) return 'NORMAL';
            if (t.alarm_low !== undefined && t.warning_low !== undefined && !t.alarm_high) {
                if (value >= t.alarm_low) return 'ALARM';
                if (value >= t.warning_low) return 'WARNING';
                return 'NORMAL';
            }
            if (t.alarm_low !== undefined && t.alarm_high !== undefined) {
                if (value < t.alarm_low || value > t.alarm_high) return 'ALARM';
                if (value < t.warning_low || value > t.warning_high) return 'WARNING';
                return 'NORMAL';
            }
            return 'NORMAL';
        }

        function getStatusText(s) {
            const map = { 'NORMAL': 'Норма', 'WARNING': 'Предупр.', 'ALARM': 'Авария' };
            return map[s] || s;
        }

        function convertValue(value, paramId, tempUnit, pressUnit) {
            if (paramId === 'temperature') return convertTemp(value, tempUnit);
            if (paramId === 'pressure') return convertPress(value, pressUnit);
            return value;
        }

        // ================================================================
        // 4. ЗАГРУЗКА ПАРАМЕТРОВ
        // ================================================================
        async function loadParamsAndThresholds() {
            try {
                const [paramsRes, thresholdsRes] = await Promise.all([
                    apiRequest('/api/params'),
                    apiRequest('/api/thresholds')
                ]);
                if (!paramsRes.ok || !thresholdsRes.ok) throw new Error('Ошибка загрузки');
                PARAMS = await paramsRes.json();
                THRESHOLDS = await thresholdsRes.json();
                PARAM_IDS = PARAMS.map(p => p.id);
                console.log('✅ Параметры:', PARAMS);
                console.log('✅ Пороги:', THRESHOLDS);
                return true;
            } catch (e) {
                console.warn('⚠️ Ошибка загрузки, fallback:', e);
                PARAMS = [
                    { id: 'temperature', name: 'Температура', unit: '°C' },
                    { id: 'pressure', name: 'Давление', unit: 'кПа' },
                    { id: 'humidity', name: 'Влажность', unit: '%' },
                    { id: 'vibration', name: 'Вибрация', unit: 'мм/с' },
                    { id: 'current', name: 'Ток', unit: 'A' },
                    { id: 'speed', name: 'Скорость', unit: 'об/мин' },
                    { id: 'level', name: 'Уровень жидкости', unit: '%' },
                    { id: 'frequency', name: 'Частота', unit: 'Гц' }
                ];
                PARAM_IDS = PARAMS.map(p => p.id);
                THRESHOLDS = {};
                return false;
            }
        }

        // ================================================================
        // 5. ПОСТРОЕНИЕ UI
        // ================================================================
        function buildUI() {
            buildCards();
            buildCompareCheckboxes();
            buildAlarmSelect();
            buildExportParams();
            buildTableHeader();
        }

        function buildCards() {
            const container = document.getElementById('cards-container');
            container.innerHTML = '';
            PARAMS.forEach(p => {
                const card = document.createElement('div');
                card.className = 'card';
                card.id = 'card-' + p.id;
                card.innerHTML = `
                    <div class="label">${p.name}</div>
                    <div class="value"><span id="value-${p.id}">--</span><span class="unit"> ${p.unit || ''}</span></div>
                    <div><span class="status-badge" id="status-${p.id}">--</span></div>
                `;
                container.appendChild(card);
            });
            const overall = document.createElement('div');
            overall.className = 'card';
            overall.id = 'card-status';
            overall.innerHTML = `
                <div class="label">Общий статус</div>
                <div class="value" style="font-size:1.2rem;"><span id="overall-status">--</span></div>
                <div style="font-size:0.85rem; color:#95a5a6;" id="last-updated">--</div>
            `;
            container.appendChild(overall);
        }

        function buildCompareCheckboxes() {
            const container = document.getElementById('compare-params');
            container.innerHTML = '';
            PARAMS.forEach(p => {
                const label = document.createElement('label');
                label.innerHTML = `<input type="checkbox" class="compare-param" data-param="${p.id}" checked> ${p.name}`;
                container.appendChild(label);
            });
            const all = document.createElement('label');
            all.innerHTML = `<input type="checkbox" id="compare-select-all" checked> Выбрать все`;
            container.appendChild(all);

            document.getElementById('compare-select-all').addEventListener('change', function() {
                const checked = this.checked;
                document.querySelectorAll('.compare-param').forEach(cb => cb.checked = checked);
                if (currentMode === 'compare' && currentData.length > 0) renderCharts(currentData);
            });
            document.querySelectorAll('.compare-param').forEach(cb => {
                cb.addEventListener('change', function() {
                    const all = document.querySelectorAll('.compare-param');
                    const checkedAll = Array.from(all).every(c => c.checked);
                    document.getElementById('compare-select-all').checked = checkedAll;
                    if (currentMode === 'compare' && currentData.length > 0) renderCharts(currentData);
                });
            });
            document.querySelectorAll('input[name="chart-mode"]').forEach(radio => {
                radio.addEventListener('change', function() {
                    if (this.checked) {
                        currentMode = this.value;
                        document.getElementById('compare-params').style.display = currentMode === 'compare' ? 'flex' : 'none';
                        if (currentData.length > 0) renderCharts(currentData);
                    }
                });
            });
        }

        function buildAlarmSelect() {
            const select = document.getElementById('alarm-param');
            select.innerHTML = '<option value="">Все</option>';
            PARAMS.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = p.name;
                select.appendChild(opt);
            });
        }

        function buildExportParams() {
            const grid = document.getElementById('export-params-grid');
            grid.innerHTML = '';
            PARAMS.forEach(p => {
                const label = document.createElement('label');
                label.innerHTML = `<input type="checkbox" class="export-param" data-field="${p.id}" checked> ${p.name}`;
                grid.appendChild(label);
            });
            const statusLabel = document.createElement('label');
            statusLabel.innerHTML = `<input type="checkbox" class="export-param" data-field="status" checked> 📌 Статус`;
            grid.appendChild(statusLabel);
            const allLabel = document.createElement('label');
            allLabel.style.gridColumn = '1 / -1';
            allLabel.style.fontWeight = 'bold';
            allLabel.innerHTML = `<input type="checkbox" id="export-select-all" checked> Выбрать все`;
            grid.appendChild(allLabel);

            document.getElementById('export-select-all').addEventListener('change', function() {
                const checked = this.checked;
                document.querySelectorAll('.export-param').forEach(cb => cb.checked = checked);
            });
        }

        function buildTableHeader() {
            const thead = document.getElementById('history-thead');
            let html = '<tr><th>Время</th>';
            PARAMS.forEach(p => { html += `<th>${p.name}</th>`; });
            html += '<th>Общий статус</th></tr>';
            thead.innerHTML = html;
        }

        // ================================================================
        // 6. ФИЛЬТРЫ
        // ================================================================
        function saveFilters() {
            const state = {
                start_date: document.getElementById('start-date').value,
                end_date: document.getElementById('end-date').value,
                status: document.getElementById('status-filter').value,
                limit: document.getElementById('limit-select').value,
                auto_scroll: document.getElementById('auto-scroll').checked,
                temp_unit: document.getElementById('temp-unit').value,
                press_unit: document.getElementById('press-unit').value,
                theme: document.body.classList.contains('dark') ? 'dark' : 'light'
            };
            localStorage.setItem('opc_filters', JSON.stringify(state));
        }

        function loadFilters() {
            const saved = localStorage.getItem('opc_filters');
            if (!saved) return;
            try {
                const state = JSON.parse(saved);
                if (state.start_date) document.getElementById('start-date').value = state.start_date;
                if (state.end_date) document.getElementById('end-date').value = state.end_date;
                if (state.status) document.getElementById('status-filter').value = state.status;
                if (state.limit) document.getElementById('limit-select').value = state.limit;
                if (state.auto_scroll !== undefined) document.getElementById('auto-scroll').checked = state.auto_scroll;
                if (state.temp_unit) document.getElementById('temp-unit').value = state.temp_unit;
                if (state.press_unit) document.getElementById('press-unit').value = state.press_unit;
                if (state.theme === 'dark') document.body.classList.add('dark');
                else document.body.classList.remove('dark');
            } catch(e) {}
        }

        // ================================================================
        // 7. ПОЛНАЯ ЗАГРУЗКА ДАННЫХ
        // ================================================================
        function applyFilters() {
            const params = getFilterParams();
            const query = new URLSearchParams({
                limit: params.limit || 100,
                start_date: params.start_date || '',
                end_date: params.end_date || '',
                status: params.status || 'ALL'
            });
            apiRequest('/api/history?' + query.toString())
                .then(res => res.json())
                .then(data => {
                    // Сортируем по времени
                    data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                    currentData = data || [];
                    if (!data || data.length === 0) {
                        document.getElementById('history-body').innerHTML = '<tr><td colspan="100">Нет данных</td></tr>';
                        Object.values(charts).forEach(chart => { if (chart && chart.destroy) chart.destroy(); });
                        charts = {};
                        document.getElementById('charts-container').innerHTML = '';
                        return;
                    }
                    renderCharts(currentData);
                    updateTable(currentData);
                    updateLatest();
                    if (currentData.length > 0) {
                        lastAddedTimestamp = currentData[currentData.length - 1].timestamp;
                    }
                })
                .catch(err => {
                    console.warn('Ошибка получения истории:', err);
                    document.getElementById('history-body').innerHTML = '<tr><td colspan="100">Ошибка загрузки</td></tr>';
                });
            saveFilters();
        }

        function getFilterParams() {
            return {
                limit: parseInt(document.getElementById('limit-select').value),
                start_date: document.getElementById('start-date').value,
                end_date: document.getElementById('end-date').value,
                status: document.getElementById('status-filter').value
            };
        }

        // ================================================================
        // 8. ОТРИСОВКА ГРАФИКОВ (С СОРТИРОВКОЙ)
        // ================================================================
        function renderCharts(data) {
            // Всегда сортируем входные данные по времени
            const sortedData = data.slice().sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

            // Уничтожаем старые графики
            Object.values(charts).forEach(chart => {
                if (chart && typeof chart.destroy === 'function') chart.destroy();
            });
            charts = {};

            const container = document.getElementById('charts-container');
            container.innerHTML = '';

            const tempUnit = document.getElementById('temp-unit').value;
            const pressUnit = document.getElementById('press-unit').value;
            const labels = sortedData.map(d => formatLocalTime(d.timestamp, false));
            const timestamps = sortedData.map(d => d.timestamp);

            if (currentMode === 'compare') {
                const selectedParams = Array.from(document.querySelectorAll('.compare-param:checked')).map(cb => cb.dataset.param);
                if (selectedParams.length === 0) {
                    container.innerHTML = '<p>Выберите хотя бы один параметр для сравнения</p>';
                    return;
                }
                const div = document.createElement('div');
                div.className = 'chart-container';
                div.innerHTML = '<h3>📊 Сравнение параметров</h3><canvas id="chart-compare"></canvas>';
                container.appendChild(div);
                const ctx = document.getElementById('chart-compare').getContext('2d');
                const datasets = [];
                const colors = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22','#2c3e50'];
                selectedParams.forEach((pid, idx) => {
                    const p = PARAMS.find(p => p.id === pid);
                    if (!p) return;
                    let dataArr = sortedData.map(d => {
                        let val = getParamValue(d, pid);
                        if (pid === 'temperature') val = convertTemp(val, tempUnit);
                        if (pid === 'pressure') val = convertPress(val, pressUnit);
                        return val;
                    });
                    const unitLabel = pid === 'temperature' ? getTempUnitLabel(tempUnit) :
                                      pid === 'pressure' ? getPressUnitLabel(pressUnit) :
                                      p.unit || '';
                    datasets.push({
                        label: p.name + ' (' + unitLabel + ')',
                        data: dataArr,
                        borderColor: colors[idx % colors.length],
                        backgroundColor: colors[idx % colors.length] + '33',
                        tension: 0.2,
                        fill: false
                    });
                });
                if (datasets.length > 0) {
                    charts.compare = new Chart(ctx, {
                        type: 'line',
                        data: { labels, datasets },
                        options: {
                            responsive: true,
                            maintainAspectRatio: true,
                            animation: { duration: 500 },
                            plugins: {
                                tooltip: {
                                    callbacks: {
                                        afterBody: function(tooltipItems) {
                                            const index = tooltipItems[0].dataIndex;
                                            const row = sortedData[index];
                                            if (row) {
                                                const statuses = selectedParams.map(pid => getStatusText(row[pid + '_status'] || 'NORMAL'));
                                                return 'Статусы: ' + statuses.join(', ');
                                            }
                                            return '';
                                        }
                                    }
                                }
                            },
                            scales: {
                                y: { beginAtZero: false, title: { display: true, text: 'Значения' } },
                                x: { title: { display: true, text: 'Время' } }
                            }
                        }
                    });
                    charts.compare.timestamps = timestamps.slice();
                }
                return;
            }

            // Режим отдельных графиков
            const grid = document.createElement('div');
            grid.className = 'charts-grid';
            container.appendChild(grid);

            const colors = ['#e74c3c','#3498db','#2ecc71','#f39c12','#9b59b6','#1abc9c','#e67e22','#2c3e50'];

            PARAMS.forEach((p, idx) => {
                const div = document.createElement('div');
                div.className = 'chart-container';
                div.innerHTML = `<h3>${p.name}</h3><canvas id="chart-${p.id}"></canvas>`;
                grid.appendChild(div);

                const ctx = document.getElementById(`chart-${p.id}`).getContext('2d');

                let paramData = sortedData.map(d => {
                    let val = getParamValue(d, p.id);
                    if (p.id === 'temperature') val = convertTemp(val, tempUnit);
                    if (p.id === 'pressure') val = convertPress(val, pressUnit);
                    return val;
                });
                const unitLabel = p.id === 'temperature' ? getTempUnitLabel(tempUnit) :
                                  p.id === 'pressure' ? getPressUnitLabel(pressUnit) :
                                  p.unit || '';

                const datasets = [{
                    label: p.name + ' (' + unitLabel + ')',
                    data: paramData,
                    borderColor: colors[idx % colors.length],
                    backgroundColor: colors[idx % colors.length] + '33',
                    tension: 0.2,
                    fill: true
                }];

                const t = THRESHOLDS[p.id];
                if (t) {
                    if (t.alarm_high !== undefined && t.alarm_high !== null && t.warning_high !== undefined && t.warning_high !== null) {
                        const wLow = (t.warning_low !== undefined && t.warning_low !== null) ? convertValue(t.warning_low, p.id, tempUnit, pressUnit) : null;
                        const wHigh = convertValue(t.warning_high, p.id, tempUnit, pressUnit);
                        const aLow = (t.alarm_low !== undefined && t.alarm_low !== null) ? convertValue(t.alarm_low, p.id, tempUnit, pressUnit) : null;
                        const aHigh = convertValue(t.alarm_high, p.id, tempUnit, pressUnit);
                        if (wLow !== null) {
                            datasets.push({
                                label: '⚠️ Пред. ниж.',
                                data: new Array(labels.length).fill(wLow),
                                borderColor: '#f1c40f',
                                borderWidth: 2,
                                borderDash: [6, 4],
                                pointRadius: 0,
                                fill: false,
                                showInLegend: true
                            });
                        }
                        if (wHigh !== null) {
                            datasets.push({
                                label: '⚠️ Пред. верх.',
                                data: new Array(labels.length).fill(wHigh),
                                borderColor: '#f1c40f',
                                borderWidth: 2,
                                borderDash: [6, 4],
                                pointRadius: 0,
                                fill: false,
                                showInLegend: true
                            });
                        }
                        if (aLow !== null) {
                            datasets.push({
                                label: '🚨 Авар. ниж.',
                                data: new Array(labels.length).fill(aLow),
                                borderColor: '#e74c3c',
                                borderWidth: 2,
                                borderDash: [6, 4],
                                pointRadius: 0,
                                fill: false,
                                showInLegend: true
                            });
                        }
                        if (aHigh !== null) {
                            datasets.push({
                                label: '🚨 Авар. верх.',
                                data: new Array(labels.length).fill(aHigh),
                                borderColor: '#e74c3c',
                                borderWidth: 2,
                                borderDash: [6, 4],
                                pointRadius: 0,
                                fill: false,
                                showInLegend: true
                            });
                        }
                    } else if (t.alarm_low !== undefined && t.alarm_low !== null && t.warning_low !== undefined && t.warning_low !== null) {
                        const warn = convertValue(t.warning_low, p.id, tempUnit, pressUnit);
                        const alarm = convertValue(t.alarm_low, p.id, tempUnit, pressUnit);
                        if (warn !== null) {
                            datasets.push({
                                label: '⚠️ Предупреждение',
                                data: new Array(labels.length).fill(warn),
                                borderColor: '#f1c40f',
                                borderWidth: 2,
                                borderDash: [8, 4],
                                pointRadius: 0,
                                fill: false,
                                showInLegend: true
                            });
                        }
                        if (alarm !== null) {
                            datasets.push({
                                label: '🚨 Авария',
                                data: new Array(labels.length).fill(alarm),
                                borderColor: '#e74c3c',
                                borderWidth: 2,
                                borderDash: [8, 4],
                                pointRadius: 0,
                                fill: false,
                                showInLegend: true
                            });
                        }
                    }
                }

                charts[p.id] = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        animation: { duration: 500 },
                        plugins: {
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return context.dataset.label + ': ' + context.parsed.y.toFixed(2);
                                    },
                                    afterBody: function(tooltipItems) {
                                        const index = tooltipItems[0].dataIndex;
                                        const row = sortedData[index];
                                        if (row) {
                                            const status = row[p.id + '_status'] || 'NORMAL';
                                            return 'Статус: ' + getStatusText(status);
                                        }
                                        return '';
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: (p.id === 'humidity' || p.id === 'vibration' || p.id === 'current' || p.id === 'level' || p.id === 'frequency'),
                                title: { display: true, text: unitLabel }
                            },
                            x: { title: { display: true, text: 'Время' } }
                        }
                    }
                });
                charts[p.id].timestamps = timestamps.slice();
            });
        }

        // ================================================================
        // 9. ИНКРЕМЕНТАЛЬНОЕ ОБНОВЛЕНИЕ (С СОРТИРОВКОЙ)
        // ================================================================
        function updateCharts(record) {
            if (!record) return;
            const newTimestamp = record.timestamp;
            if (lastAddedTimestamp === newTimestamp) return;

            // Добавляем запись в currentData и сортируем
            currentData.push(record);
            currentData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

            // Ограничиваем количество точек
            if (currentData.length > MAX_CHART_POINTS) {
                currentData = currentData.slice(currentData.length - MAX_CHART_POINTS);
            }

            // Перерисовываем графики полностью
            renderCharts(currentData);
            lastAddedTimestamp = newTimestamp;
        }

        // ================================================================
        // 10. ТАБЛИЦА
        // ================================================================
        function updateTable(data) {
            const tbody = document.getElementById('history-body');
            const rows = data.slice(-MAX_TABLE_ROWS).reverse();
            const tempUnit = document.getElementById('temp-unit').value;
            const pressUnit = document.getElementById('press-unit').value;
            if (!rows.length) {
                tbody.innerHTML = '<tr><td colspan="100">Нет данных</td></tr>';
                return;
            }
            tbody.innerHTML = rows.map(row => {
                let html = `<td>${formatLocalTime(row.timestamp)}</td>`;
                PARAMS.forEach(p => {
                    let val = getParamValue(row, p.id);
                    if (p.id === 'temperature') val = convertTemp(val, tempUnit);
                    if (p.id === 'pressure') val = convertPress(val, pressUnit);
                    const status = row[p.id + '_status'] || 'NORMAL';
                    const cls = status.toLowerCase();
                    const unit = p.id === 'temperature' ? getTempUnitLabel(tempUnit) :
                                 p.id === 'pressure' ? getPressUnitLabel(pressUnit) :
                                 p.unit || '';
                    html += `<td class="cell-${cls}">${val.toFixed(2)} ${unit}</td>`;
                });
                const overallStatus = row.status || 'NORMAL';
                html += `<td><span class="status-cell ${overallStatus.toLowerCase()}">${getStatusText(overallStatus)}</span></td>`;
                return `<tr>${html}</tr>`;
            }).join('');
        }

        // ================================================================
        // 11. КАРТОЧКИ
        // ================================================================
        function updateCard(cardId, badgeId, status) {
            const card = document.getElementById(cardId);
            const badge = document.getElementById(badgeId);
            if (card) {
                const cls = status === 'ALARM' ? 'alarm' : status === 'WARNING' ? 'warning' : 'normal';
                card.className = 'card status-' + cls;
            }
            if (badge) {
                badge.textContent = getStatusText(status);
                const cls = status === 'ALARM' ? 'alarm' : status === 'WARNING' ? 'warning' : 'normal';
                badge.className = 'status-badge ' + cls;
            }
        }

        // ================================================================
        // 12. ОБНОВЛЕНИЕ ПОСЛЕДНИХ ДАННЫХ
        // ================================================================
        function updateLatest() {
            apiRequest('/api/latest')
                .then(res => {
                    if (!res.ok) throw new Error('Сервер недоступен');
                    document.getElementById('connection-indicator').className = 'indicator online';
                    return res.json();
                })
                .then(data => {
                    if (data && data.timestamp) {
                        const tempUnit = document.getElementById('temp-unit').value;
                        const pressUnit = document.getElementById('press-unit').value;
                        PARAMS.forEach(p => {
                            const val = getParamValue(data, p.id);
                            let displayVal = val;
                            if (p.id === 'temperature') displayVal = convertTemp(val, tempUnit);
                            if (p.id === 'pressure') displayVal = convertPress(val, pressUnit);
                            document.getElementById('value-' + p.id).textContent = displayVal.toFixed(2);
                            const status = data[p.id + '_status'] || 'NORMAL';
                            updateCard('card-' + p.id, 'status-' + p.id, status);
                        });
                        const overallStatus = data.status || 'NORMAL';
                        document.getElementById('overall-status').textContent = getStatusText(overallStatus);
                        const cardStatus = document.getElementById('card-status');
                        const cls = overallStatus === 'ALARM' ? 'alarm' : overallStatus === 'WARNING' ? 'warning' : 'normal';
                        cardStatus.className = 'card status-' + cls;
                        document.getElementById('last-updated').textContent = formatLocalTime(data.timestamp);

                        if (overallStatus === 'ALARM' && previousOverallStatus !== 'ALARM') {
                            sendBrowserNotification('🚨 Авария на OPC-мониторе!',
                                `Общий статус: Авария. Время: ${formatLocalTime(data.timestamp)}`);
                        }
                        previousOverallStatus = overallStatus;

                        const soundEnabled = document.getElementById('sound-enabled').checked;
                        if (soundEnabled && overallStatus === 'ALARM') {
                            try {
                                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                                if (ctx.state === 'suspended') ctx.resume();
                                const osc = ctx.createOscillator();
                                const gain = ctx.createGain();
                                osc.type = 'sawtooth';
                                osc.frequency.value = 800;
                                gain.gain.setValueAtTime(0.3, ctx.currentTime);
                                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
                                osc.connect(gain);
                                gain.connect(ctx.destination);
                                osc.start(ctx.currentTime);
                                osc.stop(ctx.currentTime + 0.3);
                            } catch(e) {}
                        }
                        document.getElementById('update-time').textContent = 'Обновлено: ' + new Date().toLocaleTimeString();

                        // Дедупликация через lastAddedTimestamp — надёжнее, чем строковое сравнение
                        if (data.timestamp !== lastAddedTimestamp) {
                            const exists = currentData.some(item => item.timestamp === data.timestamp);
                            if (!exists) {
                                currentData.push(data);
                                currentData.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
                                if (currentData.length > MAX_CHART_POINTS) {
                                    currentData = currentData.slice(currentData.length - MAX_CHART_POINTS);
                                }
                            }
                            lastAddedTimestamp = data.timestamp;

                            if (Object.keys(charts).length > 0) {
                                renderCharts(currentData);
                                updateTable(currentData);
                            } else {
                                applyFilters();
                            }
                        }
                    }
                })
                .catch(err => {
                    console.warn('Ошибка latest:', err);
                    document.getElementById('connection-indicator').className = 'indicator offline';
                });
        }

        // ================================================================
        // 13. АВАРИИ
        // ================================================================
        function loadAlarms() {
            const start_date = document.getElementById('alarm-start-date').value;
            const end_date = document.getElementById('alarm-end-date').value;
            const param = document.getElementById('alarm-param').value;
            const query = new URLSearchParams({
                start_date: start_date || '',
                end_date: end_date || '',
                param: param || ''
            });
            apiRequest('/api/alarms?' + query.toString())
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById('alarms-body');
                    if (!data || data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="100">Нет аварий</td></tr>';
                        return;
                    }
                    updateAlarmHeaders();
                    data.sort((a,b) => new Date(b.timestamp) - new Date(a.timestamp));
                    const rows = data.slice(0, 100);
                    tbody.innerHTML = rows.map(row => {
                        let html = `<td>${formatLocalTime(row.timestamp)}</td>`;
                        PARAMS.forEach(p => {
                            const val = getParamValue(row, p.id);
                            html += `<td>${val.toFixed(2)}</td>`;
                        });
                        const alarmParams = PARAMS.filter(p => row[p.id + '_status'] === 'ALARM').map(p => p.name);
                        let alarmText = 'Авария';
                        if (alarmParams.length > 0) {
                            const display = alarmParams.slice(0, 3).join(', ');
                            const extra = alarmParams.length > 3 ? ` +${alarmParams.length - 3}` : '';
                            alarmText += ` (${display}${extra})`;
                        }
                        html += `<td><span class="status-cell alarm">${alarmText}</span></td>`;
                        return `<tr>${html}</tr>`;
                    }).join('');
                })
                .catch(err => {
                    console.warn('Ошибка загрузки аварий:', err);
                    document.getElementById('alarms-body').innerHTML = '<tr><td colspan="100">Ошибка загрузки</td></tr>';
                });
        }

        function updateAlarmHeaders() {
            const row = document.getElementById('alarm-headers-row');
            if (!row) return;
            let html = '<th>Время</th>';
            PARAMS.forEach(p => { html += `<th>${p.name}</th>`; });
            html += '<th>Статус</th>';
            row.innerHTML = html;
        }

        function exportAlarmsCSV() {
            const start_date = document.getElementById('alarm-start-date').value;
            const end_date = document.getElementById('alarm-end-date').value;
            const fields = ['timestamp', ...PARAM_IDS, 'status'];
            const query = new URLSearchParams({
                start_date: start_date || '',
                end_date: end_date || '',
                status: 'ALARM',
                fields: fields.join(',')
            });
            window.location.href = '/api/export?' + query.toString();
        }

        // ================================================================
        // 14. СТАТИСТИКА
        // ================================================================
        function loadStats() {
            const start_date = document.getElementById('stats-start-date').value;
            const end_date = document.getElementById('stats-end-date').value;
            const query = new URLSearchParams({
                start_date: start_date || '',
                end_date: end_date || ''
            });
            apiRequest('/api/stats?' + query.toString())
                .then(res => res.json())
                .then(data => {
                    if (!data || Object.keys(data).length === 0) {
                        document.getElementById('stat-records').textContent = '--';
                        document.getElementById('stat-alarms').textContent = '--';
                        document.getElementById('stat-warnings').textContent = '--';
                        document.getElementById('stats-alarms-by-param').innerHTML = '<tr><td colspan="2">Нет данных</td></tr>';
                        document.getElementById('stats-values').innerHTML = '<tr><td colspan="4">Нет данных</td></tr>';
                        if (chartAlarmsByDay) { chartAlarmsByDay.destroy(); chartAlarmsByDay = null; }
                        return;
                    }
                    document.getElementById('stat-records').textContent = data.total_records || 0;
                    document.getElementById('stat-alarms').textContent = data.total_alarms || 0;
                    document.getElementById('stat-warnings').textContent = data.total_warnings || 0;

                    const tbody1 = document.getElementById('stats-alarms-by-param');
                    const alarmParams = data.alarms_by_param || {};
                    let rows1 = '';
                    PARAMS.forEach(p => {
                        rows1 += `<tr><td>${p.name}</td><td>${alarmParams[p.id] || 0}</td></tr>`;
                    });
                    tbody1.innerHTML = rows1;

                    const tbody2 = document.getElementById('stats-values');
                    const stats = data.stats_by_param || {};
                    let rows2 = '';
                    PARAMS.forEach(p => {
                        const s = stats[p.id];
                        if (s) {
                            rows2 += `<tr><td>${p.name}</td><td>${s.min.toFixed(2)}</td><td>${s.max.toFixed(2)}</td><td>${s.avg.toFixed(2)}</td></tr>`;
                        } else {
                            rows2 += `<tr><td>${p.name}</td><td>--</td><td>--</td><td>--</td></tr>`;
                        }
                    });
                    tbody2.innerHTML = rows2;

                    const alarmsByDay = data.alarms_by_day || [];
                    const labels = alarmsByDay.map(d => d.date);
                    const counts = alarmsByDay.map(d => d.count);
                    const ctx = document.getElementById('chart-alarms-by-day').getContext('2d');
                    if (chartAlarmsByDay) chartAlarmsByDay.destroy();
                    if (labels.length > 0) {
                        chartAlarmsByDay = new Chart(ctx, {
                            type: 'bar',
                            data: {
                                labels: labels,
                                datasets: [{
                                    label: 'Количество аварий',
                                    data: counts,
                                    backgroundColor: '#e74c3c',
                                    borderColor: '#c0392b',
                                    borderWidth: 1
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: true,
                                scales: {
                                    y: { beginAtZero: true, title: { display: true, text: 'Число аварий' } },
                                    x: { title: { display: true, text: 'Дата' } }
                                }
                            }
                        });
                    } else {
                        chartAlarmsByDay = null;
                    }
                })
                .catch(err => {
                    console.warn('Ошибка загрузки статистики:', err);
                });
        }

        // ================================================================
        // 15. ИСТОРИЯ ПОРОГОВ
        // ================================================================
        function loadThresholdsHistory() {
            apiRequest('/api/thresholds/history')
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById('history-thresholds-body');
                    if (!data || data.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="2">Нет записей</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.map(item => {
                        const ts = new Date(item.timestamp).toLocaleString();
                        const snapshot = item.snapshot;
                        let changes = '';
                        if (snapshot.params) {
                            changes = snapshot.params.map(p =>
                                `${p.name}: пред. ${p.warning_low || p.warning_high || '—'}, авар. ${p.alarm_low || p.alarm_high || '—'}`
                            ).join('; ');
                        }
                        return `<tr><td>${ts}</td><td>${changes || 'Изменение конфигурации'}</td></tr>`;
                    }).join('');
                })
                .catch(err => {
                    console.warn('Ошибка загрузки истории порогов:', err);
                    document.getElementById('history-thresholds-body').innerHTML = '<tr><td colspan="2">Ошибка загрузки</td></tr>';
                });
        }

        // ================================================================
        // 16. ЭКСПОРТ
        // ================================================================
        function openExportModal() {
            document.getElementById('export-modal').classList.add('active');
            document.getElementById('export-start-date').value = document.getElementById('start-date').value;
            document.getElementById('export-end-date').value = document.getElementById('end-date').value;
            document.getElementById('export-status').value = document.getElementById('status-filter').value;
        }

        function closeExportModal() {
            document.getElementById('export-modal').classList.remove('active');
        }

        document.getElementById('export-modal').addEventListener('click', function(e) {
            if (e.target === this) closeExportModal();
        });

        function exportWithOptions() {
            let start_date = document.getElementById('export-start-date').value;
            let end_date = document.getElementById('export-end-date').value;
            if (start_date) {
                const dt = new Date(start_date);
                start_date = dt.toISOString();
            }
            if (end_date) {
                const dt = new Date(end_date);
                end_date = dt.toISOString();
            }
            const status = document.getElementById('export-status').value;
            const fields = ['timestamp'];
            document.querySelectorAll('.export-param:checked').forEach(cb => {
                fields.push(cb.dataset.field);
            });
            if (!fields.includes('status')) fields.push('status');
            const query = new URLSearchParams({
                start_date: start_date || '',
                end_date: end_date || '',
                status: status || 'ALL',
                fields: fields.join(',')
            });
            closeExportModal();
            window.location.href = '/api/export?' + query.toString();
        }

        function exportAsExcel() {
            const start_date = document.getElementById('export-start-date').value;
            const end_date = document.getElementById('export-end-date').value;
            const status = document.getElementById('export-status').value;
            const fields = ['timestamp'];
            document.querySelectorAll('.export-param:checked').forEach(cb => {
                fields.push(cb.dataset.field);
            });
            if (!fields.includes('status')) fields.push('status');
            const query = new URLSearchParams({
                start_date: start_date || '',
                end_date: end_date || '',
                status: status || 'ALL',
                fields: fields.join(',')
            });
            fetch('/api/export?' + query.toString())
                .then(res => res.text())
                .then(csv => {
                    const lines = csv.trim().split('\n');
                    if (lines.length < 2) {
                        alert('Нет данных для экспорта');
                        return;
                    }
                    const headers = lines[0].split(',');
                    const data = lines.slice(1).map(line => {
                        const values = line.split(',');
                        const obj = {};
                        headers.forEach((h, i) => obj[h] = values[i] || '');
                        return obj;
                    });
                    const wb = XLSX.utils.book_new();
                    const ws = XLSX.utils.json_to_sheet(data);
                    XLSX.utils.book_append_sheet(wb, ws, "Data");
                    XLSX.writeFile(wb, `opc_data_${new Date().toISOString().slice(0,10)}.xlsx`);
                    closeExportModal();
                })
                .catch(err => alert('Ошибка: '+err));
        }

        // ================================================================
        // 17. РЕДАКТИРОВАНИЕ ПОРОГОВ
        // ================================================================
        function openThresholdsEditor() {
            const modal = document.getElementById('thresholds-modal');
            modal.classList.add('active');
            apiRequest('/api/thresholds')
                .then(res => res.json())
                .then(data => {
                    const form = document.getElementById('thresholds-form');
                    form.innerHTML = '';
                    PARAMS.forEach(p => {
                        const t = data[p.id] || {};
                        const div = document.createElement('div');
                        div.className = 'param-threshold';
                        div.innerHTML = `
                            <strong>${p.name}</strong> (${p.unit || ''})<br>
                            <label>⚠️ Пред. нижний: <input type="number" step="any" id="warn_low_${p.id}" value="${t.warning_low ?? ''}"></label>
                            <label>🚨 Авар. нижний: <input type="number" step="any" id="alarm_low_${p.id}" value="${t.alarm_low ?? ''}"></label>
                            <label>⚠️ Пред. верхний: <input type="number" step="any" id="warn_high_${p.id}" value="${t.warning_high ?? ''}"></label>
                            <label>🚨 Авар. верхний: <input type="number" step="any" id="alarm_high_${p.id}" value="${t.alarm_high ?? ''}"></label>
                        `;
                        form.appendChild(div);
                    });
                });
        }

        function closeThresholdsEditor() {
            document.getElementById('thresholds-modal').classList.remove('active');
        }

        function saveThresholds() {
            const updates = [];
            PARAMS.forEach(p => {
                const warn_low = parseFloat(document.getElementById(`warn_low_${p.id}`).value);
                const alarm_low = parseFloat(document.getElementById(`alarm_low_${p.id}`).value);
                const warn_high = parseFloat(document.getElementById(`warn_high_${p.id}`).value);
                const alarm_high = parseFloat(document.getElementById(`alarm_high_${p.id}`).value);
                updates.push({
                    param_id: p.id,
                    warning_low: isNaN(warn_low) ? null : warn_low,
                    alarm_low: isNaN(alarm_low) ? null : alarm_low,
                    warning_high: isNaN(warn_high) ? null : warn_high,
                    alarm_high: isNaN(alarm_high) ? null : alarm_high
                });
            });
            Promise.all(updates.map(u =>
                apiRequest('/api/thresholds/update', {
                    method: 'POST',
                    body: JSON.stringify(u)
                })
            )).then(() => {
                alert('✅ Пороги обновлены!');
                closeThresholdsEditor();
                applyFilters();
                updateLatest();
            }).catch(err => alert('❌ Ошибка: '+err));
        }

        // ================================================================
        // 18. УВЕДОМЛЕНИЯ
        // ================================================================
        function requestNotificationPermission() {
            if (!("Notification" in window)) return;
            if (Notification.permission === "granted") return;
            if (Notification.permission !== "denied") {
                Notification.requestPermission();
            }
        }

        function sendBrowserNotification(title, body) {
            if (Notification.permission === "granted") {
                new Notification(title, { body: body, icon: 'https://via.placeholder.com/48/ff0000/fff?text=!' });
            }
        }

        requestNotificationPermission();

        // ================================================================
        // 19. ВКЛАДКИ
        // ================================================================
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                const tabId = this.dataset.tab;
                document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
                document.getElementById('tab-' + tabId).classList.add('active');
                if (tabId === 'alarms') loadAlarms();
                else if (tabId === 'stats') loadStats();
                else if (tabId === 'history') loadThresholdsHistory();
            });
        });

        // ================================================================
        // 20. ТЁМНАЯ ТЕМА
        // ================================================================
        function toggleTheme() {
            document.body.classList.toggle('dark');
            saveFilters();
        }

        // ================================================================
        // 21. ЗВУК
        // ================================================================
        document.getElementById('enable-sound-btn').addEventListener('click', function() {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                if (ctx.state === 'suspended') ctx.resume();
                ctx.close();
                localStorage.setItem('sound_allowed', 'true');
            } catch(e) {}
            document.getElementById('sound-overlay').classList.add('hidden');
        });
        if (localStorage.getItem('sound_allowed') === 'true') {
            document.getElementById('sound-overlay').classList.add('hidden');
        }

        // ================================================================
        // 22. ОБРАБОТЧИКИ
        // ================================================================
        document.getElementById('temp-unit').addEventListener('change', function() {
            if (currentData.length > 0) {
                renderCharts(currentData);
                updateTable(currentData);
            }
            updateLatest();
            saveFilters();
        });
        document.getElementById('press-unit').addEventListener('change', function() {
            if (currentData.length > 0) {
                renderCharts(currentData);
                updateTable(currentData);
            }
            updateLatest();
            saveFilters();
        });
        document.querySelectorAll('.filters input, .filters select').forEach(el => {
            el.addEventListener('change', saveFilters);
        });

        let updateIndicator = document.getElementById('update-indicator');
        let blinkTimeout;

        function blinkUpdate() {
            updateIndicator.style.opacity = '0.1';
            clearTimeout(blinkTimeout);
            blinkTimeout = setTimeout(() => { updateIndicator.style.opacity = '1'; }, 200);
        }

        const originalApply = applyFilters;
        applyFilters = function() {
            blinkUpdate();
            originalApply();
        };
        const originalUpdate = updateLatest;
        updateLatest = function() {
            blinkUpdate();
            originalUpdate();
        };

        // ================================================================
        // 23. WEBSOCKET — отключён (на бэкенде нет Flask-SocketIO)
        // ================================================================
        // Используем polling через setInterval в initApp() — обновление каждые 5 сек.
        // Если Socket.IO будет добавлен на бэкенд, вернуть блок io() сюда.

        // ================================================================
        // 24. ИНИЦИАЛИЗАЦИЯ
        // ================================================================
        async function initApp() {
            await loadParamsAndThresholds();
            buildUI();
            loadFilters();
            applyFilters();
            updateLatest();
            setInterval(updateLatest, 5000); // автообновление каждые 5 секунд (синхронно с client)
        }

        // Проверка аутентификации при загрузке
        if (checkAuth()) {
            initApp();
        }

        // Обработка Enter в форме логина
        document.getElementById('login-form').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('login-btn').click();
            }
        });

        // ================================================================
        // 25. EVENT DELEGATION (CSP: заменяет inline onclick-обработчики)
        // ================================================================
        const ACTION_HANDLERS = {
            'refresh': applyFilters,
            'open-thresholds': openThresholdsEditor,
            'toggle-theme': toggleTheme,
            'logout': logout,
            'apply-filters': () => { applyFilters(); saveFilters(); },
            'open-export': openExportModal,
            'load-alarms': loadAlarms,
            'export-alarms': exportAlarmsCSV,
            'load-stats': loadStats,
            'load-thresholds-history': loadThresholdsHistory,
            'close-export': closeExportModal,
            'export-csv': exportWithOptions,
            'export-excel': exportAsExcel,
            'save-thresholds': saveThresholds,
            'close-thresholds': closeThresholdsEditor,
        };

        document.addEventListener('click', function(e) {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const handler = ACTION_HANDLERS[btn.dataset.action];
            if (handler) {
                e.preventDefault();
                handler();
            }
        });

        document.getElementById('login-form').addEventListener('submit', login);