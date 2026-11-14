#!/usr/bin/env python3
# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""plane_weekly_monitor.py —— Plane 官方动向周检脚本（草案）

用途
    抓取 makeplane/plane 上游公开数据（releases / preview 提交 / compare 漂移）、
    plane.so changelog 与 blog 的 sitemap 快照 diff、npm 官方包版本、pricing 正文 hash，
    生成一份可直接粘进周报模板的 Markdown。

边界（重要）
    * 只做「读取上游公开数据」，绝不执行 git fetch / 修改 ~/Develop/plane；
    * 只写 --out 指定的目录（默认 /tmp/plane_monitor），不触碰仓库；
    * 不获取任何闭源 plane-ee 代码。

用法
    python3 -I docs/运维/监控/plane_weekly_monitor.py [--out /tmp/plane_monitor]

依赖
    仅 Python 3 标准库。可选环境变量 GITHUB_TOKEN（提高 API 限额）。
    定价页 hash 基线：首次运行后把输出的 hash 记回周报，此后滚动对比。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import urllib.request

GITHUB = "https://api.github.com"
UPSTREAM = "makeplane/plane"
FORK = "yuemingist/plane"
SITE = "https://plane.so"
NPM_PACKAGES = [
    "@makeplane/propel",
    "@makeplane/plane-node-sdk",
    "@makeplane/plane-mcp-server",
]
# 上一个已知 GA/rc tag：每次 GA 后由人工更新这里（或改读参数）
LAST_KNOWN_TAG = os.environ.get("PLANE_LAST_TAG", "v1.5.0-rc2")

UA = "plane-fork-weekly-monitor/0.1 (docs/运维/监控)"


