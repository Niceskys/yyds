import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Developer B 前端。fixture 直接读取仓库内 canonical 资产
// contracts/fixtures/mvp-v0.2/，不在 web/ 内复制第二套。
export default defineConfig({
  plugins: [react()],
  server: {
    // 允许 Vite dev server 读取 web/ 之外的 contracts/fixtures/
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // 允许在尚未添加测试用例的增量提交上运行 `npm run test`。
    passWithNoTests: true,
  },
});
