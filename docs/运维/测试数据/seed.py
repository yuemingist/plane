# Seed script for Plane open-source demo data
# Run inside plane-api-1: python manage.py shell < /tmp/seed.py
from datetime import timedelta
from django.utils import timezone

from plane.db.models import (
    User, Workspace, WorkspaceMember, Project, ProjectMember, ProjectIdentifier,
    IssueType, State, Label, Issue, IssueAssignee, IssueLabel,
    IssueComment, IssueSubscriber, IssueRelation, Cycle, CycleIssue, Module,
    ModuleMember, ModuleIssue, Page, ProjectPage, IssueView, Intake, IntakeIssue,
    Estimate, EstimatePoint,
)
from plane.db.models.issue_type import ProjectIssueType
from plane.db.models.state import DEFAULT_STATES

now = timezone.now()


def jdoc(text):
    """Minimal Tiptap doc JSON for descriptions."""
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


def html(*paras):
    return "".join(f"<p>{p}</p>" for p in paras)


# ---------------------------------------------------------------- users
owner = User.objects.get(email="yueming@yuegr.com")

demo_users = [owner]
for email, first in [
    ("alice.demo@yuegr.com", "Alice"),
    ("bob.demo@yuegr.com", "Bob"),
    ("carol.demo@yuegr.com", "Carol"),
]:
    u, created = User.objects.get_or_create(
        email=email,
        defaults={"username": email.split("@")[0], "first_name": first},
    )
    demo_users.append(u)
print("users ok:", [u.email for u in demo_users])

# ---------------------------------------------------------------- workspace
ws, ws_created = Workspace.objects.get_or_create(
    slug="demo-workspace",
    defaults={
        "name": "Demo Workspace",
        "owner": owner,
        "created_by": owner,
        "updated_by": owner,
    },
)
if ws_created:
    WorkspaceMember.objects.create(
        workspace=ws, member=demo_users[0], role=20, created_by=owner, updated_by=owner
    )
    for u in demo_users[1:]:
        WorkspaceMember.objects.create(
            workspace=ws, member=u, role=15, created_by=owner, updated_by=owner
        )
print("workspace ok:", ws.slug, "created:", ws_created)

# ---------------------------------------------------------------- projects
PROJECTS = [
    {
        "name": "Web Platform",
        "identifier": "WEB",
        "emoji": "\U0001f310",
        "description": "面向客户的 Web 端平台，覆盖认证、仪表盘、设置与计费等核心模块。",
        "description_html": html(
            "面向客户的 Web 端平台，覆盖认证、仪表盘、设置与计费等核心模块。",
            "<b>目标：</b>提供稳定、可扩展的 Web 体验，支持灰度发布与多语言。",
            "<b>技术栈：</b>Next.js + TypeScript + Tailwind。",
        ),
        "cycle_view": True,
        "module_view": True,
        "issue_views_view": True,
        "intake_view": True,
        "is_issue_type_enabled": True,
    },
    {
        "name": "Mobile App",
        "identifier": "MOB",
        "emoji": "\U0001f4f1",
        "description": "iOS / Android 移动客户端。",
        "description_html": "<p>iOS / Android 移动客户端，与 Web 平台共享 API。</p>",
        "cycle_view": True,
        "module_view": True,
    },
    {
        "name": "Design System",
        "identifier": "DSGN",
        "emoji": "\U0001f3a8",
        "description": "",
        "description_html": "",
        "module_view": True,
    },
]

