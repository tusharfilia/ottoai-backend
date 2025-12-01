/**
 * WebSocket Client Example for Live Metrics
 * 
 * This example shows how to connect to the WebSocket endpoint
 * and subscribe to live metrics updates.
 */

class LiveMetricsClient {
    constructor(baseUrl, token) {
        this.baseUrl = baseUrl;
        this.token = token;
        this.ws = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.subscriptions = new Set();
        this.eventHandlers = new Map();
    }

    /**
     * Connect to the WebSocket endpoint
     */
    async connect() {
        try {
            const wsUrl = `${this.baseUrl.replace('http', 'ws')}/ws`;
            this.ws = new WebSocket(wsUrl, [], {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            this.ws.onopen = (event) => {
                console.log('WebSocket connected');
                this.connected = true;
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                
                // Resubscribe to all channels
                this.subscriptions.forEach(channel => {
                    this.subscribe(channel);
                });
                
                this.emit('connected', event);
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.connected = false;
                this.emit('disconnected', event);
                
                // Attempt to reconnect if not a clean close
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.scheduleReconnect();
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };

        } catch (error) {
            console.error('Failed to connect to WebSocket:', error);
            this.emit('error', error);
        }
    }

    /**
     * Disconnect from the WebSocket
     */
    disconnect() {
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        this.connected = false;
    }

    /**
     * Subscribe to a channel for live updates
     */
    subscribe(channel) {
        if (!this.connected) {
            console.warn('WebSocket not connected, queuing subscription:', channel);
            this.subscriptions.add(channel);
            return;
        }

        const message = {
            type: 'subscribe',
            channel: channel
        };

        this.ws.send(JSON.stringify(message));
        this.subscriptions.add(channel);
        console.log('Subscribed to channel:', channel);
    }

    /**
     * Unsubscribe from a channel
     */
    unsubscribe(channel) {
        if (!this.connected) {
            this.subscriptions.delete(channel);
            return;
        }

        const message = {
            type: 'unsubscribe',
            channel: channel
        };

        this.ws.send(JSON.stringify(message));
        this.subscriptions.delete(channel);
        console.log('Unsubscribed from channel:', channel);
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(message) {
        const { type, event, data, channel } = message;

        switch (type) {
            case 'welcome':
                console.log('WebSocket welcome:', message);
                this.emit('welcome', message);
                break;

            case 'ping':
                // Respond to ping with pong
                this.ws.send(JSON.stringify({ type: 'pong' }));
                break;

            case 'subscribe_result':
                console.log('Subscription result:', message);
                this.emit('subscription_result', message);
                break;

            case 'unsubscribe_result':
                console.log('Unsubscription result:', message);
                this.emit('unsubscription_result', message);
                break;

            case 'error':
                console.error('WebSocket error message:', message);
                this.emit('websocket_error', message);
                break;

            case 'system':
                console.log('System message:', message);
                this.emit('system', message);
                break;

            default:
                // Handle live metrics events
                if (event && data) {
                    this.emit('metrics_update', { event, data, channel });
                }
                break;
        }
    }

    /**
     * Schedule a reconnection attempt
     */
    scheduleReconnect() {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (!this.connected) {
                this.connect();
            }
        }, delay);
    }

    /**
     * Add event listener
     */
    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }

    /**
     * Remove event listener
     */
    off(event, handler) {
        if (this.eventHandlers.has(event)) {
            const handlers = this.eventHandlers.get(event);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Emit event to all listeners
     */
    emit(event, data) {
        if (this.eventHandlers.has(event)) {
            this.eventHandlers.get(event).forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error('Error in event handler:', error);
                }
            });
        }
    }
}

/**
 * Live Metrics Dashboard Integration
 * 
 * Example of how to integrate live metrics into a dashboard
 */
class LiveMetricsDashboard {
    constructor(baseUrl, token, tenantId) {
        this.client = new LiveMetricsClient(baseUrl, token);
        this.tenantId = tenantId;
        this.metrics = {
            revenue: {},
            calls: {},
            leads: {},
            csr_performance: {}
        };
        
        this.setupEventHandlers();
    }

