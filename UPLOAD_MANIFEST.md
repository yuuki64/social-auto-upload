# GitHub 上传清单 · social-auto-upload 多平台扩展

生成时间：2026-11-17 22:30 +08:00

## 包含

- 原项目 `dreammis/social-auto-upload` 源码（MIT License，保留 LICENSE 与版权声明）
- `publish_package.py`：七平台一键发布（抖音/小红书/YouTube/快手/视频号/X/Instagram）
- `x_check.py`、`x_publish.py`：X 登录检查与发布 sidecar
- `uploader/x_uploader/`：X/Twitter 浏览器上传器
- 修改后的 uploader：douyin / xiaohongshu / youtube / ks / tencent / tk / meta_uploader/insgraph_uploader
- `docs/AUTO_PUBLISH.md`：使用说明
- `AGENT_PROMPT.md`：给本机其他 agent 的直接使用提示词
- `conf.example.py`：配置示例

## 不包含（个人数据/本机状态）

- `cookies/`（各平台登录态）
- `conf.py`（本机 Chrome/代理配置）
- `.venv/`、`.uv-cache/`、`.uv-python/`、`.browsers/`
- `.runtime-tmp/`（含二维码、审核截图、发布标志）
- `.local/`、`logs/`、`publish-logs/`
- 任何 `publish-results.json`（含账号、作品链接、后台数据）
- 投稿包视频、封面、截图

## 上传前

1. 确认 GitHub 仓库为公开时，不要再把上述个人文件放进去。
2. 保留 `LICENSE`（MIT，Copyright (c) 2023 dreammis），并在 README 说明本仓库是基于原项目的本地扩展。
3. patchright 1.58.2 的 CSP 修复未包含在仓库；建议在 `requirements.txt` 使用 `patchright>=1.61.2`，或单独提供 `.patch`。
4. 建议单独建分支/仓库，不要直接 push 到 `dreammis/social-auto-upload` 的 main。

## 快速检查

```powershell
cd social-auto-upload-clean-20261117
python -m py_compile publish_package.py x_check.py x_publish.py
python publish_package.py --help
```
