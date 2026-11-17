# -*- coding: utf-8 -*-
import argparse
import asyncio
from pathlib import Path
from conf import BASE_DIR
from uploader.x_uploader.main import x_cookie_auth

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="primary")
    args = ap.parse_args()
    account = Path(BASE_DIR) / "cookies" / f"x_{args.account}.json"
    ok = asyncio.run(x_cookie_auth(account, headless=False))
    print("valid" if ok else "invalid")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