def http_get(url: str) -> bytes:
    """带 UA / 可选 GITHUB_TOKEN 的 GET。失败抛 RuntimeError。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(GITHUB):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def get_json(url: str):
    return json.loads(http_get(url).decode("utf-8"))


def get_text(url: str) -> str:
    return http_get(url).decode("utf-8", errors="replace")


def page_text(raw_html: str) -> str:
    """去 script/style 后提取可见文本（供 pricing hash 用，滤掉部署 ID 噪音）。"""
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", h))
    return "\n".join(line.strip() for line in t.splitlines() if line.strip())


def sitemap_locs(url: str, prefix: str) -> list[str]:
    try:
        xml = get_text(url)
    except RuntimeError:
        return []
    locs = re.findall(r"<loc>([^<]+)</loc>", xml)
    return sorted(loc for loc in locs if prefix in loc)


def load_prev(path: str) -> list[str]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    return []


def save_list(path: str, items: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(items) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plane 官方动向周检（只读上游，只写输出目录）")
    parser.add_argument("--out", default="/tmp/plane_monitor", help="报告与快照输出目录（默认 /tmp/plane_monitor）")
    args = parser.parse_args()

    today = dt.date.today().isoformat()
    outdir = os.path.join(args.out, today)
    os.makedirs(outdir, exist_ok=True)

    lines: list[str] = [f"# 官方动向周检原始输出 {today}", ""]

    # ---------- A/B: releases ----------
    lines += ["## Releases（最近 5 个）", ""]
    try:
        rels = get_json(f"{GITHUB}/repos/{UPSTREAM}/releases?per_page=5")
        lines += ["| tag | 发布时间 | prerelease |", "| --- | --- | --- |"]
        for r in rels:
            lines.append(
                f"| {r.get('tag_name')} | {(r.get('published_at') or '')[:10]} | {str(r.get('prerelease')).lower()} |"
            )
        ga_or_rc = [r.get("tag_name", "") for r in rels]
        new_tags = [t for t in ga_or_rc if t and t != LAST_KNOWN_TAG]
        if new_tags:
            lines += ["", f"> 注意：出现未知 tag {new_tags}，GA 版本需触发「同步上游决策流程」（08.工作约定 §1）。"]
    except RuntimeError as e:
        lines.append(f"(releases 抓取失败: {e})")
    lines += [""]

    # ---------- A: preview 提交 ----------
    lines += ["## preview 最近 30 条提交", ""]
    try:
        commits = get_json(f"{GITHUB}/repos/{UPSTREAM}/commits?sha=preview&per_page=30")
        interesting = re.compile(r"^\s*(feat|fix|release|perf)(\(|:)|\[(WEB|GIT|INFRA|SECUR)-", re.I)
        for c in commits:
            msg = c["commit"]["message"].splitlines()[0]
            date = c["commit"]["committer"]["date"][:10]
            mark = "★" if interesting.search(msg) else " "
            lines.append(f"- {mark} `{c['sha'][:7]}` {date} {msg}")
        lines += ["", "> ★ = 功能性/工单类提交，周报 §3 只抄这些。"]
        # 提交日期跨度（判断官方是否在放假/攒版本）
        if commits:
            span = (commits[0]["commit"]["committer"]["date"][:10], commits[-1]["commit"]["committer"]["date"][:10])
            lines.append(f"> 提交时间窗：{span[1]} → {span[0]}")
    except RuntimeError as e:
        lines.append(f"(commits 抓取失败: {e})")
    lines += [""]

    # ---------- B: 漂移 ----------
    lines += ["## 漂移指标", ""]
    for name, url in [
        (f"上游 {LAST_KNOWN_TAG} → preview", f"{GITHUB}/repos/{UPSTREAM}/compare/{LAST_KNOWN_TAG}...preview"),
        ("fork main → upstream preview", f"{GITHUB}/repos/{FORK}/compare/main...preview"),
    ]:
        try:
            cmp = get_json(url)
            lines.append(
                f"- {name}: status={cmp.get('status')} ahead_by={cmp.get('ahead_by')} behind_by={cmp.get('behind_by')} total={cmp.get('total_commits')}"
            )
        except RuntimeError as e:
            lines.append(f"- {name}: 抓取失败 ({e})")
    lines += [""]

    # ---------- C: changelog sitemap diff ----------
    lines += ["## changelog 新条目（相对上次快照）", ""]
    cl_now = sitemap_locs(f"{SITE}/changelog-sitemap.xml", "/changelog/")
    cl_prev_path = os.path.join(args.out, "changelog_urls.txt")
    cl_prev = load_prev(cl_prev_path)
    added = [u for u in cl_now if u not in cl_prev]
    lines += [f"- 快照总数：{len(cl_now)}（上次 {len(cl_prev)}）"]
    lines += [f"- 新增：{len(added)} 条"]
    for u in added:
        lines.append(f"  - {u}")
    if not cl_prev:
        lines += ["- （首轮无基线：以主文档时间线最后条目 2025/2026 已录 29 条为准）"]
    lines += [f"- Availability 小节判定：抓新增条目正文后人工确认（脚本不做正文解析）", ""]
    if cl_now:
        save_list(cl_prev_path, cl_now)

    # ---------- F: blog sitemap diff ----------
    lines += ["## blog 新文章（相对上次快照）", ""]
    blog_now = sitemap_locs(f"{SITE}/blog-sitemap.xml", "/blog/")
    blog_prev_path = os.path.join(args.out, "blog_urls.txt")
    blog_prev = load_prev(blog_prev_path)
    blog_added = [u for u in blog_now if u not in blog_prev]
    lines.append(f"- 新增：{len(blog_added)} 条")
    for u in blog_added:
        lines.append(f"  - {u}")
    lines += [""]
    if blog_now:
        save_list(blog_prev_path, blog_now)

    # ---------- D: pricing hash ----------
    lines += ["## pricing 正文 hash（月度项，周检顺带）", ""]
    try:
        digest = hashlib.sha256(page_text(get_text(f"{SITE}/pricing")).encode("utf-8")).hexdigest()
        lines.append(f"- sha256(正文文本): `{digest}`")
        hash_path = os.path.join(args.out, "pricing_hash.txt")
        prev_hash = load_prev(hash_path)
        if prev_hash and prev_hash[0] != digest:
            lines.append("- **变化！请人工 diff 定价页正文**（档位/价格/功能清单/Self-hosted tab）。")
        save_list(hash_path, [digest])
    except RuntimeError as e:
        lines.append(f"(pricing 抓取失败: {e})")
    lines += [""]

    # ---------- E: npm 包 ----------
    lines += ["## npm 官方包", ""]
    for pkg in NPM_PACKAGES:
        try:
            meta = get_json(f"https://registry.npmjs.org/{pkg.replace('/', '%2f')}")
            latest = meta.get("dist-tags", {}).get("latest", "?")
            times = meta.get("time", {})
            modified = (times.get("modified") or "")[:10]
            lines.append(f"- {pkg}: latest={latest} (modified {modified})")
        except RuntimeError as e:
            lines.append(f"- {pkg}: 抓取失败 ({e})")
    lines += [""]

    # ---------- 收尾 ----------
    report_path = os.path.join(outdir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[ok] 报告已写: {report_path}")
    print(f"[ok] 快照基线在: {args.out}/（changelog_urls.txt / blog_urls.txt / pricing_hash.txt）")
    print("[提示] 把 report.md 的内容按 docs/01.追赶正式版/01.功能调研/15.官方Release与路线图跟踪/监控方案.md §3 模板整理成周报。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
