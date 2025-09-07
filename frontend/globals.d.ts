// frontend/globals.d.ts

// --- CDN Libraries ---
declare const React: any;
declare const ReactDOM: any;
declare const MaterialUI: any;
declare const MaterialUIIcons: any;

// --- flashmvp Platform Scripts (from auth.js, models.js, usage.js) ---
declare function checkAuth(): void;
declare function getAvailableModels(): any[];
declare function calculateCost(provider: string, model: string, inputTokens: number, outputTokens: number, options?: any): any;

declare const usageTracker: {
  recordUsage(feature: string, provider: string, model: string, inputTokens: number, outputTokens: number): Promise<{ success: boolean; cost: number; error?: string }>;
  getReportData(): Promise<any>;
  getUserId(): string;
};