projects = {}
for pc in PROJECTS:
    proj = Project.objects.filter(workspace=ws, identifier=pc["identifier"]).first()
    if proj is None:
        proj = Project.objects.create(
            workspace=ws,
            name=pc["name"],
            identifier=pc["identifier"],
            description=pc["description"],
            description_text=pc["description"],
            description_html=pc["description_html"],
            emoji=pc["emoji"],
            icon_prop={"in_use": "emoji", "emoji": {"value": pc["emoji"], "url": None}},
            logo_props={"in_use": "emoji", "emoji": {"value": pc["emoji"], "url": None}},
            cycle_view=pc.get("cycle_view", False),
            module_view=pc.get("module_view", False),
            issue_views_view=pc.get("issue_views_view", False),
            intake_view=pc.get("intake_view", False),
            is_issue_type_enabled=pc.get("is_issue_type_enabled", False),
            created_by=owner,
            updated_by=owner,
        )
        ProjectIdentifier.objects.create(
            workspace=ws, project=proj, name=pc["identifier"], created_by=owner, updated_by=owner
        )
        # members: owner admin, others member
        ProjectMember.objects.create(project=proj, member=owner, role=20, created_by=owner, updated_by=owner)
        for u in demo_users[1:]:
            ProjectMember.objects.create(project=proj, member=u, role=15, created_by=owner, updated_by=owner)
        # default states
        for sd in DEFAULT_STATES:
            State.all_state_objects.get_or_create(
                project=proj,
                name=sd["name"],
                defaults={
                    "description": "",
                    "color": sd["color"],
                    "group": sd["group"],
                    "default": sd.get("default", False),
                    "is_triage": sd["name"] == "Triage",
                    "created_by": owner,
                    "updated_by": owner,
                },
            )
    projects[pc["identifier"]] = proj
print("projects ok:", list(projects))

p_web = projects["WEB"]
p_mob = projects["MOB"]
p_dsgn = projects["DSGN"]

# ---------------------------------------------------------------- custom states (WEB)
custom_states = [
    {"name": "In Review", "color": "#8B5CF6", "group": "started"},
    {"name": "QA Testing", "color": "#06B6D4", "group": "unstarted"},
]
for cs in custom_states:
    State.all_state_objects.get_or_create(
        project=p_web,
        name=cs["name"],
        defaults={
            "description": f"自定义状态示例：{cs['name']}",
            "color": cs["color"],
            "group": cs["group"],
            "created_by": owner,
            "updated_by": owner,
        },
    )

states = {}
for proj in projects.values():
    states[proj.identifier] = {
        s.name: s
        for s in State.all_state_objects.filter(project=proj)
    }

# ---------------------------------------------------------------- labels
LABELS = {
    "WEB": [
        ("Bug", "#EF4444"), ("Feature", "#3B82F6"),
        ("Enhancement", "#8B5CF6"), ("Documentation", "#10B981"),
    ],
    "MOB": [("Bug", "#EF4444"), ("Feature", "#3B82F6")],
    "DSGN": [("Design", "#F59E0B"), ("Research", "#EC4899")],
}
labels = {}
for ident, defs in LABELS.items():
    labels[ident] = {}
    for name, color in defs:
        lb, _ = Label.objects.get_or_create(
            project=projects[ident],
            name=name,
            defaults={"color": color, "created_by": owner, "updated_by": owner},
        )
        labels[ident][name] = lb

# ---------------------------------------------------------------- estimates
est, _ = Estimate.objects.get_or_create(
    project=p_web, name="Story Points",
    defaults={"description": "斐波那契故事点估算", "created_by": owner, "updated_by": owner},
)
for idx, val in enumerate(["1", "2", "3", "5", "8"]):
    EstimatePoint.objects.get_or_create(
        estimate=est, project=p_web, value=val,
        defaults={"key": idx, "description": f"{val} points", "created_by": owner, "updated_by": owner},
    )
p_web.estimate = est
p_web.save(update_fields=["estimate"])
print("estimate ok")

# ---------------------------------------------------------------- issue types (workspace-level)
epic_type, _ = IssueType.objects.get_or_create(
    workspace=ws, name="Epic",
    defaults={
        "is_epic": True, "is_active": True,
        "logo_props": {"in_use": "emoji", "emoji": {"value": "\U0001f3d4", "url": None}},
        "created_by": owner, "updated_by": owner,
    },
)
bug_type, _ = IssueType.objects.get_or_create(
    workspace=ws, name="Bug",
    defaults={"is_active": True, "created_by": owner, "updated_by": owner},
)
feature_type, _ = IssueType.objects.get_or_create(
    workspace=ws, name="Feature",
    defaults={"is_active": True, "created_by": owner, "updated_by": owner},
)
for it, lvl in [(epic_type, 0), (bug_type, 1), (feature_type, 2)]:
    ProjectIssueType.objects.get_or_create(
        project=p_web, issue_type=it, defaults={"level": lvl, "created_by": owner, "updated_by": owner}
    )
print("issue types ok")

