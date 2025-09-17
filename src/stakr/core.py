from pathlib import Path
from PIL import Image, ImageChops
import math


# ── helpers ───────────────────────────────────────────────────────────────
def load_stack(path: Path, slices: int):
    img = Image.open(path).convert("RGBA")
    if img.width % slices:
        raise ValueError(f"{img.width=} not divisible by {slices}")
    w = img.width // slices
    return [img.crop((i * w, 0, (i + 1) * w, img.height)) for i in range(slices)]


def _baseline_drop(w: int, h: int, theta: float) -> float:
    half_h = 0.5 * (h * abs(math.cos(theta)) + w * abs(math.sin(theta)))
    return half_h - h * 0.5


def _hex_rgb(s: str):
    s = s.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


def _tint(img: Image.Image, color):
    """Multiply `img` by solid `color` (RGB)."""
    tint = Image.new("RGBA", img.size, (*color, 255))
    return ImageChops.multiply(img, tint)


# ── object stack (gradient tint) ─────────────────────────────────────────-
def build_stack(
    frames,
    obj_angle: float,
    v_step: int,
    squash: float,
    grad_top,
    grad_bottom,
):
    theta = math.radians(obj_angle)
    sw, sh0 = frames[0].size
    sh = int(sh0 * squash)

    rot0 = frames[1].resize((sw, sh), Image.NEAREST).rotate(obj_angle, expand=True)
    rw, rh = rot0.size
    drop = _baseline_drop(sw, sh, theta)

    depth = len(frames) - 1
    canvas_h = rh + abs(v_step) * depth
    canvas = Image.new("RGBA", (rw, canvas_h), (0, 0, 0, 0))

    for i, fr in enumerate(frames[1:], 0):
        rot = fr.resize((sw, sh), Image.NEAREST).rotate(obj_angle, expand=True)

        # gradient modulation ------------------------------------------------
        t = i / depth if depth else 0  # 0 at bottom, 1 at top
        r = int(grad_bottom[0] + (grad_top[0] - grad_bottom[0]) * t)
        g = int(grad_bottom[1] + (grad_top[1] - grad_bottom[1]) * t)
        b = int(grad_bottom[2] + (grad_top[2] - grad_bottom[2]) * t)
        rot = _tint(rot, (r, g, b))
        # --------------------------------------------------------------------

        x = (rw - rot.width) // 2
        y = int(canvas_h - rot.height - abs(v_step) * i + drop)
        canvas.alpha_composite(rot, (x, y))
        if i == 0:
            canvas.info["origin"] = (x + rot.width // 2, y + rot.height)

    return canvas


# ── shadow builder (unchanged) ────────────────────────────────────────────
def build_shadow(frames, obj_angle, sh_angle, step_px, squash):
    theta_off = math.radians(sh_angle)
    dx =  step_px * math.cos(theta_off)
    dy = -step_px * math.sin(theta_off)

    sw, sh0 = frames[0].size
    sh = int(sh0 * squash)
    rot0 = frames[1].resize((sw, sh), Image.NEAREST).rotate(obj_angle, expand=True)
    rw, rh = rot0.size
    depth = len(frames) - 1

    min_dx, max_dx = sorted((0, dx * depth))
    min_dy, max_dy = sorted((0, dy * depth))

    cw = rw + int(round(max_dx - min_dx))
    ch = rh + int(round(max_dy - min_dy))
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    base_x = -int(round(min_dx))
    base_y = -int(round(min_dy))

    def silhouette(img):
        blk = Image.new("RGBA", img.size, (0, 0, 0, 255))
        blk.putalpha(img.split()[3])
        return blk

    for i, fr in enumerate(frames[1:], 0):
        rot = fr.resize((sw, sh), Image.NEAREST).rotate(obj_angle, expand=True)
        sil = silhouette(rot)
        ox = int(round(dx * i)) + base_x
        oy = int(round(dy * i)) + base_y
        canvas.paste(sil, (ox, oy), sil)
        if i == 0:
            canvas.info["origin"] = (ox + rot.width // 2, oy + rot.height)

    return canvas


# ── sheet helper ----------------------------------------------------------
def _sheet(imgs):
    cw = max(i.width for i in imgs)
    ch = max(i.height for i in imgs)
    s = Image.new("RGBA", (cw * len(imgs), ch), (0, 0, 0, 0))
    for n, img in enumerate(imgs):
        s.alpha_composite(img, (n * cw + (cw - img.width) // 2, ch - img.height))
    return s


# ── bake entry ------------------------------------------------------------
def bake(
    src: Path,
    out_dir: Path,
    *,
    slices: int,
    rot_inc: int = 36,
    v_step: int = -1,
    squash: float = 1.0,
    shadow_angle: float = 40.0,
    shadow_step: float = 1.0,
    grad_top="#FFFFFF",
    grad_bottom="#FFFFFF",
):
    frames = load_stack(src, slices)
    grad_top_rgb = _hex_rgb(grad_top)
    grad_bot_rgb = _hex_rgb(grad_bottom)

    angles = range(0, 360, rot_inc)
    stacks = [
        build_stack(frames, a, v_step, squash, grad_top_rgb, grad_bot_rgb)
        for a in angles
    ]
    shadows = [
        build_shadow(frames, a, shadow_angle, shadow_step, squash) for a in angles
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    _sheet(stacks).save(out_dir / f"{src.stem}_obj.png")
    _sheet(shadows).save(out_dir / f"{src.stem}_shd.png")
