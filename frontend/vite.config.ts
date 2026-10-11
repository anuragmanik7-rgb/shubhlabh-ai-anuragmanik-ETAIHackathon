import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { cpSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

// The FastAPI server mounts only dist/assets (every other path falls back to index.html), so public/ ships under
// dist/assets/ instead of the dist root: public/howto/oneclick.mp4 is served at /assets/howto/oneclick.mp4.
const root = fileURLToPath(new URL('.', import.meta.url));
const publicUnderAssets = (): Plugin => ({
  name: 'public-under-assets',
  apply: 'build',
  closeBundle() { if (existsSync(root + 'public')) cpSync(root + 'public', root + 'dist/assets', { recursive: true }); },
});

export default defineConfig({publicDir:false,plugins:[react(),publicUnderAssets()],build:{emptyOutDir:false,rollupOptions:{output:{manualChunks:{charts:['recharts'],react:['react','react-dom']}}}},server:{proxy:{'/api':'http://127.0.0.1:8000','/health':'http://127.0.0.1:8000'}}});