# ---------------------------------------------------------------- issues
ISSUES = {
    "WEB": [
        # name, state, priority, labels, assignee_idx, dates(days from now), desc
        ("As a user I can log in with email and password", "Done", "high", ["Feature", "Documentation"], 0, (-20, -14),
         "支持邮箱密码登录，包含记住登录状态与找回密码。"),
        ("As a user I can reset my password via email", "Done", "medium", ["Feature"], 1, (-18, -12),
         "通过邮件重置密码，链接有效期 30 分钟。"),
        ("Dashboard: show project progress widget", "In Progress", "high", ["Feature"], 1, (-6, 4),
         "仪表盘展示项目进度组件，含燃尽图。"),
        ("Slow query on workspace activity feed", "In Progress", "urgent", ["Bug"], 2, (-3, 2),
         "工作区动态 feed 查询超过 2s，需要加索引与分页优化。"),
        ("Add dark mode toggle to settings", "In Review", "medium", ["Enhancement"], 2, (-4, 6),
         "设置页新增主题切换，跟随系统或手动指定。"),
        ("Upgrade to Next.js 15", "QA Testing", "low", ["Enhancement"], 0, (-2, 10),
         "升级 Next.js 大版本，回归验证 SSR 与中间件。"),
        ("Billing page shows wrong currency for EU users", "Todo", "high", ["Bug"], 1, (0, 5),
         "欧盟用户看到美元计价，应根据区域设置展示欧元。"),
        ("Email notifications are sent twice", "Todo", "medium", ["Bug"], 2, (1, 6),
         "同一条评论触发两封邮件，疑似重复入队。"),
        ("Write onboarding documentation", "Backlog", "low", ["Documentation"], 3, (7, 20),
         "撰写新用户引导文档，覆盖注册、建项目、邀请成员。"),
        ("Support SSO with SAML", "Backlog", "Todo", ["Feature"], 0, (10, 30),
         "企业级单点登录支持（SAML 2.0）。"),
        ("Implement SAML metadata upload", "Backlog", "low", ["Feature"], 1, (12, 32),
         "允许管理员上传 IdP 元数据 XML。"),
        ("Audit log for permission changes", "Backlog", "medium", ["Feature", "Enhancement"], 2, (14, 35),
         "记录成员权限变更的审计日志。"),
    ],
    "MOB": [
        ("Push notifications for mentions", "Done", "high", ["Feature"], 0, (-15, -8),
         "被 @ 提及时推送通知，支持免打扰时段。"),
        ("Crash on cold start in offline mode", "In Progress", "urgent", ["Bug"], 1, (-2, 3),
         "离线冷启动时本地数据库迁移失败导致崩溃。"),
        ("Biometric login (Face ID / fingerprint)", "In Progress", "medium", ["Feature"], 1, (-5, 7),
         "支持生物识别快捷登录。"),
        ("Offline mode: sync queued changes", "Todo", "high", ["Feature"], 2, (2, 12),
         "离线时队列本地修改，联网后同步。"),
        ("Improve list scrolling performance", "Todo", "medium", [], 2, (3, 14),
         "长列表滚动掉帧，考虑虚拟列表优化。"),
        ("Deep link support for issues", "Backlog", "low", ["Feature"], 0, (10, 25),
         "从浏览器/邮件打开直达 issue 详情页。"),
        ("Add iPad layout", "Backlog", "low", [], 3, (15, 40),
         "适配 iPad 分屏与大屏布局。"),
        ("Localization: add Spanish and French", "Backlog", "medium", [], 1, (8, 30),
         "新增西语和法语翻译。"),
    ],
    "DSGN": [
        ("Define color tokens for light/dark themes", "In Progress", "high", ["Design"], 0, (-4, 5),
         "建立语义化颜色 token，同时覆盖明暗主题。"),
        ("Icon set audit and cleanup", "Todo", "medium", ["Design"], 2, (1, 10),
         "清理废弃图标，统一 24px 网格。"),
        ("Empty state illustrations", "Todo", "low", ["Design"], 1, (4, 15),
         "为列表、看板等空态提供插画。"),
        ("Typography scale proposal", "Backlog", "medium", ["Research"], 3, (7, 18),
         "提出新的字号阶梯提案。"),
        ("Research: competitor onboarding flows", "Done", "medium", ["Research"], 0, (-14, -6),
         "竞品引导流程调研报告。"),
        ("Component: data table", "Backlog", "high", ["Design"], 2, (6, 20),
         "设计通用数据表格组件。"),
    ],
}

