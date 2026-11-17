# social-auto-upload 多平台发布：给本机其他 agent 的提示词

你是本机另一个执行 agent。工作目录：`D:\project for deepseekharness\default-workspace\social-auto-upload`。

任务：用 `publish_package.py` 把投稿包发布到抖音、小红书、YouTube、快手、微信视频号、X、Instagram。默认不要发 TikTok（平台已判定自动化/机器人，继续自动重试有账号风险）。

先做：
1. `cd D:\project for deepseekharness\default-workspace\social-auto-upload`
2. 读 `publish_package.py --help` 和投稿包的 `meta.json`、`description.txt`
3. 先 dry-run，不执行上传：
   `.venv\Scripts\python.exe publish_package.py --package "<投稿包目录>" --dry-run`
4. 确认平台、标题、标签、封面后，去掉 `--dry-run` 执行；只跑部分平台用：
   `--platforms douyin,xiaohongshu,youtube,kuaishou,tencent,x,instagram`
5. 需要发布前人工确认时加 `--review`；确认后在 `.runtime-tmp\<platform>-publish-go.flag` 写 `go`。

登录失效时：
- 视频号：`.venv\Scripts\sau.exe tencent login --account primary --headed`
- 抖音/小红书/YouTube/快手：`.venv\Scripts\sau.exe <platform> login --account primary --headed`
- X：`.venv\Scripts\python.exe x_check.py --account primary`；失效时用 `uploader/x_uploader/main.py` 的 `x_login` 或 X 登录页
- Instagram：`.venv\Scripts\sau.exe instagram login --account primary --proxy http://127.0.0.1:7897 --headed`

发布后看：
- `<投稿包>/publish-results.json`（平台状态、post_id/url、duration_seconds）
- `<投稿包>/publish-logs/`（每平台日志）

硬规则：
- 不要读取、复制、上传 `cookies/`、`conf.py`、`.local/`、`.runtime-tmp/`、`.venv/`、`.browsers/`。
- 不要重复发同片：脚本按「平台 + 账号 + 原片 SHA-256」自动去重。
- 不要发 TikTok；TikTok 需用户手动发布。
- 不要 git commit / git push，除非用户明确要求。
- 如果 `publish_package.py` 报 `login_required`，只提示用户登录，不要连续重试。
