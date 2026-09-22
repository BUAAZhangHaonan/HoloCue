"""Capture actual browser evidence. Install Playwright in a separate QA environment if necessary."""

import argparse, os
from pathlib import Path
from playwright.sync_api import sync_playwright

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://127.0.0.1:8780")
p.add_argument("--out", default="runs/viser_actual.png")
a = p.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"] = ""
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    page = b.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    page.goto(a.url, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    page.screenshot(path=a.out, full_page=True)
    b.close()
print(a.out)
