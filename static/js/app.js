/**
 * Historical Stock Market Simulator - Client JavaScript
 */

class StockSimulator {
    constructor() {
        this.socket = null;
        this.chart = null;
        this.chartLabels = [];
        this.chartData = [];
        this.currentPrices = {};
        this.previousPrices = {};
        this.portfolio = { cash: 100, holdings: {} };
        this.currentTicker = null;
        this.tradeType = null;
        this.currentYear = null;
        this.headlineCache = {};
        this.activeIndexTicker = '^DJI';
        
        this.init();
    }
    
    init() {
        this.connectSocket();
        this.initChart();
        this.bindEvents();
    }
    
    connectSocket() {
        // Auto-detect server URL from current location
        // Works on localhost, localhost:5001, and public URLs
        this.socket = io({
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.socket.emit('join_room', {
                room_code: window.roomCode,
                username: window.username
            });
        });
        
        this.socket.on('joined_room', (data) => {
            console.log('Joined room:', data);
            this.updateAdminControls(data.is_admin);
        });
        
        this.socket.on('game_state_update', (data) => {
            this.updateGameState(data);
        });
        
        this.socket.on('leaderboard_update', (data) => {
            this.updateLeaderboard(data.leaderboard);
        });
        
        this.socket.on('trade_success', (data) => {
            this.showTradeNotification(data);
            this.requestPortfolioUpdate();
        });
        
        this.socket.on('error', (data) => {
            this.showError(data.message);
        });
        
        this.socket.on('market_event', (data) => {
            this.handleMarketEvent(data);
        });

        this.socket.on('market_panic', (data) => {
            this.handleMarketPanic(data);
        });

        this.socket.on('new_headline', (data) => {
            this.updateHeadlineTicker(data);
        });

        this.socket.on('info', (data) => {
            if (data && data.message) {
                this.showInfo(data.message);
            }
        });

        this.socket.on('insider_rumor', (data) => {
            this.updateRumorTicker(data);
        });

        this.socket.on('insider_status_updated', (data) => {
            this.handleInsiderStatusUpdate(data);
        });

        this.socket.on('sec_penalty', (data) => {
            this.handleSECPenalty(data);
        });
    }
    