    /**
     * Setup event handlers for live metrics
     */
    setupEventHandlers() {
        // Handle metrics updates
        this.client.on('metrics_update', (data) => {
            if (data.event === 'metrics.live_updated') {
                this.updateMetrics(data.data);
            }
        });

        // Handle connection events
        this.client.on('connected', () => {
            console.log('Connected to live metrics');
            this.subscribeToMetrics();
        });

        this.client.on('disconnected', () => {
            console.log('Disconnected from live metrics');
        });

        this.client.on('error', (error) => {
            console.error('Live metrics error:', error);
        });
    }

    /**
     * Subscribe to live metrics channel
     */
    subscribeToMetrics() {
        const channel = `tenant:${this.tenantId}:events`;
        this.client.subscribe(channel);
    }

    /**
     * Update metrics data and trigger UI updates
     */
    updateMetrics(data) {
        this.metrics = data;
        
        // Update revenue metrics
        this.updateRevenueDisplay(data.revenue);
        
        // Update call metrics
        this.updateCallDisplay(data.calls);
        
        // Update lead metrics
        this.updateLeadDisplay(data.leads);
        
        // Update CSR performance
        this.updateCSRDisplay(data.csr_performance);
        
        // Trigger custom event for other components
        window.dispatchEvent(new CustomEvent('liveMetricsUpdated', {
            detail: data
        }));
    }

    /**
     * Update revenue display
     */
    updateRevenueDisplay(revenue) {
        // Update revenue elements
        const todayElement = document.getElementById('revenue-today');
        const weekElement = document.getElementById('revenue-week');
        const monthElement = document.getElementById('revenue-month');
        const avgDealElement = document.getElementById('avg-deal-size');

        if (todayElement) todayElement.textContent = `$${revenue.today?.toLocaleString() || 0}`;
        if (weekElement) weekElement.textContent = `$${revenue.this_week?.toLocaleString() || 0}`;
        if (monthElement) monthElement.textContent = `$${revenue.this_month?.toLocaleString() || 0}`;
        if (avgDealElement) avgDealElement.textContent = `$${revenue.avg_deal_size?.toLocaleString() || 0}`;
    }

    /**
     * Update call display
     */
    updateCallDisplay(calls) {
        const activeElement = document.getElementById('active-calls');
        const todayElement = document.getElementById('calls-today');
        const successElement = document.getElementById('success-rate');
        const durationElement = document.getElementById('avg-duration');

        if (activeElement) activeElement.textContent = calls.active_calls || 0;
        if (todayElement) todayElement.textContent = calls.calls_today || 0;
        if (successElement) successElement.textContent = `${calls.success_rate || 0}%`;
        if (durationElement) durationElement.textContent = `${calls.avg_duration_minutes || 0} min`;
    }

    /**
     * Update lead display
     */
    updateLeadDisplay(leads) {
        const activeElement = document.getElementById('active-leads');
        const newElement = document.getElementById('new-leads-today');
        const conversionElement = document.getElementById('conversion-rate');

        if (activeElement) activeElement.textContent = leads.active_leads || 0;
        if (newElement) newElement.textContent = leads.new_leads_today || 0;
        if (conversionElement) conversionElement.textContent = `${leads.conversion_rate || 0}%`;
    }

    /**
     * Update CSR performance display
     */
    updateCSRDisplay(csr) {
        const topPerformerElement = document.getElementById('top-performer');
        const callsHandledElement = document.getElementById('calls-handled');
        const overallSuccessElement = document.getElementById('overall-success-rate');

        if (topPerformerElement) topPerformerElement.textContent = csr.top_performer?.name || 'N/A';
        if (callsHandledElement) callsHandledElement.textContent = csr.top_performer?.calls_handled || 0;
        if (overallSuccessElement) overallSuccessElement.textContent = `${csr.overall?.success_rate || 0}%`;
    }

    /**
     * Start the live metrics dashboard
     */
    async start() {
        await this.client.connect();
    }

    /**
     * Stop the live metrics dashboard
     */
    stop() {
        this.client.disconnect();
    }
}

// Example usage:
/*
// Initialize the live metrics dashboard
const dashboard = new LiveMetricsDashboard(
    'https://ottoai-backend-production.up.railway.app',
    'your-jwt-token',
    'your-tenant-id'
);

// Start receiving live updates
dashboard.start();

// Listen for custom events
window.addEventListener('liveMetricsUpdated', (event) => {
    console.log('Live metrics updated:', event.detail);
});
*/

export { LiveMetricsClient, LiveMetricsDashboard };










