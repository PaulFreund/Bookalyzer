import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { PythonBridge } = require("./desktop/bridge.cjs");
const {
  libraryMiddleware,
  pathMethods,
} = require("./desktop/library-transfer.cjs");

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    {
      name: "local-analysis",
      configureServer(server) {
        const bridge = new PythonBridge(process.cwd());
        server.httpServer?.on("close", () => bridge.close());
        server.middlewares.use(libraryMiddleware(bridge));
        server.middlewares.use("/api/rpc", async (req, res) => {
          const origin = req.headers.origin;
          if (
            req.method !== "POST" ||
            (origin && origin !== `http://${req.headers.host}`)
          ) {
            res.writeHead(403).end();
            return;
          }
          try {
            let body = "";
            for await (const part of req) {
              body += part;
              if (body.length > 45 * 1024 * 1024)
                throw new Error("Datei zu groß (max. 30 MB).");
            }
            const { method, params } = JSON.parse(body);
            if (pathMethods.has(method))
              throw new Error("Bitte den Dateidialog verwenden.");
            const result = await bridge.call(method, params);
            res.setHeader("Content-Type", "application/json");
            res.end(JSON.stringify({ result }));
          } catch (error) {
            res.statusCode = 400;
            res.end(JSON.stringify({ error: error.message }));
          }
        });
      },
    },
  ],
  build: { outDir: "desktop-dist" },
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      ignored: [
        "**/outputs/**",
        "**/.bookanalyzer/**",
        "**/build/**",
        "**/release/**",
        "**/data/**",
      ],
    },
  },
});
