#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ModelScope（魔搭）魔粒「社区互动」每日脚本
==========================================
作用：每天给最多 10 个你还没“喜欢”过的模型点“喜欢”。
魔粒规则：收藏/喜欢 2 魔粒/次，每日 10 次封顶（+20）；
每日登录奖励（200+50）仍需当天用浏览器打开过魔搭页面。

特点：
- 只用 Python 标准库，不需要 pip 安装任何东西
- 自动跳过已喜欢过的、你自己发布的模型
- 每次点赞之间随机等待 1~10 秒，降低被机器人检测的风险
- 本地记录状态与日志（ms_like_state.json / ms_like.log），同一天重复运行不会超量

用法：
  1. 把登录后的完整 Cookie 存到同目录 ms_cookie.txt（推荐，已被 .gitignore 忽略；
     取 Cookie 步骤见同目录 README.md），或设置环境变量 MS_COOKIE
  2. 试运行（不真点赞）：python ms_magicube_daily.py --dry-run
  3. 正式运行：python ms_magicube_daily.py
  4. 每天自动运行：双击 setup_task.bat（默认每天 09:30，可在文件里改时间）
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime

__version__ = "0.1.0"

BASE_URL = "https://www.modelscope.cn"

# ============================ 配置区 ============================
# 在下面两个三引号之间粘贴完整 Cookie（等同登录凭证，不要外传！）
# 也可以不改这里，改用环境变量 MS_COOKIE 传入。
COOKIE = r"""
"""

LIKE_COUNT = 10             # 每天点赞次数上限（魔粒规则 2 分/次、10 次/天封顶）
PAGE_SIZE = 100             # 模型列表每页数量
MAX_PAGES = 6               # 最多扫描多少页模型列表来收集“还没喜欢过”的模型
DELAY_RANGE = (1.0, 10.0)   # 每次点赞之间的随机等待秒数（防机器人检测）
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
# ================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(SCRIPT_DIR, "ms_cookie.txt")  # 可选：Cookie 存这里（.gitignore 已忽略）
STATE_FILE = os.path.join(SCRIPT_DIR, "ms_like_state.json")
LOG_FILE = os.path.join(SCRIPT_DIR, "ms_like.log")
STATE_KEEP_DAYS = 60        # 本地状态只保留最近 60 天


def log(msg: str) -> None:
    line = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("days"), dict):
                return data
    except (OSError, ValueError):
        pass
    return {"days": {}}


def save_state(state: dict) -> None:
    days = state.get("days", {})
    keep = sorted(days)[-STATE_KEEP_DAYS:]
    state["days"] = {k: days[k] for k in keep}
    tmp = STATE_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def parse_cookies(cookie_str: str) -> dict:
    out = {}
    for part in cookie_str.replace("\n", " ").split(";"):
        part = part.strip()
        if part and "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def api(method: str, path: str, cookies: dict, csrf: str, body=None):
    """调用魔搭接口。返回 (http_status, json_dict 或 None, 原始文本)。"""
    data = None
    if method in ("PUT", "POST"):
        data = json.dumps(body if body is not None else {}).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    req.add_header("Cookie", "; ".join("%s=%s" % (k, v) for k, v in cookies.items()))
    req.add_header("User-Agent", USER_AGENT)
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("Referer", BASE_URL + "/")
    req.add_header("Origin", BASE_URL)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-modelscope-accept-language", "zh_CN")
    req.add_header("X-Modelscope-Trace-Id", str(uuid.uuid4()))
    if csrf:
        req.add_header("X-CSRF-TOKEN", csrf)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            raw = e.read().decode("utf-8", "replace")
        except Exception:
            raw = ""
    except urllib.error.URLError as e:
        return 0, None, "network error: %s" % getattr(e, "reason", e)
    try:
        return status, json.loads(raw), raw
    except ValueError:
        return status, None, raw


def login_username(cookies: dict, csrf: str):
    """返回 (user_name, err)；err 为空表示成功，否则为 'network'/'auth'/'http:<状态码>'。"""
    st, data, _ = api("GET", "/api/v1/users/info", cookies, csrf)
    if st == 200 and isinstance(data, dict):
        name = str((data.get("Data") or {}).get("user_name") or "").strip()
        return name, ("" if name else "auth")
    if st == 0:
        return "", "network"
    if st in (401, 403):
        return "", "auth"
    return "", "http:%s" % st


