// frontend/_worker.js
// This is a Cloudflare Pages Function that acts as a smart router and API gateway.
// It intercepts every request to your site before it hits the static assets.

// --- IMPORTANT CONFIGURATION ---
// The BACKEND_URL is no longer hardcoded here.
// It will be injected as an environment variable during the GitHub Actions deployment.
// This allows the same code to work across different environments (dev, staging, prod).

export default {
  async fetch(request, env, ctx) {
    // Dynamically get the backend URL from the environment bindings.
    // 'env.BACKEND_URL' is set in the GitHub Actions workflow via 'cloudflare/pages-action'.
    const BACKEND_URL = env.BACKEND_URL;
    
    // Ensure the backend URL is configured, otherwise return an error.
    if (!BACKEND_URL) {
        console.error("CRITICAL: BACKEND_URL environment variable is not set.");
        return new Response("Backend service is not configured. Deployment is incomplete.", { status: 503 });
    }
    
    const url = new URL(request.url);

    // --- ROUTE 1: Handle Usage Tracking at the Edge ---
    if (url.pathname === '/api/track-usage' && request.method === 'POST') {
      try {
        const data = await request.json();
        // `env.DB` is the D1 database binding from wrangler.toml or CI/CD bindings
        const stmt = env.DB.prepare(
          `INSERT INTO Usage (timestamp, feature, provider, model, input_tokens, output_tokens, cost, user_id) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
        );
        await stmt.bind(
          data.timestamp || new Date().toISOString(),
          data.feature, data.provider, data.model,
          data.inputTokens, data.outputTokens, data.cost, data.userId
        ).run();

        const response = { success: true, message: 'Usage tracked successfully in D1.' };
        return new Response(JSON.stringify(response), {
          headers: { 'Content-Type': 'application/json' },
        });
      } catch (e) {
        console.error('D1 Insert Error:', e.message);
        const errorResponse = { success: false, error: 'Failed to record usage in database.' };
        return new Response(JSON.stringify(errorResponse), { status: 500 });
      }
    }

    // --- ROUTE 2: Handle Usage Reporting at the Edge ---
    if (url.pathname === '/api/usage-report' && request.method === 'GET') {
      try {
        const d1_calls = [
          // Query for summary stats
          env.DB.prepare("SELECT COUNT(*) as totalRequests, SUM(cost) as totalCost, SUM(input_tokens) as totalInputTokens, SUM(output_tokens) as totalOutputTokens FROM Usage").first(),
          // Query for top features
          env.DB.prepare("SELECT feature, COUNT(*) as requests, SUM(cost) as cost FROM Usage GROUP BY feature ORDER BY cost DESC LIMIT 10").all(),
          // Query for model usage
          env.DB.prepare("SELECT provider, model, COUNT(*) as requests, SUM(cost) as cost FROM Usage GROUP BY provider, model ORDER BY cost DESC LIMIT 10").all(),
        ];
        
        const [summary, topFeatures, modelUsage] = await Promise.all(d1_calls);
        
        const report = {
          summary: summary || {},
          topFeatures: topFeatures.results || [],
          modelUsage: modelUsage.results || []
        };
        
        return new Response(JSON.stringify(report), {
          headers: { 'Content-Type': 'application/json' },
        });
      } catch (e) {
        console.error('D1 Report Error:', e.message);
        const errorResponse = { success: false, error: 'Failed to generate usage report from database.' };
        return new Response(JSON.stringify(errorResponse), { status: 500 });
      }
    }

    // --- ROUTE 3: Proxy other API requests to Google Cloud Run Backend ---
    if (url.pathname.startsWith('/api/')) {
      // Construct the new URL for the backend
      const backendApiUrl = new URL(url.pathname, BACKEND_URL);

      // Create a new request object to avoid modifying the original
      const backendRequest = new Request(backendApiUrl, request);

      // It's good practice to forward the original host
      backendRequest.headers.set('X-Forwarded-Host', url.hostname);
      
      console.log(`Proxying API request from ${url.pathname} to ${backendApiUrl}`);
      
      // Fetch from the backend and return its response directly to the client
      return fetch(backendRequest);
    }

    // --- FALLBACK: Serve Static Assets from Cloudflare Pages ---
    // If the request doesn't match any of the API routes above,
    // `env.ASSETS.fetch()` will serve the static file (e.g., index.html, style.css).
    return env.ASSETS.fetch(request);
  }
};