created_issues = {}
for ident, items in ISSUES.items():
    proj = projects[ident]
    lst = []
    for name, state_name, prio, label_names, aidx, dates, desc in items:
        issue, issue_created = Issue.objects.get_or_create(
            project=proj,
            name=name,
            defaults={
                "description_html": html(desc),
                "description_json": jdoc(desc),
                "description_stripped": desc,
                "priority": prio,
                "state": states[ident][state_name],
                "start_date": (now + timedelta(days=dates[0])).date(),
                "target_date": (now + timedelta(days=dates[1])).date(),
                "type": bug_type if (ident == "WEB" and "Bug" in (label_names or [])
                                     and "Feature" not in label_names) else None,
                "created_by": owner,
                "updated_by": owner,
            },
        )
        for ln in label_names or []:
            IssueLabel.objects.get_or_create(
                issue=issue, label=labels[ident][ln],
                defaults={"project": proj, "created_by": owner, "updated_by": owner},
            )
        assignee = demo_users[aidx % len(demo_users)]
        IssueAssignee.objects.get_or_create(
            issue=issue, assignee=assignee,
            defaults={"project": proj, "created_by": owner, "updated_by": owner},
        )
        IssueSubscriber.objects.get_or_create(
            issue=issue, subscriber=assignee,
            defaults={"project": proj, "created_by": owner, "updated_by": owner},
        )
        lst.append(issue)
        created_issues[(ident, name)] = issue
        if issue_created:
            print("issue:", proj.identifier, issue.sequence_id, name)

# parent/children: WEB epic + sub-issues
epic = created_issues[("WEB", "Support SSO with SAML")]
Issue.objects.filter(
    id__in=[created_issues[("WEB", "Implement SAML metadata upload")].id,
            created_issues[("WEB", "Audit log for permission changes")].id]
).update(parent=epic.id)
# also one sub-issue under dashboard widget
Issue.objects.filter(id=created_issues[("WEB", "Email notifications are sent twice")].id).update(
    parent=created_issues[("WEB", "Dashboard: show project progress widget")].id
)

# relations: billing bug blocked by activity feed perf
IssueRelation.objects.get_or_create(
    issue=created_issues[("WEB", "Billing page shows wrong currency for EU users")],
    related_issue=created_issues[("WEB", "Slow query on workspace activity feed")],
    defaults={"project": p_web, "relation_type": "blocked_by", "created_by": owner, "updated_by": owner},
)

# comments
COMMENT_TEXTS = {
    ("WEB", "Slow query on workspace activity feed"): [
        (1, "初步定位是 activity 表缺少 (workspace, created_at) 复合索引。"),
        (0, "已在本地加索引验证，查询降到 120ms，准备提 PR。"),
    ],
    ("WEB", "Dashboard: show project progress widget"): [
        (2, "设计稿已更新在 Figma，燃尽图配色请参考 Design System token。"),
    ],
    ("MOB", "Crash on cold start in offline mode"): [
        (0, "崩溃日志已上传 Sentry，栈顶在 migration v12。"),
        (1, "临时方案是捕获迁移异常后重建本地库，正式修复排在本周。"),
    ],
}
for (ident, name), comments in COMMENT_TEXTS.items():
    issue = created_issues[(ident, name)]
    for aidx, text in comments:
        IssueComment.objects.create(
            project=projects[ident],
            issue=issue,
            actor=demo_users[aidx],
            comment_html=f"<p>{text}</p>",
            comment_json=jdoc(text),
            created_by=demo_users[aidx],
            updated_by=demo_users[aidx],
        )
        print("comment:", ident, name)

