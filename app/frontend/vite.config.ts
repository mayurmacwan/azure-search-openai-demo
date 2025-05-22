import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default ({ mode }) => {
    // Load env variables from .env files
    const env = loadEnv(mode, process.cwd(), "");

    // API base URL from environment or default to relative path for local dev
    const apiBaseUrl = env.VITE_API_BASE_URL || "";

    return defineConfig({
        plugins: [react()],
        resolve: {
            preserveSymlinks: true
        },
        build: {
            // For SPA deployment, output to dist folder
            outDir: mode === "production" ? "dist" : "../backend/static",
            emptyOutDir: true,
            sourcemap: true,
            rollupOptions: {
                output: {
                    manualChunks: id => {
                        if (id.includes("@fluentui/react-icons")) {
                            return "fluentui-icons";
                        } else if (id.includes("@fluentui/react")) {
                            return "fluentui-react";
                        } else if (id.includes("node_modules")) {
                            return "vendor";
                        }
                    }
                }
            },
            target: "esnext"
        },
        define: {
            // Make API base URL available in the app
            __API_BASE_URL__: JSON.stringify(apiBaseUrl)
        },
        server: {
            proxy: {
                "/content/": "http://localhost:50505",
                "/auth_setup": "http://localhost:50505",
                "/.auth/me": "http://localhost:50505",
                "/ask": "http://localhost:50505",
                "/chat": "http://localhost:50505",
                "/speech": "http://localhost:50505",
                "/config": "http://localhost:50505",
                "/upload": "http://localhost:50505",
                "/delete_uploaded": "http://localhost:50505",
                "/list_uploaded": "http://localhost:50505",
                "/chat_history": "http://localhost:50505"
            }
        }
    });
};
