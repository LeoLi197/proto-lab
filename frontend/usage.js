// frontend/usage.js
// flashmvp 使用量统计模块 - 与 Cloudflare Worker + D1 集成

// API Endpoints are now handled by the Cloudflare Worker (_worker.js)
// CRITICAL CHANGE: Removed .py extension
const USAGE_API_ENDPOINT = '/api/track-usage';
const REPORT_API_ENDPOINT = '/api/usage-report';

class UsageTracker {
    constructor() {
        // The local cache is no longer the source of truth for reporting,
        // but it can be useful for offline queueing if needed.
        // For this version, we will simplify and always call the worker.
    }

    /**
     * Records a single usage event by sending it to the Cloudflare Worker.
     * @param {string} feature - The name of the feature used.
     * @param {string} provider - The AI provider.
     * @param {string} model - The AI model ID.
     * @param {number} inputTokens - Number of input tokens.
     * @param {number} outputTokens - Number of output tokens.
     */
    async recordUsage(feature, provider, model, inputTokens, outputTokens) {
        const costResult = calculateCost(provider, model, inputTokens, outputTokens);
        if (!costResult) {
            console.error('Usage recording failed: Invalid model configuration for cost calculation.');
            return { success: false, error: 'Invalid model configuration' };
        }

        const usageRecord = {
            feature,
            provider,
            model,
            inputTokens: parseInt(inputTokens) || 0,
            outputTokens: parseInt(outputTokens) || 0,
            cost: parseFloat(costResult.totalCost),
            timestamp: new Date().toISOString(),
            userId: this.getUserId()
        };

        try {
            // Send the record to our worker endpoint
            const response = await fetch(USAGE_API_ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(usageRecord)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Failed to record usage on the server.');
            }
            
            const result = await response.json();
            console.log('Usage recorded via Cloudflare Worker:', result.message);
            return { success: true, cost: usageRecord.cost };

        } catch (error) {
            console.error('Error recording usage:', error);
            // In a production app, you might queue this locally to retry later.
            return { success: false, error: error.message };
        }
    }

    /**
     * Fetches the complete, aggregated usage report from the Cloudflare Worker.
     * This is now the single source of truth for the dashboard.
     * @returns {Promise<object>} The full report object.
     */
    async getReportData() {
        try {
            const response = await fetch(REPORT_API_ENDPOINT);
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || 'Failed to fetch usage report.');
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching report data:', error);
            // Return an empty structure on failure so the UI doesn't break
            return {
                summary: {},
                dailyTrend: [],
                topFeatures: [],
                modelUsage: []
            };
        }
    }

    /**
     * Extracts the user ID from the authentication token in localStorage.
     * @returns {string} The username or 'anonymous'.
     */
    getUserId() {
        try {
            const authToken = localStorage.getItem('proto-lab_auth_token'); // Use updated key
            if (authToken) {
                const decoded = atob(authToken);
                const [username] = decoded.split(':');
                return username;
            }
        } catch (e) {
            console.error('Error extracting user ID:', e);
        }
        return 'anonymous';
    }
}

// Create a global instance for all pages to use
const usageTracker = new UsageTracker();