# ---------------------------------------------------------------- cycles
c1, _ = Cycle.objects.get_or_create(
    project=p_web, name="Sprint 24 · Current",
    defaults={
        "description": "进行中的迭代：修复性能问题并上线仪表盘组件",
        "start_date": now - timedelta(days=5),
        "end_date": now + timedelta(days=9),
        "owned_by": owner,
        "created_by": owner,
        "updated_by": owner,
    },
)
c2, _ = Cycle.objects.get_or_create(
    project=p_web, name="Sprint 25 · Next",
    defaults={
        "description": "未来迭代：SSO 探索与文档完善",
        "start_date": now + timedelta(days=14),
        "end_date": now + timedelta(days=28),
        "owned_by": owner,
        "created_by": owner,
        "updated_by": owner,
    },
)
for issue_name in ["Dashboard: show project progress widget",
                   "Slow query on workspace activity feed",
                   "Add dark mode toggle to settings",
                   "Upgrade to Next.js 15"]:
    CycleIssue.objects.get_or_create(
        cycle=c1, issue=created_issues[("WEB", issue_name)],
        defaults={"project": p_web, "created_by": owner, "updated_by": owner},
    )
for issue_name in ["Write onboarding documentation",
                   "Billing page shows wrong currency for EU users"]:
    CycleIssue.objects.get_or_create(
        cycle=c2, issue=created_issues[("WEB", issue_name)],
        defaults={"project": p_web, "created_by": owner, "updated_by": owner},
    )
print("cycles ok")

# ---------------------------------------------------------------- modules
m1, _ = Module.objects.get_or_create(
    project=p_web, name="Authentication",
    defaults={
        "description": "登录、注册、找回密码与 SSO 相关需求。",
        "description_html": "<p>登录、注册、找回密码与 SSO 相关需求。</p>",
        "status": "in-progress",
        "lead": owner,
        "start_date": (now - timedelta(days=10)).date(),
        "target_date": (now + timedelta(days=20)).date(),
        "created_by": owner,
        "updated_by": owner,
    },
)
m2, _ = Module.objects.get_or_create(
    project=p_web, name="Billing & Plans",
    defaults={
        "description": "计费、套餐与发票模块。",
        "status": "planned",
        "lead": demo_users[2],
        "start_date": (now + timedelta(days=5)).date(),
        "target_date": (now + timedelta(days=40)).date(),
        "created_by": owner,
        "updated_by": owner,
    },
)
m3, _ = Module.objects.get_or_create(
    project=p_mob, name="Offline Mode",
    defaults={
        "description": "离线缓存与冲突同步。",
        "status": "in-progress",
        "lead": demo_users[1],
        "start_date": (now - timedelta(days=3)).date(),
        "target_date": (now + timedelta(days=15)).date(),
        "created_by": owner,
        "updated_by": owner,
    },
)
for m in (m1, m2, m3):
    for u in demo_users[:3]:
        ModuleMember.objects.get_or_create(module=m, member=u, defaults={"project": m.project})

for issue_name in ["As a user I can log in with email and password",
                   "As a user I can reset my password via email",
                   "Support SSO with SAML",
                   "Implement SAML metadata upload"]:
    ModuleIssue.objects.get_or_create(
        module=m1, issue=created_issues[("WEB", issue_name)],
        defaults={"project": projects["WEB"], "created_by": owner, "updated_by": owner},
        )
for issue_name in ["Billing page shows wrong currency for EU users",
                   "Email notifications are sent twice"]:
    ModuleIssue.objects.get_or_create(
        module=m2, issue=created_issues[("WEB", issue_name)],
        defaults={"project": projects["WEB"], "created_by": owner, "updated_by": owner},
        )
for issue_name in ["Offline mode: sync queued changes",
                   "Crash on cold start in offline mode"]:
    ModuleIssue.objects.get_or_create(
        module=m3, issue=created_issues[("MOB", issue_name)],
        defaults={"project": projects["MOB"], "created_by": owner, "updated_by": owner},
        )
print("modules ok")

# ---------------------------------------------------------------- pages
LONG_PAGE = html(
    "这是一篇用于测试协同编辑的长文档。以下是关于工作区协作规范的草案。",
) + "".join(
    html(f"<h2>第 {i} 节：协作要点 {i}</h2>",
         f"<p>第 {i} 节正文：团队在跨项目协作时，应当保持 issue 的单一事实来源。"
         f"所有需求讨论必须落回到 issue 评论中，避免信息散落在聊天工具里。"
         f"每个迭代开始前，由项目负责人确认本周 scope，并在 cycle 中挂载相应 issue。</p>",
         "<ul><li>验收标准：明确可测量的完成定义。</li>"
         "<li>优先级：urgent 仅用于线上事故。</li>"
         "<li>标签：Bug / Feature / Enhancement / Documentation。</li></ul>")
    for i in range(1, 13)
)

