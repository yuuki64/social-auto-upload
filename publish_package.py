#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""读取投稿包并一键分发到抖音/小红书/YouTube/快手/视频号/X/Instagram。

用法：
  .venv\Scripts\python.exe publish_package.py --package <投稿包目录>
      [--platforms douyin,xiaohongshu,youtube,kuaishou,tencent,x,instagram]
      [--account primary] [--dry-run] [--review] [--headless]

设计：
- 只读取包内 meta.json / description.txt / cover.png / video.mp4，不修改包内素材。
- 去重键：平台 + 账号别名 + 原始成片 SHA-256。回执写回包内 publish-results.json。
- 默认按平台优先级 douyin,xiaohongshu,youtube,kuaishou,tencent,x,instagram 执行；
  B 站不出现在默认列表，TikTok 因平台判定自动化暂不纳入默认自动化。
- 每个平台提交一次；CLI 返回成功只代表已提交，后台可见性/审核状态仍需人工或另行核验。
- 每个平台单独计时、单独超时；X 使用本地 sidecar x_publish.py，其余用 sau CLI。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAU = ROOT / ".venv" / "Scripts" / "sau.exe"
RUNTIME = ROOT / ".runtime-tmp"
DEFAULT_PLATFORMS = ["douyin", "xiaohongshu", "youtube", "kuaishou", "tencent", "x", "instagram"]
PLATFORM_ORDER = {name: i for i, name in enumerate(DEFAULT_PLATFORMS)}
DONE_STATUSES = {
    "published",
    "published_public",
    "under_review",
    "submitted",
    "submitted_pending_verification",
    "backend_listed",
    "skipped_already_published",
}
PLATFORM_CONFIG = {
    "douyin": {"title_limit": 30, "thumb_arg": "--thumbnail-landscape", "timeout": 900},
    "xiaohongshu": {"title_limit": 20, "thumb_arg": "--thumbnail", "timeout": 900},
    "youtube": {"title_limit": 100, "thumb_arg": "--thumbnail", "timeout": 1200},
    "kuaishou": {"title_limit": 30, "thumb_arg": "--thumbnail", "timeout": 900},
    "tencent": {"title_limit": 30, "thumb_arg": "--thumbnail-landscape", "timeout": 900},
    "x": {"title_limit": 280, "thumb_arg": None, "timeout": 900},
    "instagram": {"title_limit": 2200, "thumb_arg": "--thumbnail", "timeout": 1200},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise SystemExit(f"回执不是有效 JSON：{path}（{exc}）")


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def short_title(title: str) -> str:
    """把长标题里的模型清单压成「五位 AI」，保留作品辨识度。"""
    shortened = title.replace("DeepSeek·Kimi·Gemini·GPT·Claude ", "五位 AI ")
    if shortened != title:
        return shortened
    return title


def find_ffmpeg() -> str | None:
    env_path = os.environ.get("FFMPEG")
    if env_path and Path(env_path).exists():
        return env_path
    found = shutil.which("ffmpeg")
    if found:
        return found
    fallback = Path(r"D:\tools\ffmpeg\bin\ffmpeg.exe")
    if fallback.exists():
        return str(fallback)
    return None


def make_youtube_thumbnail(cover: Path) -> Path | None:
    """YouTube 缩略图上限 2MB；cover.png 2.5MB，转成 1280x720 JPEG。"""
    if not cover.exists():
        return None
    if cover.stat().st_size <= 2 * 1024 * 1024:
        return cover
    target = RUNTIME / "cover-youtube.jpg"
    if target.exists() and target.stat().st_mtime >= cover.stat().st_mtime:
        return target
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print(f"警告：cover.png 超过 2MB 且找不到 ffmpeg，YouTube 将跳过封面上传", file=sys.stderr)
        return None
    RUNTIME.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(cover), "-vf",
         "scale=1280:720:force_original_aspect_ratio=decrease", "-q:v", "3", str(target)],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0 or not target.exists():
        print(f"警告：生成 YouTube 缩略图失败：{proc.stderr[-300:]}", file=sys.stderr)
        return None
    return target


def make_cover_variant(cover: Path, width: int, height: int, name: str) -> Path | None:
    """从 16:9 封面裁出平台要求的比例；失败返回 None。"""
    if not cover.exists():
        return None
    target = RUNTIME / name
    if target.exists() and target.stat().st_mtime >= cover.stat().st_mtime:
        return target
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print(f"警告：找不到 ffmpeg，无法生成 {name}", file=sys.stderr)
        return None
    RUNTIME.mkdir(parents=True, exist_ok=True)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    proc = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(cover), "-vf", vf,
         "-frames:v", "1", str(target)],
        capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0 or not target.exists():
        print(f"警告：生成 {name} 失败：{proc.stderr[-300:]}", file=sys.stderr)
        return None
    return target


