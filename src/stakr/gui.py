import base64, io
from pathlib import Path

import flet as ft
from PIL import Image

from . import core
from .utils import pinfo


HOME     = Path.home()
ROOT_DIR = Path("~/Desktop/art/games/lustrum/stacks").expanduser()
OUT_DIR  = ROOT_DIR / "stack_sheets"


def _user_path(p: Path) -> str:
    return str(p).replace(str(HOME), "~")


def _b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _merge(obj: Image.Image, sh: Image.Image) -> Image.Image:
    ox, oy = obj.info["origin"]
    sx, sy = sh.info["origin"]
    left  = max(ox, sx)
    right = max(obj.width - ox, sh.width - sx)
    h     = max(oy, sy)
    c = Image.new("RGBA", (left + right, h), (255, 255, 255, 0))
    c.alpha_composite(sh, (left - sx, h - sh.height))
    c.alpha_composite(obj, (left - ox, h - obj.height))
    return c


def _hex_rgb(hexstr: str):
    s = hexstr.lstrip("#")
    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))


# GUI ----------------------------------------------------------------------
def main(page: ft.Page):
    page.title = "Stakr"
    page.padding = 16

    png: Path | None = None
    frames: list[str] = []
    idx = [0]

    # inputs
    slices   = ft.TextField(label="Slices", value="125", width=80)
    rot_inc  = ft.TextField(label="Rot Δ°", value="36",  width=70)
    v_step   = ft.TextField(label="v_step", value="-1", width=70)
    squash   = ft.TextField(label="squash", value="1.0", width=70)
    sh_angle = ft.TextField(label="shadow °", value="40", width=90)
    sh_step  = ft.TextField(label="shadow step", value="1.0", width=100)
    grad_top = ft.TextField(label="grad top", value="#FFFFFF", width=100)
    grad_bot = ft.TextField(label="grad bottom", value="#FFFFFF", width=100)

    pick = ft.ElevatedButton("PNG")
    path = ft.TextField(read_only=True, width=360)
    render = ft.ElevatedButton("Render", disabled=True)
    status = ft.Text()

    img_view = ft.Image(visible=False, fit=ft.ImageFit.CONTAIN)
    box = ft.Container(content=img_view, bgcolor=ft.Colors.WHITE, alignment=ft.alignment.center)

    prev = ft.ElevatedButton("←", disabled=True)
    nxt  = ft.ElevatedButton("→", disabled=True)
    f_lbl= ft.Text()

    page.add(
        ft.Column(
            [
                ft.Text("General", weight="bold"),
                ft.Row([slices, rot_inc, pick, path], spacing=6),

                ft.Text("Object stack", weight="bold"),
                ft.Row([v_step, squash, grad_top, grad_bot], spacing=6),

                ft.Text("Shadow", weight="bold"),
                ft.Row([sh_angle, sh_step], spacing=6),

                render,
                status,
                ft.Row([prev, box, nxt, f_lbl], alignment="end", spacing=8),
            ],
            spacing=10,
        )
    )

    # picker
    picker = ft.FilePicker(on_result=lambda e: _picked(e))
    page.overlay.append(picker)
    page.update()

    def _picked(e):
        nonlocal png
        if e.files:
            png = Path(e.files[0].path)
            path.value = _user_path(png)
            render.disabled = False
            page.update()

    pick.on_click = lambda _: picker.pick_files(allowed_extensions=["png"], initial_directory=str(ROOT_DIR))

    # preview
    def _show():
        if not frames:
            return
        img_view.src_base64 = frames[idx[0] % len(frames)]
        img_view.visible = True
        f_lbl.value = f"{idx[0] % len(frames)+1}/{len(frames)}"
        page.update()

    # render
    def _render(_):
        if png is None:
            return

        params = dict(
            slices=int(slices.value),
            rot_inc=int(rot_inc.value),
            v_step=int(v_step.value),
            squash=float(squash.value),
            shadow_angle=float(sh_angle.value),
            shadow_step=float(sh_step.value),
            grad_top=grad_top.value or "#FFFFFF",
            grad_bottom=grad_bot.value or "#FFFFFF",
        )

        # RGB tuples for preview build_stack
        top_rgb = _hex_rgb(params["grad_top"])
        bot_rgb = _hex_rgb(params["grad_bottom"])

        base = core.load_stack(png, params["slices"])
        angles = range(0, 360, params["rot_inc"])

        obj_frames = [
            core.build_stack(base, a, params["v_step"], params["squash"], top_rgb, bot_rgb)
            for a in angles
        ]
        shd_frames = [
            core.build_shadow(base, a, params["shadow_angle"], params["shadow_step"], params["squash"])
            for a in angles
        ]

        # lock preview box
        w = max(max(o.width for o in obj_frames), max(s.width for s in shd_frames)) + 20
        h = max(max(o.height for o in obj_frames), max(s.height for s in shd_frames)) + 20
        box.width, box.height = w, h
        img_view.width, img_view.height = w - 20, h - 20

        frames.clear()
        frames.extend(_b64(_merge(o, s)) for o, s in zip(obj_frames, shd_frames))
        idx[0] = 0
        _show()

        core.bake(png, OUT_DIR, **params)
        status.value = f"✅ saved → {_user_path(OUT_DIR)}"
        prev.disabled = nxt.disabled = False
        page.update()

    render.on_click = _render
    prev.on_click   = lambda _: (idx.__setitem__(0, idx[0]-1), _show())
    nxt.on_click    = lambda _: (idx.__setitem__(0, idx[0]+1), _show())


def run():
    pinfo("Launching GUI")
    ft.app(target=main)