    initChart() {
        const ctx = document.getElementById('sp500-chart').getContext('2d');
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'S&P 500',
                    data: [],
                    borderColor: '#58a6ff',
                    backgroundColor: 'rgba(88, 166, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#161b22',
                        borderColor: '#30363d',
                        borderWidth: 1,
                        titleFont: { family: 'Inter' },
                        bodyFont: { family: 'JetBrains Mono' }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: {
                            color: 'rgba(48, 54, 61, 0.5)'
                        },
                        ticks: {
                            color: '#8b949e',
                            maxTicksLimit: 8,
                            font: { family: 'JetBrains Mono', size: 10 }
                        }
                    },
                    y: {
                        display: true,
                        grid: {
                            color: 'rgba(48, 54, 61, 0.5)'
                        },
                        ticks: {
                            color: '#8b949e',
                            font: { family: 'JetBrains Mono', size: 10 },
                            callback: (value) => '$' + value.toLocaleString()
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
        
        // Load initial chart data
        this.loadChartData();
    }
    
    async loadChartData() {
        try {
            const response = await fetch(`/api/room/${window.roomCode}`);
            const roomData = await response.json();

            // Seed chart with current room date if a value exists.
            const currentDate = roomData.current_date;
            const activePrice = roomData.prices ? roomData.prices[this.activeIndexTicker] : null;
            this.updateChart(currentDate, activePrice);
        } catch (error) {
            console.error('Error loading chart data:', error);
        }
    }
    
    bindEvents() {
        // Buy/Sell buttons
        document.querySelectorAll('.btn-buy').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ticker = e.target.dataset.ticker;
                this.openTradeModal(ticker, 'buy');
            });
        });
        
        document.querySelectorAll('.btn-sell').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const ticker = e.target.dataset.ticker;
                this.openTradeModal(ticker, 'sell');
            });
        });
        
        // Modal events
        document.getElementById('modal-close').addEventListener('click', () => {
            this.closeModal();
        });
        
        document.getElementById('modal-cancel').addEventListener('click', () => {
            this.closeModal();
        });
        
        document.getElementById('modal-confirm').addEventListener('click', () => {
            this.executeTrade();
        });
        
        document.getElementById('dollar-input').addEventListener('input', (e) => {
            this.updateTradeTotal();
        });
        
        // Admin controls
        if (window.isAdmin) {
            document.getElementById('play-pause-btn').addEventListener('click', () => {
                this.socket.emit('admin_toggle_play');
            });
            
            document.getElementById('set-date-btn').addEventListener('click', () => {
                const date = document.getElementById('date-picker').value;
                this.socket.emit('admin_set_date', { date });
            });
            
            document.getElementById('reset-btn').addEventListener('click', () => {
                if (confirm('Are you sure you want to reset the game? All players will lose their progress.')) {
                    this.socket.emit('admin_reset');
                }
            });

            const insiderUsernameInput = document.getElementById('insider-username');
            const setInsiderButton = document.getElementById('set-insider-btn');
            const revokeInsiderButton = document.getElementById('revoke-insider-btn');

            if (setInsiderButton && insiderUsernameInput) {
                setInsiderButton.addEventListener('click', () => {
                    const target = insiderUsernameInput.value.trim();
                    if (!target) {
                        this.showError('Enter a username to grant insider access.');
                        return;
                    }
                    this.socket.emit('admin_set_insider', {
                        username: target,
                        is_insider: true
                    });
                });
            }

            if (revokeInsiderButton && insiderUsernameInput) {
                revokeInsiderButton.addEventListener('click', () => {
                    const target = insiderUsernameInput.value.trim();
                    if (!target) {
                        this.showError('Enter a username to revoke insider access.');
                        return;
                    }
                    this.socket.emit('admin_set_insider', {
                        username: target,
                        is_insider: false
                    });
                });
            }
        }
        
        // Close modal on outside click
        document.getElementById('trade-modal').addEventListener('click', (e) => {
            if (e.target.id === 'trade-modal') {
                this.closeModal();
            }
        });

    }
    
    updateGameState(data) {
        // Update date
        document.getElementById('current-date').textContent = data.current_date;
        this.updateHeadlineForDate(data.current_date);
        
        // Update game status
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');
        
        if (data.game_state === 'playing') {
            statusIndicator.classList.add('playing');
            statusText.textContent = 'Playing';
            
            if (window.isAdmin) {
                document.getElementById('play-pause-btn').innerHTML = 
                    '<span class="btn-icon">⏸</span> Pause';
            }
        } else {
            statusIndicator.classList.remove('playing');
            statusText.textContent = 'Paused';
            
            if (window.isAdmin) {
                document.getElementById('play-pause-btn').innerHTML = 
                    '<span class="btn-icon">▶</span> Play';
            }
        }
        
        // Update prices
        this.updatePrices(data.prices);

        this.updateActiveIndex(data.active_index);

        // Add latest active-index point
        this.updateChart(data.current_date, data.active_index ? data.active_index.value : null);
        
        // Update available tickers
        if (data.available_tickers) {
            this.updateAvailableTickers(data.available_tickers);
        }

        if (data.panic_mode) {
            this.setPanicVisuals(true);
        } else {
            this.setPanicVisuals(false);
        }
        
        // Update portfolio
        this.requestPortfolioUpdate();
    }
    
    updatePrices(prices) {
        // Store previous prices for change calculation
        this.previousPrices = { ...this.currentPrices };
        this.currentPrices = prices;
        
        window.tickers.forEach(ticker => {
            const priceEl = document.getElementById(`price-${ticker}`);
            const changeEl = document.getElementById(`change-${ticker}`);
            const statusEl = document.getElementById(`status-${ticker}`);
            const buyBtn = document.querySelector(`.btn-buy[data-ticker="${ticker}"]`);
            const sellBtn = document.querySelector(`.btn-sell[data-ticker="${ticker}"]`);
            
            const price = prices[ticker];
            
            if (price === undefined || price === null) {
                priceEl.textContent = 'N/A';
                changeEl.textContent = '';
                statusEl.textContent = 'Not yet IPO\'d';
                statusEl.className = 'stock-status unavailable';
                buyBtn.disabled = true;
                sellBtn.disabled = true;
            } else {
                priceEl.textContent = this.formatCurrency(price);
                
                // Calculate change
                const prevPrice = this.previousPrices[ticker];
                if (prevPrice && prevPrice !== price) {
                    const change = ((price - prevPrice) / prevPrice) * 100;
                    changeEl.textContent = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
                    changeEl.className = 'price-change ' + (change >= 0 ? 'positive' : 'negative');
                    
                    // Flash animation
                    const card = document.querySelector(`.stock-card[data-ticker="${ticker}"]`);
                    card.classList.add(change >= 0 ? 'price-flash-up' : 'price-flash-down');
                    setTimeout(() => {
                        card.classList.remove('price-flash-up', 'price-flash-down');
                    }, 500);
                }
                
                statusEl.textContent = '';
                statusEl.className = 'stock-status';
                buyBtn.disabled = false;
                sellBtn.disabled = false;
            }
        });
        
    }
    
    updateChart(date, sp500Price) {
        if (!date || sp500Price === undefined || sp500Price === null) {
            return;
        }

        const lastLabel = this.chartLabels[this.chartLabels.length - 1];
        if (lastLabel === date) {
            this.chartData[this.chartData.length - 1] = sp500Price;
        } else {
            this.chartLabels.push(date);
            this.chartData.push(sp500Price);
        }

        // Keep chart fast and readable.
        if (this.chartLabels.length > 100) {
            this.chartLabels = this.chartLabels.slice(-100);
            this.chartData = this.chartData.slice(-100);
        }

        this.chart.data.labels = this.chartLabels;
        this.chart.data.datasets[0].data = this.chartData;
        this.chart.update('none');
    }

    updateActiveIndex(activeIndex) {
        if (!activeIndex || !activeIndex.ticker) {
            return;
        }

        const tickerChanged = this.activeIndexTicker !== activeIndex.ticker;
        this.activeIndexTicker = activeIndex.ticker;

        const titleEl = document.getElementById('index-title');
        const valueEl = document.getElementById('index-value');
        const legendEl = document.getElementById('chart-legend-text');

        const displayName = activeIndex.ticker === '^DJI' ? 'Dow Jones' : 'S&P 500';
        titleEl.textContent = `${displayName} Progress`;
        legendEl.textContent = `📊 Historical ${displayName} Index`;
        valueEl.textContent = activeIndex.value ? this.formatCurrency(activeIndex.value) : '--';

        if (tickerChanged) {
            this.chartLabels = [];
            this.chartData = [];
            this.chart.data.labels = [];
            this.chart.data.datasets[0].data = [];
            this.chart.update('none');
        }
    }
    
    async requestPortfolioUpdate() {
        try {
            const response = await fetch(`/api/player/${window.roomCode}/${window.username}`);
            const data = await response.json();
            this.updatePortfolio(data);
        } catch (error) {
            console.error('Error fetching portfolio:', error);
        }
    }
    
    updatePortfolio(data) {
        this.portfolio = { cash: data.cash, holdings: data.holdings };
        
        // Update cash
        document.getElementById('cash-balance').textContent = this.formatCurrency(data.cash);
        
        // Calculate holdings value
        let holdingsValue = 0;
        for (const [ticker, shares] of Object.entries(data.holdings)) {
            const price = this.currentPrices[ticker];
            if (price) {
                holdingsValue += shares * price;
            }
        }
        
        document.getElementById('holdings-value').textContent = this.formatCurrency(holdingsValue);
        document.getElementById('net-worth').textContent = this.formatCurrency(data.net_worth);
        
        // Update holdings list
        const holdingsList = document.getElementById('holdings-list');
        
        if (Object.keys(data.holdings).length === 0) {
            holdingsList.innerHTML = '<p class="empty-message">No holdings yet</p>';
        } else {
            let html = '';
            for (const [ticker, shares] of Object.entries(data.holdings)) {
                const price = this.currentPrices[ticker] || 0;
                const value = shares * price;
                html += `
                    <div class="holding-item">
                        <span class="holding-ticker">${ticker}</span>
                        <span class="holding-shares">${shares.toFixed(2)} shares</span>
                        <span class="holding-value">${this.formatCurrency(value)}</span>
                    </div>
                `;
            }
            holdingsList.innerHTML = html;
        }
    }
    
    updateLeaderboard(leaderboard) {
        const list = document.getElementById('leaderboard-list');
        
        let html = '';
        leaderboard.forEach((entry, index) => {
            const isCurrentUser = entry.username === window.username;
            const rankClass = index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'other';
            
            html += `
                <div class="leaderboard-item">
                    <span class="leaderboard-rank ${rankClass}">${index + 1}</span>
                    <div class="leaderboard-info">
                        <span class="leaderboard-name ${isCurrentUser ? 'you' : ''}">
                            ${entry.username}${isCurrentUser ? ' (You)' : ''}
                        </span>
                    </div>
                    <span class="leaderboard-worth">${this.formatCurrency(entry.net_worth)}</span>
                </div>
            `;
        });
        
        list.innerHTML = html;
    }
    
    openTradeModal(ticker, type) {
        this.currentTicker = ticker;
        this.tradeType = type;
        
        const price = this.currentPrices[ticker];
        if (!price) {
            this.showError('Stock not available for trading');
            return;
        }
        
        document.getElementById('modal-title').textContent = 
            type === 'buy' ? `Buy ${ticker}` : `Sell ${ticker}`;
        document.getElementById('modal-ticker').textContent = ticker;
        document.getElementById('modal-price').textContent = this.formatCurrency(price);
        
        const dollarInput = document.getElementById('dollar-input');
        const inputLabel = document.getElementById('trade-input-label');
        const totalLabel = document.getElementById('trade-total-label');

        if (type === 'buy') {
            inputLabel.textContent = 'Dollar Amount';
            totalLabel.textContent = 'Estimated Shares:';
            dollarInput.value = Math.min(100, this.portfolio.cash || 100);
            dollarInput.max = this.portfolio.cash || 0;
            dollarInput.min = 1;
            dollarInput.step = 0.01;
        } else {
            inputLabel.textContent = 'Number of Shares';
            totalLabel.textContent = 'Total Value:';
            const ownedShares = this.portfolio.holdings[ticker] || 0;
            dollarInput.value = ownedShares.toFixed(2);
            dollarInput.max = ownedShares;
            dollarInput.min = 0.01;
            dollarInput.step = 0.01;
        }
        
        this.updateTradeTotal();
        
        // Update button style
        const confirmBtn = document.getElementById('modal-confirm');
        confirmBtn.className = 'btn btn-confirm ' + type;
        confirmBtn.textContent = type === 'buy' ? 'Buy' : 'Sell';
        
        document.getElementById('trade-modal').classList.add('active');
    }
    
    closeModal() {
        document.getElementById('trade-modal').classList.remove('active');
        this.currentTicker = null;
        this.tradeType = null;
    }
    
    updateTradeTotal() {
        const amount = parseFloat(document.getElementById('dollar-input').value) || 0;
        const price = this.currentPrices[this.currentTicker];
        let displayValue = '0.00';

        if (this.tradeType === 'buy') {
            const shares = price ? amount / price : 0;
            displayValue = shares > 0 ? shares.toFixed(8) : '0.00';
        } else {
            const total = price ? amount * price : 0;
            displayValue = price ? this.formatCurrency(total) : '0.00';
        }

        document.getElementById('trade-total').textContent = displayValue;
    }
    
    executeTrade() {
        const amount = parseFloat(document.getElementById('dollar-input').value);
        
        if (!amount || amount <= 0) {
            const message = this.tradeType === 'buy'
                ? 'Please enter a valid dollar amount'
                : 'Please enter a valid share amount';
            this.showError(message);
            return;
        }
        
        if (this.tradeType === 'buy') {
            this.socket.emit('buy_stock', {
                ticker: this.currentTicker,
                amount: amount
            });
        } else {
            this.socket.emit('sell_stock', {
                ticker: this.currentTicker,
                shares: amount
            });
        }
        
        this.closeModal();
    }
    
    showTradeNotification(data) {
        const message = data.action === 'buy' 
            ? `Bought ${data.shares} shares of ${data.ticker} for ${this.formatCurrency(data.total)}`
            : `Sold ${data.shares} shares of ${data.ticker} for ${this.formatCurrency(data.total)}`;
        
        // Show temporary notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${data.action === 'buy' ? '#238636' : '#da3633'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 2000;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    showError(message) {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #da3633;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 2000;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    handleSECPenalty(data) {
        this.showError(data.message || 'SEC enforcement penalty applied.');
        if (data && typeof data.cash_remaining === 'number') {
            document.getElementById('cash-balance').textContent = this.formatCurrency(data.cash_remaining);
            this.requestPortfolioUpdate();
        }
    }

    showInfo(message) {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #1f6feb;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 2000;
            animation: slideIn 0.3s ease-out;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    updateRumorTicker(data) {
        const wrapper = document.getElementById('rumor-wrap');
        const rumorText = document.getElementById('rumor-text');
        if (!wrapper || !rumorText) {
            return;
        }

        if (window.isInsider && data && data.headline) {
            wrapper.classList.remove('hidden');
            rumorText.textContent = data.headline;
            return;
        }

        wrapper.classList.add('hidden');
    }

    handleInsiderStatusUpdate(data) {
        if (data && typeof data.is_insider !== 'undefined') {
            window.isInsider = data.is_insider;

            const headerRight = document.querySelector('.header-right');
            const existingBadge = document.querySelector('.insider-badge');

            if (window.isInsider) {
                if (!existingBadge && headerRight) {
                    const badge = document.createElement('span');
                    badge.className = 'insider-badge';
                    badge.textContent = 'Insider';
                    headerRight.appendChild(badge);
                }
            } else if (existingBadge) {
                existingBadge.remove();
            }
        }

        if (data && data.message) {
            this.showInfo(data.message);
        }
    }

    handleMarketPanic(data) {
        this.setPanicVisuals(true);

        if (data && data.message) {
            this.showError(data.message);
        }
    }

    setPanicVisuals(enabled) {
        const chartContainer = document.querySelector('.chart-container');
        const tickerWrap = document.querySelector('.ticker-wrap');

        [chartContainer, tickerWrap].forEach(el => {
            if (!el) return;
            if (enabled) {
                el.classList.add('panic-mode');
            } else {
                el.classList.remove('panic-mode');
            }
        });
    }

    handleMarketEvent(data) {
        if (data.type === 'sp500_launch') {
            // Show notification
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
                color: white;
                padding: 30px 50px;
                border-radius: 16px;
                font-size: 24px;
                font-weight: bold;
                z-index: 2000;
                animation: popIn 0.5s ease-out;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            `;
            notification.textContent = '🎉 S&P 500 Launched!';
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.remove();
            }, 5000);
            
            // Refresh available stocks
            this.updateStockList();
            return;
        }

    }

    
    updateStockList() {
        // This will be called to refresh the stock dropdown
        // The game_state_update should contain available tickers
    }
    
    updateAvailableTickers(tickers) {
        // Update which stocks are available for trading
        window.tickers.forEach(ticker => {
            const buyBtn = document.querySelector(`.btn-buy[data-ticker="${ticker}"]`);
            const sellBtn = document.querySelector(`.btn-sell[data-ticker="${ticker}"]`);
            const isAvailable = tickers.includes(ticker);
            
            if (buyBtn) {
                buyBtn.disabled = !isAvailable;
                buyBtn.style.opacity = isAvailable ? '1' : '0.5';
            }
            if (sellBtn) {
                sellBtn.disabled = !isAvailable;
                sellBtn.style.opacity = isAvailable ? '1' : '0.5';
            }
        });
    }
    
    updateAdminControls(isAdmin) {
        // This is handled by the template, but we can add dynamic behavior here
    }

    async updateHeadlineForDate(dateString) {
        if (!dateString || dateString.length < 4) {
            return;
        }

        const year = dateString.slice(0, 4);
        if (this.currentYear === year) {
            return;
        }
        this.currentYear = year;

        const yearLabel = document.getElementById('news-year-label');
        const headlineEl = document.getElementById('headline-text');
        const linkEl = document.getElementById('headline-link');
        const errorEl = document.getElementById('headline-error');

        yearLabel.textContent = `Year: ${year}`;
        if (errorEl) {
            errorEl.textContent = '';
        }
        if (linkEl) {
            linkEl.style.display = 'none';
        }

        if (this.headlineCache[year]) {
            this.renderHeadline(this.headlineCache[year]);
            return;
        }

        headlineEl.textContent = 'Loading headline...';

        try {
            const response = await fetch(`/api/headline/${year}`);
            const payload = await response.json();
            this.headlineCache[year] = payload;
            this.renderHeadline(payload);
        } catch (error) {
            headlineEl.textContent = 'Headline unavailable right now.';
            errorEl.textContent = 'Could not load historical headline.';
        }
    }

    renderHeadline(payload) {
        const headlineEl = document.getElementById('headline-text');
        const linkEl = document.getElementById('headline-link');
        const errorEl = document.getElementById('headline-error');

        if (payload && payload.headline) {
            headlineEl.textContent = payload.headline;
            if (payload.url && linkEl) {
                linkEl.href = payload.url;
                linkEl.style.display = 'inline-block';
            } else if (linkEl) {
                linkEl.style.display = 'none';
            }
            if (errorEl) {
                errorEl.textContent = payload.error || '';
            }
            return;
        }

        headlineEl.textContent = 'No headline available for this year.';
        if (linkEl) {
            linkEl.style.display = 'none';
        }
        if (errorEl) {
            errorEl.textContent = payload && payload.error ? payload.error : '';
        }
    }

    updateHeadlineTicker(data) {
        const headlineEl = document.getElementById('headline-text');
        const yearEl = document.getElementById('news-year-label');
        if (!headlineEl) {
            return;
        }

        headlineEl.textContent = data && data.headline ? data.headline : 'Headline unavailable right now.';
        if (yearEl) {
            yearEl.textContent = data && data.year ? `Year: ${data.year}` : '';
        }
    }
    
    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }
}

// Add slideIn animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.stockSimulator = new StockSimulator();
});