def build_title(platform: str, title: str) -> str:
    limit = PLATFORM_CONFIG[platform]["title_limit"]
    value = short_title(title)
    if platform == "xiaohongshu":
        value = value.replace("五位 AI 拟人二创", "五位AI二创")
    return value[:limit]


def build_command(platform: str, account: str, package: Path, meta: dict, desc: str, headless: bool) -> list[str]:
    files = {item.get("role"): package / item.get("name", "") for item in meta.get("files", []) if item.get("role")}
    video = files.get("video")
    cover = files.get("cover")
    if not video or not video.exists():
        raise SystemExit(f"投稿包缺少 video.mp4：{package}")

    title = build_title(platform, str(meta.get("title", "")))
    tags = ",".join(meta.get("tags", []))

    # X 没有 sau CLI，走本地 sidecar。
    if platform == "x":
        args = [
            sys.executable, str(ROOT / "x_publish.py"),
            "--account", account,
            "--file", str(video),
            "--title", title,
            "--desc", desc,
            "--tags", tags,
        ]
        if headless:
            args.append("--headless")
        return args

    args = [
        str(SAU), platform, "upload-video",
        "--account", account,
        "--file", str(video),
        "--title", title,
        "--desc", desc,
        "--tags", tags,
    ]
    if platform == "youtube":
        thumb = make_youtube_thumbnail(cover) if cover else None
        if thumb:
            args += ["--thumbnail", str(thumb)]
        args += ["--visibility", "public"]
    elif platform == "tencent":
        landscape = make_cover_variant(cover, 1440, 1080, "cover-tencent-4x3.png") if cover else None
        portrait = make_cover_variant(cover, 810, 1080, "cover-tencent-3x4.png") if cover else None
        if landscape:
            args += ["--thumbnail-landscape", str(landscape)]
        if portrait:
            args += ["--thumbnail-portrait", str(portrait)]
        short = title.split("｜")[0].strip()
        if short:
            args += ["--short-title", short]
    elif platform == "instagram":
        args += ["--proxy", os.environ.get("SAU_INSTAGRAM_PROXY", "http://127.0.0.1:7897")]
        if cover and cover.exists():
            args += ["--thumbnail", str(cover)]
    elif cover and cover.exists():
        thumb_arg = PLATFORM_CONFIG[platform].get("thumb_arg")
        if thumb_arg:
            args += [thumb_arg, str(cover)]

    args.append("--headless" if headless else "--headed")
    return args


def login_check(platform: str, account: str) -> tuple[bool, str]:
    env = build_env()
    if platform == "x":
        cmd = [sys.executable, str(ROOT / "x_check.py"), "--account", account]
        timeout = 180
    else:
        cmd = [str(SAU), platform, "check", "--account", account]
        if platform == "instagram":
            cmd += ["--proxy", os.environ.get("SAU_INSTAGRAM_PROXY", "http://127.0.0.1:7897")]
        timeout = 180
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
        output = (proc.stdout + proc.stderr).strip()
        return proc.returncode == 0 and "valid" in output.lower(), output
    except subprocess.TimeoutExpired as exc:
        return False, f"登录检查超时（{timeout}s）：{exc}"


def build_env() -> dict:
    env = os.environ.copy()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(RUNTIME)
    env["TMP"] = str(RUNTIME)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / ".browsers")
    env["PYTHONUTF8"] = "1"
    return env


def dedupe_hit(results: dict, platform: str, account: str, video_hash: str) -> bool:
    entry = (results.get("platforms") or {}).get(platform) or {}
    if not entry:
        return False
    status = str(entry.get("status", ""))
    existing_hash = entry.get("uploaded_video_sha256") or entry.get("source_video_sha256")
    same_key = entry.get("account_alias") in (None, account) and existing_hash == video_hash
    return status in DONE_STATUSES and same_key


