/**
 * API configuration for the application
 * Handles the API base URL for different environments
 */

// The base URL is injected by Vite from environment variables
declare const __API_BASE_URL__: string;

/**
 * Returns the API URL for a given endpoint
 *
 * In local development, this uses relative paths
 * In production, it uses the configured API base URL
 */
export const getApiUrl = (endpoint: string): string => {
    // If the API base URL is defined, use it
    if (__API_BASE_URL__) {
        // Ensure no double slashes in the URL
        const baseUrl = __API_BASE_URL__.endsWith("/") ? __API_BASE_URL__.slice(0, -1) : __API_BASE_URL__;

        const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
        return `${baseUrl}${path}`;
    }

    // Default to relative path for local development
    return endpoint;
};
