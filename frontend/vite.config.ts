import { defineConfig } from 'vite';
export default defineConfig({
  // Local Vite has no Worker bindings; keep the browser on the same API path during development.
  server: { proxy: { '/api/comments': {
    target: 'https://zenith-comments.moonbite233.workers.dev', changeOrigin: true,
    rewrite: path => path.replace(/^\/api\/comments/, '') || '/',
  } } },
  build: { rollupOptions: { input: { workbench: 'index.html', gripper: 'gripper.html', dock: 'dock.html', wiring: 'wiring.html', protection: 'protection.html' } } },
});