def main() -> int:
    parser = argparse.ArgumentParser(description="ModelScope 魔粒每日互动脚本")
    parser.add_argument("--dry-run", action="store_true",
                        help="只列出将要点赞的模型，不实际点赞")
    parser.add_argument("--count", type=int, default=None,
                        help="本次点赞次数上限（默认 %d）" % LIKE_COUNT)
    args = parser.parse_args()

    dry_run = args.dry_run or os.environ.get("MS_DRY_RUN", "").strip() in ("1", "true", "True")
    daily_limit = LIKE_COUNT
    if args.count is not None:
        daily_limit = args.count
    else:
        env_count = os.environ.get("MS_LIKE_COUNT", "").strip()
        if env_count:
            try:
                daily_limit = int(env_count)
            except ValueError:
                log("!! 环境变量 MS_LIKE_COUNT=%r 不是整数，忽略并使用默认 %d。" % (env_count, LIKE_COUNT))
    if daily_limit <= 0:
        log("点赞次数上限为 %d（<=0），本次结束。" % daily_limit)
        return 0

    cookie_src = "环境变量 MS_COOKIE"
    cookie_str = os.environ.get("MS_COOKIE", "").strip()
    if not cookie_str and COOKIE.strip():
        cookie_src = "脚本内 COOKIE"
        cookie_str = COOKIE.strip()
    if not cookie_str and os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, encoding="utf-8-sig") as f:
                cookie_str = f.read().strip()
            cookie_src = "ms_cookie.txt"
        except OSError:
            cookie_str = ""
    if not cookie_str:
        print("!! 还没有配置 Cookie：请把登录后的完整 Cookie 存到同目录 ms_cookie.txt，")
        print("   或设置环境变量 MS_COOKIE（步骤见同目录 README.md）。")
        return 2
    log("Cookie 来源：%s" % cookie_src)

    cookies = parse_cookies(cookie_str)
    csrf = urllib.parse.unquote(cookies.get("csrf_token", ""))

    log("== ModelScope 魔粒每日互动 v%s 开始 ==" % __version__)
    user, err = login_username(cookies, csrf)
    if not user:
        if err == "network":
            log("!! 网络错误：连不上 www.modelscope.cn，请检查网络后重试。")
        elif err == "auth":
            log("!! Cookie 失效或未登录（401/403 或未返回用户）。请重新复制完整 Cookie。")
        else:
            log("!! 接口异常（HTTP %s），无法确认登录身份，请稍后重试。" % err)
        return 2
    log("登录身份：%s" % user)

    today = date.today().isoformat()
    state = load_state()
    done_today = list(state.setdefault("days", {}).setdefault(today, []))
    if len(done_today) >= daily_limit:
        log("今天已互动 %d 次，达到上限 %d，结束（明天再跑）。" % (len(done_today), daily_limit))
        return 0
    need = daily_limit - len(done_today)
    log("今天已互动 %d 次，本次还可点赞 %d 次（上限 %d）。" % (len(done_today), need, daily_limit))

    # ---- 扫描模型列表，收集还没喜欢过的模型 ----
    done_set = set(done_today)
    candidates = []
    for page_no in range(1, MAX_PAGES + 1):
        body = {"PageSize": PAGE_SIZE, "PageNumber": page_no, "SortBy": "Default",
                "Target": "", "SingleCriterion": [], "Criterion": []}
        st, data, _raw = api("PUT", "/api/v1/dolphin/models", cookies, csrf, body)
        models = ((((data or {}).get("Data") or {}).get("Model") or {}) or {}).get("Models") or []
        if st != 200 or not models:
            log("模型列表第 %d 页获取失败（HTTP %s），停止扫描。" % (page_no, st))
            break
        fresh = [m for m in models
                 if not m.get("AlreadyStar")
                 and m.get("Path") and m.get("Name")
                 and m.get("Path") != user and m.get("CreatedBy") != user
                 and "%s/%s" % (m["Path"], m["Name"]) not in done_set]
        candidates.extend(fresh)
        log("第 %d 页：%d 个模型，其中还没喜欢过的 %d 个。" % (page_no, len(models), len(fresh)))
        if len(candidates) >= need * 3:
            break
        time.sleep(random.uniform(*DELAY_RANGE))

    random.shuffle(candidates)  # 打乱顺序，避免每天点赞同一批
    targets = candidates[:need]

    if not targets:
        log("没有找到可点赞的新模型（可能都已经喜欢过），结束。")
        return 0

    if dry_run:
        log("[试运行] 将点赞以下 %d 个模型（本次不实际点赞）：" % len(targets))
        for m in targets:
            log("  - https://www.modelscope.cn/models/%s/%s  (当前喜欢数 %s)"
                % (m["Path"], m["Name"], m.get("Stars")))
        log("[试运行] 结束。去掉 --dry-run 即为正式运行。")
        return 0

    # ---- 逐个点赞 ----
    ok = skip = fail = 0
    for i, m in enumerate(targets, 1):
        path = "%s/%s" % (m["Path"], m["Name"])
        url_path = "/api/v1/models/%s/%s/stars" % (
            urllib.parse.quote(m["Path"], safe=""), urllib.parse.quote(m["Name"], safe=""))
        st, data, raw = api("PUT", url_path, cookies, csrf, {})
        success = bool(data) and (data.get("Success") is True or data.get("Code") == 200)
        stars = ((data or {}).get("Data") or {}).get("Stars")
        msg = str(((data or {}).get("Message") or raw or ""))[:120]
        if success:
            ok += 1
            done_today.append(path)
            state["days"][today] = done_today
            save_state(state)
            log("(%d/%d) 喜欢成功：%s  当前喜欢数=%s" % (i, len(targets), path, stars))
        elif st in (401, 403):
            fail += 1
            log("(%d/%d) 喜欢失败：%s  HTTP %s —— Cookie 可能已过期，请重新复制填入。" % (i, len(targets), path, st))
            break
        elif st == 200 and isinstance(data, dict):
            # HTTP 200 但业务上没成功（如重复点赞），记录下来避免反复重试
            skip += 1
            done_today.append(path)
            state["days"][today] = done_today
            save_state(state)
            log("(%d/%d) 接口提示（未确认成功，今日不再重试）：%s  %s" % (i, len(targets), path, msg))
        else:
            fail += 1
            log("(%d/%d) 喜欢失败：%s  HTTP %s %s" % (i, len(targets), path, st, msg))
        if i < len(targets):
            delay = random.uniform(*DELAY_RANGE)
            log("    随机等待 %.1f 秒后继续…" % delay)
            time.sleep(delay)

    log("== 结束：成功 %d 次（额度未满时预计 +%d 魔粒），跳过 %d 次，失败 %d 次 =="
        % (ok, ok * 2, skip, fail))
    log("积分明细见：https://www.modelscope.cn/magicube/usage?tab=earn")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(main())
