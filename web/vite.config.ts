import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// Developer B 前端。fixture 仍可从仓库根目录作为 regression 资产读取，
// 正式运行路径通过 /api 访问 A3 FastAPI。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const proxyTarget = env.VITE_BACKEND_PROXY_TARGET || 'http://127.0.0.1:8000';

  return {
    plugins: [react()],
    server: {
      // 允许测试读取 web/ 之外的 canonical fixtures。
      fs: { allow: ['..'] },
      // 本地开发保持浏览器同源；不要求后端为了开发环境扩大 CORS。
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./vitest.setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      passWithNoTests: true,
    },
  };
});