PAGES = [
    ("Meeting Notes · 周会记录", p_web,
     html("每周一 10:00 周会。", "<h2>本周议题</h2>", "<ol><li>仪表盘组件进度</li><li>性能优化 PR review</li><li>SSO 技术选型</li></ol>")),
    ("产品需求协作指南（长文档协同编辑测试）", p_web, LONG_PAGE),
    ("移动端发布 Checklist", p_mob,
     html("发版前逐项确认：", "<ul><li>崩溃率 &lt; 0.3%</li><li>离线模式回归通过</li><li>应用商店截图更新</li></ul>")),
]
page_objs = []
for name, proj, content in PAGES:
    page, created = Page.objects.get_or_create(
        workspace=ws, name=name,
        defaults={
            "owned_by": owner,
            "description_html": content,
            "description_stripped": name,
            "description_json": jdoc(name),
            "created_by": owner,
            "updated_by": owner,
        },
    )
    ProjectPage.objects.get_or_create(
        project=proj, page=page, workspace=ws,
        defaults={"created_by": owner, "updated_by": owner},
    )
    page_objs.append(page)
print("pages ok:", len(page_objs))

# ---------------------------------------------------------------- views (workspace-level)
v1, _ = IssueView.objects.get_or_create(
    workspace=ws, project=None, name="High & Urgent (all projects)",
    defaults={
        "description": "跨项目高优先级问题视图",
        "filters": {"priority": ["high", "urgent"]},
        "owned_by": owner,
        "created_by": owner,
        "updated_by": owner,
    },
)
v2, _ = IssueView.objects.get_or_create(
    workspace=ws, project=None, name="Open bugs",
    defaults={
        "description": "所有未完成的 Bug",
        "filters": {"labels": [str(labels["WEB"]["Bug"].id), str(labels["MOB"]["Bug"].id)]},
        "owned_by": owner,
        "created_by": owner,
        "updated_by": owner,
    },
)
print("views ok")

# ---------------------------------------------------------------- intake (WEB)
triage_state = State.all_state_objects.filter(project=p_web, is_triage=True).first()
intake, _ = Intake.objects.get_or_create(
    project=p_web, name="Default",
    defaults={"is_default": True, "created_by": owner, "updated_by": owner},
)
ia, _ = Issue.objects.get_or_create(
    project=p_web, name="Feature request: schedule dark mode by sunset time",
    defaults={
        "description_html": html("希望可以根据日落时间自动切换深色模式。"),
        "state": triage_state,
        "priority": "none",
        "created_by": owner,
        "updated_by": owner,
    },
)
IntakeIssue.objects.get_or_create(
    project=p_web, intake=intake, issue=ia,
    defaults={"status": -2, "source": "IN_APP", "created_by": owner, "updated_by": owner},
)
ib, _ = Issue.objects.get_or_create(
    project=p_web, name="Bug report: CSV export misses label column",
    defaults={
        "description_html": html("导出 CSV 时缺少标签列。"),
        "state": states["WEB"]["Todo"],
        "priority": "medium",
        "created_by": owner,
        "updated_by": owner,
    },
)
IntakeIssue.objects.get_or_create(
    project=p_web, intake=intake, issue=ib,
    defaults={"status": 1, "source": "IN_APP", "created_by": owner, "updated_by": owner},
)
print("intake ok")

# ---------------------------------------------------------------- summary
print("=" * 40)
print("SUMMARY")
print("workspace:", ws.slug, ws.id)
for ident, proj in projects.items():
    ic = Issue.issue_objects.filter(project=proj).count()
    print(f"project {ident}: issues={ic} states={State.all_state_objects.filter(project=proj).count()} "
          f"labels={Label.objects.filter(project=proj).count()}")
print("cycles:", Cycle.objects.filter(project=p_web).count())
print("modules:", Module.objects.filter(workspace=ws).count())
print("pages:", Page.objects.filter(workspace=ws).count())
print("views:", IssueView.objects.filter(workspace=ws, project__isnull=True).count())
print("issue_types:", IssueType.objects.filter(workspace=ws).count())
print("intake issues:", IntakeIssue.objects.filter(intake=intake).count())
print("comments:", IssueComment.objects.filter(project__workspace=ws).count())
print("DONE")
