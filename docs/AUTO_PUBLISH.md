# 多平台一键发布

本目录是在 `dreammis/social-auto-upload` 基础上的本地扩展，保留 MIT License。

## 已支持平台

- 抖音 `douyin`
- 小红书 `xiaohongshu`
- YouTube `youtube`
- 快手 `kuaishou`
- 微信视频号 `tencent`
- X `x`（本地 sidecar，不是 `sau` 子命令）
- Instagram `instagram`

TikTok 暂不纳入自动发布：平台会检测自动化/机器人，建议手动在 TikTok Studio 发布。

## 环境

- Windows + Chrome
- Python 3.12 / uv / `.venv`
- `patchright`：本项目实测 1.58.2 需要本地 CSP 修复；长期建议升级 `patchright>=1.61.2`
- ffmpeg：视频号 4:3/3:4 封面和 YouTube 缩略图使用
- 代理：本机默认 Clash `http://127.0.0.1:7897`；国内平台上传走直连，YouTube/X/Instagram 走代理

复制 `conf.example.py` 为 `conf.py`，填入自己的 Chrome 路径和代理配置。不要提交 `conf.py`。

## 使用

```powershell
cd social-auto-upload
..venvScriptspython.exe publish_package.py --package <投稿包目录> --dry-run
..venvScriptspython.exe publish_package.py --package <投稿包目录>
```

只发部分平台：

```powershell
..venvScriptspython.exe publish_package.py --package <投稿包目录> --platforms tencent,x,instagram
```

发布前暂停：

```powershell
..venvScriptspython.exe publish_package.py --package <投稿包目录> --review
# 确认后写 .runtime-tmp<platform>-publish-go.flag，内容 go
```

## 投稿包结构

```text
package/
  meta.json          # title/tags/files（video/cover）
  description.txt
  video.mp4
  cover.png
  publish-results.json  # 运行后生成/更新
  publish-logs/         # 运行后生成
```

## 去重和回执

每个平台按「平台 + 账号别名 + 原片 SHA-256」去重。已发布过的同片会自动跳过。

回执字段包括 `status`、`submission_time`、`post_id`、`url`、`duration_seconds`、`log`。

## 各平台备注

- 视频号：会生成 4:3 横版和 3:4 竖版封面；短标题由标题 `｜` 前部分推导。
- X：使用 `x_check.py` / `x_publish.py` 和 `uploader/x_uploader/main.py`；首次登录用 `x_login`。
- Instagram：登录从首页进入，避免 `/accounts/login/` 429；上传走 `--proxy`。
- TikTok：不自动发布。

## 不要提交

`cookies/`、`conf.py`、`.venv/`、`.browsers/`、`.runtime-tmp/`、`.local/`、`logs/`、`publish-logs/`、`publish-results.json`。

这些包含账号 cookie、二维码截图、个人作品链接等隐私数据。
