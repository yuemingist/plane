# Plane 开发环境（Mac mini）运维文档

> 主机：明哥的 Mac mini（macOS，Apple M4，16GB，用户 antares）
> 用途：Plane 个人测试环境 + 偶尔改代码，从其他设备经 Tailscale 访问
> 首次部署日期：2026-11-13（由 ZCode 会话执行）
> 部署方式：官方本地开发流程（`docker-compose-local.yml` + `pnpm dev`），**非** deployments/ 生产镜像方式

## 文档目录

- 本文：环境速查表（访问地址、启停命令、健康检查、当前状态）
- [部署过程与注意事项.md](./部署过程与注意事项.md)：首次部署的完整过程、关键配置决策及原因、踩坑记录、遗留问题

## 环境信息

| 项               | 值                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------ |
| 仓库             | `~/Develop/plane`（fork：origin=yuemingist/plane，upstream=makeplane/plane）         |
| 分支约定         | `main` = 明哥自己的修改；`preview` 仅用于同步官方代码                                |
| Tailscale 主机名 | `yuemingmac-mini.tail43aa97.ts.net`（IP `100.78.143.28`）                            |
| Docker           | OrbStack（context = orbstack），Docker Engine 29.8.2                                 |
| Node / pnpm      | v26.12.1 / **11.10.0**（pnpm 12 全局安装，在仓库内按 `packageManager` 字段自动切换） |

## 架构一览

- **后端在 Docker**：`docker-compose-local.yml`，含 Postgres 15 / Valkey 7.2 / RabbitMQ 3.13 / MinIO(silo) + api / worker / beat-worker / migrator（API 镜像本地构建，源码 bind-mount，改后端代码重启 api 容器即生效）
- **前端在本机**：tmux 会话 `plane` 里跑 4 个 dev server（web / admin / space / live）+ 11 个 `@plane/*` 包的 turbo watch（热更新）
- **协作服务**：Live（Hocuspocus）监听 3100，经 Redis pub/sub 与 API 联动

## 访问地址（所有设备可达，含 Tailscale）

| 服务                | 地址                                                      | 说明                                 |
| ------------------- | --------------------------------------------------------- | ------------------------------------ |
| Web 主应用          | http://yuemingmac-mini.tail43aa97.ts.net:3000             | 日常使用入口                         |
| Admin（god-mode）   | http://yuemingmac-mini.tail43aa97.ts.net:3001/god-mode/   | 实例管理；**首次注册管理员也在这里** |
| Space（对外发布页） | http://yuemingmac-mini.tail43aa97.ts.net:3002/spaces/     |                                      |
| Live 健康检查       | http://yuemingmac-mini.tail43aa97.ts.net:3100/live/health | 实时协作服务（WebSocket 走同端口）   |
| API                 | http://yuemingmac-mini.tail43aa97.ts.net:8000             | 根路径返回 `{"status": "OK"}`        |
| MinIO / silo        | http://yuemingmac-mini.tail43aa97.ts.net:9000             | 对象存储（上传走这里的预签名 URL）   |

⚠️ admin/space 必须带尾部斜杠和路径（`/god-mode/`、`/spaces/`），访问根路径会 302 跳转，属正常行为。
本机访问把主机名换成 `localhost` 即可（CORS 里两边都保留了）。

## 日常启停

```bash
# ---- Docker 后端 ----
cd ~/Develop/plane
docker compose -f docker-compose-local.yml down      # 停止（数据卷保留；切勿加 -v，会删库）
docker compose -f docker-compose-local.yml up -d     # 启动

# ---- 前端（tmux 会话 plane）----
tmux kill-session -t plane                           # 停止全部前端

# 重新启动（逐行粘贴；首次启动后等 ~40s 各服务就绪）
cd ~/Develop/plane
tmux new-session -d -s plane -n pkg  'pnpm turbo run dev --concurrency=18 --filter="@plane/*" 2>&1 | tee .logs/packages.log'
tmux new-window -d -t plane -n web   -c ~/Develop/plane/apps/web   'pnpm exec react-router dev -c vite.config.local.ts --port 3000 2>&1 | tee ~/Develop/plane/.logs/web.log'
tmux new-window -d -t plane -n admin -c ~/Develop/plane/apps/admin 'pnpm exec react-router dev -c vite.config.local.ts --port 3001 2>&1 | tee ~/Develop/plane/.logs/admin.log'
tmux new-window -d -t plane -n space -c ~/Develop/plane/apps/space 'pnpm exec react-router dev -c vite.config.local.ts --port 3002 2>&1 | tee ~/Develop/plane/.logs/space.log'
tmux new-window -d -t plane -n live  -c ~/Develop/plane/apps/live  'pnpm dev 2>&1 | tee ~/Develop/plane/.logs/live.log'
```

看实时输出：`tmux attach -t plane`（`Ctrl+B` + 数字键切窗口）；历史日志在 `~/Develop/plane/.logs/`。

> ❗前端**不要**直接用根目录 `pnpm dev`：`vite.config.ts`（源码）写死了 `host: "127.0.0.1"`，
> 远程设备会被 Vite 拒绝（403）。上面命令用 `-c vite.config.local.ts` 本地配置包装解决，详见过程文档。

## 健康检查速查

```bash
# 一屏检查 5 个服务（Tailscale 地址）
TS=yuemingmac-mini.tail43aa97.ts.net
for u in "http://$TS:3000" "http://$TS:3001/god-mode/" "http://$TS:3002/spaces/" "http://$TS:3100/live/health" "http://$TS:8000"; do
  printf "%-45s → HTTP %s\n" "$u" "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$u")"
done
# 全部应为 200

# 容器状态（migrator 显示 Exited(0) 是正常的，跑完迁移即退出）
docker compose -f docker-compose-local.yml ps

# 迁移是否完成（compose 重启后需要确认）
docker compose -f docker-compose-local.yml logs migrator | tail -3

# 内存占用
docker stats --no-stream        # 容器
memory_pressure -Q              # 系统整体
```

## 部署结果快照（2026-11-13 首次部署）

- 7 个容器 Up + migrator Exited(0)；5 个前端/服务端口全部监听 `0.0.0.0`，上表 URL 全部 200
- 数据库迁移全部完成（`sessions.0001_initial... OK`）；实例已注册、uploads bucket 已创建
- 内存：Docker VM 约 1.4GB，前端进程约 1.8GB，系统空闲约 48%（16GB）
- 管理员账号：由明哥自行在 god-mode 页面注册（`enable_signup=true` 已确认开启）
- git 工作区干净：.env 与本地配置均已 ignore/exclude，未提交任何 commit

## 已知限制（详见过程文档）

1. 镜像拉取/依赖安装依赖临时代理（oixCloud）；**正在运行的服务不受其开关影响**
2. 文件上传单文件上限 5MB（`FILE_SIZE_LIMIT`），预签名直传 `:9000`
3. `corepack enable` 需要 root，未执行（pnpm 自动切换已覆盖此需求）
4. 换 Tailscale 主机名/IP 的话，需同步改 4 个 .env + 3 个 `vite.config.local.ts` + API 的 `CORS_ALLOWED_ORIGINS`