def main() -> int:
    parser = argparse.ArgumentParser(description="把投稿包一键分发到多平台")
    parser.add_argument("--package", required=True, help="投稿包目录（含 meta.json/video.mp4/cover.png/description.txt）")
    parser.add_argument("--platforms", default=",".join(DEFAULT_PLATFORMS), help="逗号分隔，默认 douyin,xiaohongshu,youtube,kuaishou")
    parser.add_argument("--account", default="primary", help="账号别名，默认 primary")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行上传")
    parser.add_argument("--review", action="store_true", help="上传完成后在发布前暂停，等待 *.flag 文件确认")
    parser.add_argument("--headless", action="store_true", help="无头模式（默认有头，便于处理登录/验证码）")
    args = parser.parse_args()

    package = Path(args.package).expanduser().resolve()
    meta_path = package / "meta.json"
    if not meta_path.exists():
        raise SystemExit(f"找不到 meta.json：{package}")
    meta = load_json(meta_path, {})
    description_path = package / "description.txt"
    desc = description_path.read_text(encoding="utf-8-sig").strip() if description_path.exists() else ""

    video = next((package / f.get("name", "") for f in meta.get("files", []) if f.get("role") == "video"), None)
    if not video or not video.exists():
        raise SystemExit(f"投稿包缺少 video 文件：{package}")
    video_hash = sha256_file(video)
    print(f"投稿包：{package}")
    print(f"原片 SHA-256：{video_hash}")

    results_path = package / "publish-results.json"
    results = load_json(results_path, {
        "schema_version": 2,
        "recorded_at": now_iso(),
        "package": package.name,
        "package_dir": str(package),
        "title": meta.get("title", ""),
        "video": {"sha256": video_hash},
        "platforms": {},
    })
    results.setdefault("platforms", {})
    results["recorded_at"] = now_iso()
    results["video_sha256"] = video_hash
    results["last_publish_script"] = "publish_package.py"

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in PLATFORM_CONFIG]
    if unknown:
        raise SystemExit(f"不支持的平台：{', '.join(unknown)}")
    platforms.sort(key=lambda p: PLATFORM_ORDER.get(p, 99))

    env = build_env()
    if args.review:
        env["SAU_PAUSE_BEFORE_PUBLISH"] = "1"

    for platform in platforms:
        if dedupe_hit(results, platform, args.account, video_hash):
            entry = results["platforms"][platform]
            print(f"[{platform}] 已投稿过（{entry.get('status')}，账号 {entry.get('account_alias') or args.account}，同片），跳过")
            continue

        started = time.perf_counter()

        if not args.dry_run:
            print(f"[{platform}] 检查登录态…")
            ok, check_output = login_check(platform, args.account)
            if not ok:
                duration = round(time.perf_counter() - started, 1)
                print(f"[{platform}] 登录态无效，跳过：{check_output[-200:]}", file=sys.stderr)
                results["platforms"][platform] = {
                    "status": "login_required",
                    "attempts": results["platforms"].get(platform, {}).get("attempts", 0),
                    "account_alias": args.account,
                    "checked_at": now_iso(),
                    "duration_seconds": duration,
                    "error": check_output[-500:],
                }
                save_json(results_path, results)
                continue

        try:
            cmd = build_command(platform, args.account, package, meta, desc, args.headless)
        except SystemExit as exc:
            print(f"[{platform}] {exc}", file=sys.stderr)
            continue
        print(f"[{platform}] 执行：{' '.join(cmd)}")
        if args.dry_run:
            continue

        log_dir = package / "publish-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{platform}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        attempts = int((results["platforms"].get(platform) or {}).get("attempts", 0)) + 1
        timeout = int(PLATFORM_CONFIG[platform].get("timeout", 900))
        timed_out = False
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True,
                                  errors="replace", timeout=timeout)
            stdout_text, stderr_text, returncode = proc.stdout or "", proc.stderr or "", proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout_text = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr_text = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            stderr_text += f"\nTIMEOUT after {timeout}s"
            returncode = -1
        duration = round(time.perf_counter() - started, 1)
        log_path.write_text(stdout_text + ("\n--- stderr ---\n" + stderr_text if stderr_text else ""), encoding="utf-8")
        if returncode == 0:
            status = "submitted_pending_verification"
        elif timed_out:
            status = "timeout"
        else:
            status = "failed"
        results["platforms"][platform] = {
            "status": status,
            "attempts": attempts,
            "account_alias": args.account,
            "submission_time": now_iso() if returncode == 0 else None,
            "title": build_title(platform, str(meta.get("title", ""))),
            "uploaded_video_sha256": video_hash,
            "publish_command": " ".join(cmd),
            "log": str(log_path),
            "exit_code": returncode,
            "duration_seconds": duration,
            "error": None if returncode == 0 else (stderr_text or stdout_text)[-2000:],
        }
        save_json(results_path, results)
        if returncode == 0:
            print(f"[{platform}] 已提交（{duration}s），回执：{results_path}")
        elif timed_out:
            print(f"[{platform}] 超时（{timeout}s，已耗时 {duration}s），详见 {log_path}", file=sys.stderr)
        else:
            print(f"[{platform}] 失败（exit {returncode}，{duration}s），详见 {log_path}", file=sys.stderr)

    print("完成。回执：" + str(results_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
