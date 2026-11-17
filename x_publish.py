# -*- coding: utf-8 -*-
import argparse
import asyncio
import json
from pathlib import Path
from conf import BASE_DIR
from uploader.x_uploader.main import XVideo

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="primary")
    ap.add_argument("--file", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--desc", default="")
    ap.add_argument("--tags", default="")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()
    account = Path(BASE_DIR) / "cookies" / f"x_{args.account}.json"
    tags = [t.strip().lstrip("#") for t in args.tags.split(",") if t.strip()]
    app = XVideo(args.title, args.file, tags, str(account), description=args.desc, headless=args.headless)
    url = asyncio.run(app.main())
    print(json.dumps({"platform": "x", "status": "submitted_pending_verification", "url": url}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
