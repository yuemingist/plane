# CE 测试造数脚本（seed.py）

- 用途：为本机开发实例（docker-compose-local.yml，容器 plane-api-1）批量造演示数据，覆盖 UI 对比所需的列表/详情/空态/设置页状态。
- 来源：2026-11-14 调研造数所用脚本（/tmp/plane-seed/seed.py）整理入库，无凭据。
- 用法：`docker exec -it plane-api-1 python manage.py shell < docs/运维/测试数据/seed.py`（或进入 shell 后 exec(open('...').read())）。
- 幂等性：实体级幂等可重跑；⚠️ IssueComment 不幂等，重跑会重复评论（当前库已去重为 5 条，谨慎重跑）。
- 数据范围：workspace `demo-workspace`（owner yueming@yuegr.com），项目 WEB/MOB/DSGN，27 个 work item、cycle×2、module×3、pages×3、views×2、issue types（Epic/Bug/Feature）、intake、estimates、自定义状态等；详见 `docs/01.追赶正式版/01.功能调研/00.测试数据说明.md`。
- 注意：cycle/module 日期以 2026-11-13 为基准，过期后需调整日期才能继续测「进行中」态。
