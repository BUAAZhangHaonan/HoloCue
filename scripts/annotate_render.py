"""Deterministic post-render label annotation. Cycles color transforms made in-scene
FONT labels unreliable; this draws object ids at projected pixel positions instead.
Run: .venv/bin/python scripts/annotate_render.py <scene>   (after build_blender_scene --render)
Reads runs/<scene>_label_px.json, annotates runs/<scene>_blender.png in place.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

def font(size: int) -> ImageFont.FreeTypeFont:
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def main(scene: str) -> None:
    px_path = ROOT/'runs'/f'{scene}_label_px.json'
    img_path = ROOT/'runs'/f'{scene}_blender.png'
    pts = json.loads(px_path.read_text())
    im = Image.open(img_path).convert('RGB')
    d = ImageDraw.Draw(im)
    f = font(22)
    # Bounding boxes grow with text length; collisions (same-height labels like
    # VOLTMETER/GUARD in drone_bench) merge into an unreadable string, so nudge
    # overlapping labels apart vertically in deterministic x order.
    boxes = {}
    for obj_id, (x, y) in sorted(pts.items()):
        w = d.textlength(obj_id, font=f) + 6
        boxes[obj_id] = [x-3, y-14, x+w, y+14]
    # Fixed-point passes: a single pass leaves residual overlaps when a label is
    # nudged into a box that only later moves out from under it (engine_bay
    # CONN/PLUG/PLUGPORT merged into one string with the old one-shot loop).
    for _ in range(16):
        moved = False
        for obj_id in sorted(boxes, key=lambda k: boxes[k][0]):
            x0, y0, x1, y1 = boxes[obj_id]
            for other, (ox0, oy0, ox1, oy1) in boxes.items():
                if other == obj_id:
                    continue
                while x0 < ox1 and ox0 < x1 and y0 < oy1 and oy0 < y1:
                    y0 -= 15; y1 -= 15
                    boxes[obj_id] = [x0, y0, x1, y1]
                    moved = True
        if not moved:
            break
    # Draw only after all boxes reach their fixed point; ink/halo contrast is
    # sampled per label at its projected anchor point.
    for obj_id, (x, y) in pts.items():
        x0, y0, _, _ = boxes[obj_id]
        region = [im.getpixel((min(max(x+dx, 0), im.width-1), min(max(y+dy, 0), im.height-1)))
                  for dx in (-14, 0, 14) for dy in (-14, 0, 14)]
        lum = sum(0.299*r+0.587*g+0.114*b for r, g, b in region)/len(region)
        ink = (16, 18, 22) if lum > 128 else (245, 248, 252)
        halo = (245, 248, 252) if lum > 128 else (16, 18, 22)
        d.text((x0, y0+5), obj_id, font=f, fill=ink, stroke_width=3, stroke_fill=halo)
    im.save(img_path)
    print(json.dumps({'annotated': str(img_path), 'labels': len(pts)}))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'control_panel')
