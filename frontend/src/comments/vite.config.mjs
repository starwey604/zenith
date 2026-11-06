import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  root: fileURLToPath(new URL('./demo', import.meta.url)),
  publicDir: fileURLToPath(new URL('../../public', import.meta.url)),
  server: { host: '127.0.0.1', port: 5184, strictPort: true, fs: { allow: [fileURLToPath(new URL('../..', import.meta.url))] } },
  preview: { host: '127.0.0.1', port: 5185, strictPort: true },
  build: { outDir: '../.preview-dist', emptyOutDir: true },
});
