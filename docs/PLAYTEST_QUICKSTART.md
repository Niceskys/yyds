# 《规则之外》本地试玩快速开始

这份说明面向只想从 GitHub 拉取当前版本并完成一局的开发者。试玩不等于获得后端开发任务授权；Developer A 的开发 gate 仍以根目录 `DEVELOPER_A_GATE.md` 为准。

## Windows：推荐单命令启动

前置条件：

- Git；
- Python 3.11 或更新版本；
- Node.js 20 或更新版本；
- 一个有效的 MiMo API key。

```powershell
git clone https://github.com/Niceskys/yyds.git
cd yyds
.\scripts\start-local-playtest.ps1
```

脚本会：

1. 以隐藏输入方式询问 MiMo API key（如果当前进程未设置 `MIMO_API_KEY`）；
2. 创建本地 `.venv` 并按需安装 Python / npm 依赖；
3. 只在 `127.0.0.1` 启动 FastAPI 和 Vite；
4. 打开 `http://127.0.0.1:5173/`；
5. 在按下 `Ctrl+C` 后停止本次脚本启动的两个服务。

密钥不会写入仓库、日志或 `.env`。运行日志只保存在被 `.gitignore` 排除的 `.local-playtest/`。

如果端口已被占用：

```powershell
.\scripts\start-local-playtest.ps1 -BackendPort 8001 -FrontendPort 5174
```

如果不希望脚本自动打开系统浏览器：

```powershell
.\scripts\start-local-playtest.ps1 -NoBrowser
```

依赖或 lockfile 更新后需要强制刷新：

```powershell
.\scripts\start-local-playtest.ps1 -RefreshDependencies
```

若 PowerShell 执行策略阻止脚本，可在阅读脚本后仅为当前进程放行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\start-local-playtest.ps1
```

## macOS / Linux：手动启动

后端终端：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
export MIMO_API_KEY='your-key'
python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
```

前端终端：

```bash
cd web
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

然后打开 `http://127.0.0.1:5173/`。

## 试玩路径

```text
开始游戏
→ 观察第 1 回合的红蓝策略与行动
→ 直接继续，或输入一条同时影响双方的中文公共规则
→ 观察规则反馈与战局升温
→ 继续到终局
→ 打开本局回放
```

当前目标是让战斗持续尽可能多的完整回合。规则接受后不会自动推进，仍需点击“继续下一回合”。

## 常见问题

### 启动后立即退出

查看：

```text
.local-playtest/backend.stderr.log
.local-playtest/frontend.stderr.log
```

常见原因是 Python / Node.js 未安装、端口占用、MiMo key 无效或无法访问 MiMo endpoint。

### 前端能打开，但开始游戏失败

确认后端端口仍在监听，并查看 backend 日志。前端默认通过 Vite 的 `/api` 同源代理访问 FastAPI，不需要放宽 CORS。

### 可以直接把 API key 提交给仓库吗？

不可以。`.env` 已被忽略，真实 key 也不应出现在 Issue、PR、截图或日志中。
