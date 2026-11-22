# ModelScope 魔粒「社区互动」每日脚本

当前版本：v0.1.0

每天自动给魔搭上你还没“喜欢”过的模型点“喜欢”，赚取社区互动魔粒。

## 任务规则（魔粒页原文）

- 每日登录：注册并登录 +200、绑定阿里云账号后每日登录 +50（合计 250，需当天打开过魔搭页面）
- **社区互动 → 收藏/喜欢：对其他用户的发布进行点击收藏/喜欢，2 魔粒/次，每日 10 次封顶（+20）**
- 明细页：<https://www.modelscope.cn/magicube/usage?tab=earn>

本脚本只负责第二项：给**你还没喜欢过的**模型点“喜欢”，每次之间随机等待 1~10 秒，防机器人检测。登录奖励仍需你当天用浏览器打开一次魔搭。

## 已验证的接口（2026-11-22 实测）

| 用途 | 接口 |
|---|---|
| 登录身份 | `GET /api/v1/users/info` |
| 模型列表（含 `AlreadyStar` 是否已喜欢） | `PUT /api/v1/dolphin/models`，body `{"PageSize":100,"PageNumber":1,"SortBy":"Default",...}` |
| 点“喜欢” | `PUT /api/v1/models/{作者}/{模型名}/stars`，body `{}`，响应 `{"Code":200,"Data":{"Stars":新喜欢数},"Success":true}` |

注意：点赞接口需要请求头 `X-CSRF-TOKEN`，取自 Cookie 里的 `csrf_token`（URL 解码后的值）；Cookie 里还必须有登录会话。脚本已自动处理。

## 第一次使用（3 步）

1. **把整个文件夹复制到一个固定目录**（例如 `D:\tools\modelscope-magicube\`），以后别挪动，计划任务指向这里的 `run_daily.bat`。

2. **填 Cookie**（脚本等同于你的登录凭证）：
   - 电脑浏览器打开 <https://www.modelscope.cn>，确认右上角已登录
   - 按 `F12` 打开开发者工具 → 「网络 / Network」标签 → 刷新页面
   - 点请求列表里第一条（`www.modelscope.cn`）→ 「标头 / Headers」→「请求标头 / Request Headers」
   - 找到 `Cookie:` 这一行，把**冒号后面的完整内容**（很长的一串）复制下来
   - 在本目录新建文本文件 `ms_cookie.txt`，把内容粘贴进去保存（推荐；该文件已被 `.gitignore` 忽略，不会进 git）
   - 也可以改用环境变量：`setx MS_COOKIE "粘贴的Cookie"`（设完重开终端生效）
   - ⚠️ 一定要从「网络/Network」面板复制**完整 Cookie 头**：登录态依赖 HttpOnly 的 Cookie（如 `m_session_id`），在 Console 里用 `document.cookie` 或在 Application 面板里挑几个是拿不全的
   - ⚠️ Cookie 等同登录凭证，不要发给任何人；**不要把真实 Cookie 粘进 `ms_magicube_daily.py` 再提交**（脚本顶部 `COOKIE` 是给单机用户留的兜底项，公开仓库版本必须保持为空）

3. **注册每天自动运行**：双击 `setup_task.bat`（默认每天 09:30，改时间就编辑该文件里的 `09:30` 后重新运行）。

## 常用命令

```
python ms_magicube_daily.py --dry-run     # 试运行：显示登录身份 + 将点赞的模型，不真点
python ms_magicube_daily.py               # 正式运行
schtasks /Run /TN "ModelScope魔粒每日互动" # 手动触发计划任务
schtasks /Delete /TN "ModelScope魔粒每日互动" /F   # 取消每日自动运行
```

## 脚本行为说明

- 按综合排序扫描模型列表（最多 6 页 × 100 个），筛选出 `AlreadyStar=false`（你还没喜欢过）且不是你自己发布的模型，随机抽取点赞，每日上限 10 次
- 每两次点赞之间随机等待 1~10 秒
- `ms_like_state.json` 记录每天点了哪些模型，同一天重复运行不会超量；已喜欢的模型服务端也会自动跳过
- 运行日志写入 `ms_like.log`（计划任务运行的结果也在这里看）

## 配置方式

| 方式 | 说明 |
|---|---|
| `ms_cookie.txt`（推荐） | 与脚本同目录，内容为完整 Cookie（单行即可）；已被 `.gitignore` 忽略 |
| 环境变量 `MS_COOKIE` | 完整 Cookie；优先级高于 `ms_cookie.txt` |
| 环境变量 `MS_LIKE_COUNT` | 覆盖每日点赞上限（默认 10，规则上限 10） |
| 环境变量 `MS_DRY_RUN` | 设为 `1` 等效 `--dry-run` |
| 脚本内 `COOKIE` | 兜底选项；公开仓库版本必须保持为空，避免凭证泄漏 |

## 常见问题

- **提示 Cookie 失效/未登录**：登录会话过期了，按上面步骤重新复制一次 Cookie 即可（一般可用较长时间）
- **成功 10 次但魔粒没涨**：说明当天额度已经被你手动用完（网页上显示“今日已完成 20”），第二天脚本会正常计分
- **'python' 不是内部或外部命令**：没装 Python 或不在 PATH。装好后，若仍不行，把 `run_daily.bat` 里的 `python` 换成 python.exe 的完整路径
- **想改每天点赞次数**：改 `ms_magicube_daily.py` 顶部的 `LIKE_COUNT`（规则上限 10 次/天，超出不计分）

> 免责：本脚本模拟网页端正常点赞行为，频率克制（10 次/天、随机延时）。请遵守魔搭社区用户协议，如平台规则变更请停止使用。

## 许可证

MIT License —— 见 [LICENSE](LICENSE)
