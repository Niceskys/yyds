import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// 未开启 vitest globals，因此手动注册 RTL 清理，避免多个测试之间 DOM 叠加。
afterEach(() => {
  cleanup();
});
