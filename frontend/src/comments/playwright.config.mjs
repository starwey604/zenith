import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  testDir: './tests', workers: 1, timeout: 45000,
  use: { baseURL: 'http://127.0.0.1:5185', viewport: { width: 1200, height: 900 },
    launchOptions: { executablePath: process.env.CHROMIUM_PATH || (!process.env.CI && existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined), args: ['--no-sandbox'] } },
  webServer: { command: 'npx vite preview --config src/comments/vite.config.mjs', cwd: fileURLToPath(new URL('../..', import.meta.url)), url: 'http://127.0.0.1:5185', reuseExistingServer: false, stdout: 'pipe', stderr: 'pipe' },
  outputDir: './.test-results',
});
