let tradesData = null;
let equityData = null;

// Auto-load CSVs if they exist in the same directory
window.addEventListener('DOMContentLoaded', function () {
    autoLoadCSVs();
});

async function autoLoadCSVs() {
    try {
        // Try to load trades CSV
        const tradesResponse = await fetch('backtest_trades.csv');
        if (tradesResponse.ok) {
            const tradesText = await tradesResponse.text();
            tradesData = parseCSV(tradesText);
            console.log('Auto-loaded trades:', tradesData.length);
        }

        // Try to load equity CSV
        const equityResponse = await fetch('backtest_equity_curve.csv');
        if (equityResponse.ok) {
            const equityText = await equityResponse.text();
            equityData = parseCSV(equityText);
            console.log('Auto-loaded equity:', equityData.length);
        }

        // If both loaded successfully, render dashboard
        if (tradesData && equityData) {
            console.log('Auto-loading successful, rendering dashboard...');
            renderDashboard();
        } else {
            console.log('CSVs not found, waiting for manual upload...');
        }
    } catch (error) {
        console.log('Auto-load failed (files may not exist yet), waiting for manual upload...');
    }
}

function parseCSV(text) {
    const lines = text.trim().split('\n');
    const headers = lines[0].split(',').map(h => h.trim());
    return lines.slice(1).map(line => {
        const values = line.split(',');
        const obj = {};
        headers.forEach((header, i) => {
            obj[header] = values[i]?.trim();
        });
        return obj;
    });
}

function formatCurrency(val) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(val);
}

function formatPercent(val) {
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
}

function renderDashboard() {
    console.log('Rendering dashboard...');

    calculateMetrics();
    renderEquityChart();
    renderTradesChart();
    renderTradesTable();
}

function calculateMetrics() {
    const totalTrades = tradesData.length;
    const winners = tradesData.filter(t => parseFloat(t.pnl) > 0);
    const losers = tradesData.filter(t => parseFloat(t.pnl) <= 0);

    const totalPnL = tradesData.reduce((sum, t) => sum + parseFloat(t.pnl), 0);
    const winRate = (winners.length / totalTrades) * 100;

    const avgWin = winners.length > 0
        ? winners.reduce((sum, t) => sum + parseFloat(t.pnl), 0) / winners.length
        : 0;
    const avgLoss = losers.length > 0
        ? losers.reduce((sum, t) => sum + parseFloat(t.pnl), 0) / losers.length
        : 0;

    const profitFactor = avgLoss !== 0
        ? Math.abs((avgWin * winners.length) / (avgLoss * losers.length))
        : 0;

    let peak = parseFloat(tradesData[0].equity_after);
    let maxDD = 0;
    tradesData.forEach(t => {
        const equity = parseFloat(t.equity_after);
        if (equity > peak) peak = equity;
        const dd = ((peak - equity) / peak) * 100;
        if (dd > maxDD) maxDD = dd;
    });

    const metricsHTML = `
                <div class="metric-card">
                    <div class="metric-label">Total P&L</div>
                    <div class="metric-value">${formatCurrency(totalPnL)}</div>
                </div>
                <div class="metric-card green">
                    <div class="metric-label">Win Rate</div>
                    <div class="metric-value">${winRate.toFixed(1)}%</div>
                    <div class="metric-subtitle">${winners.length}W / ${losers.length}L</div>
                </div>
                <div class="metric-card purple">
                    <div class="metric-label">Profit Factor</div>
                    <div class="metric-value">${profitFactor.toFixed(2)}</div>
                </div>
                <div class="metric-card red">
                    <div class="metric-label">Max Drawdown</div>
                    <div class="metric-value">${maxDD.toFixed(2)}%</div>
                </div>
            `;

    document.getElementById('metrics').innerHTML = metricsHTML;
}

function renderEquityChart() {
    const ctx = document.getElementById('equityChart').getContext('2d');
    const data = equityData.map((row, idx) => ({
        x: idx,
        y: parseFloat(row.equity)
    }));

    new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Equity',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => formatCurrency(context.parsed.y)
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: '#334155' },
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => formatCurrency(value)
                    }
                }
            }
        }
    });
}

function renderTradesChart() {
    const ctx = document.getElementById('tradesChart').getContext('2d');
    const data = tradesData.map((trade, idx) => parseFloat(trade.pnl));
    const colors = data.map(pnl => pnl > 0 ? '#10b981' : '#ef4444');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map((_, idx) => idx + 1),
            datasets: [{
                label: 'P&L',
                data: data,
                backgroundColor: colors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => formatCurrency(context.parsed.y)
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    grid: { color: '#334155' },
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => formatCurrency(value)
                    }
                }
            }
        }
    });
}

function renderTradesTable() {
    const recentTrades = tradesData.slice(-10).reverse();

    let tableHTML = `
                <thead>
                    <tr>
                        <th>Entry Time</th>
                        <th>Exit Time</th>
                        <th style="text-align: right">Entry Price</th>
                        <th style="text-align: right">Exit Price</th>
                        <th style="text-align: right">P&L</th>
                        <th style="text-align: right">P&L %</th>
                        <th>Exit Reason</th>
                    </tr>
                </thead>
                <tbody>
            `;

    recentTrades.forEach(trade => {

        const pnl = parseFloat(trade.pnl);
        const pnlPct = parseFloat(trade.pnl_pct);
        const pnlClass = pnl > 0 ? 'positive' : 'negative';

        tableHTML += `
                    <tr>
                        <td>${new Date(trade.entry_time).toLocaleString()}</td>
                        <td>${new Date(trade.exit_time).toLocaleString()}</td>
                        <td style="text-align: right">$${parseFloat(trade.entry_price).toFixed(5)}</td>
                        <td style="text-align: right">$${parseFloat(trade.exit_price).toFixed(5)}</td>
                        <td style="text-align: right" class="${pnlClass}">${formatCurrency(pnl)}</td>
                        <td style="text-align: right" class="${pnlClass}">${formatPercent(pnlPct)}</td>
                        <td>${trade.exit_reason}</td>
                    </tr>
                `;
    });

    tableHTML += '</tbody>';
    document.getElementById('tradesTable').innerHTML = tableHTML;
}