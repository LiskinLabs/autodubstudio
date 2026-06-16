"""Generate all app icon sizes from the AD monogram design."""
from PIL import Image, ImageDraw
import os, struct

OUT = os.path.dirname(os.path.abspath(__file__))
SIZES = [32, 44, 71, 89, 107, 128, 142, 150, 284, 310]
SQUARE_SIZES = [
    ('Square30x30Logo.png', 30),
    ('Square44x44Logo.png', 44),
    ('Square71x71Logo.png', 71),
    ('Square89x89Logo.png', 89),
    ('Square107x107Logo.png', 107),
    ('Square142x142Logo.png', 142),
    ('Square150x150Logo.png', 150),
    ('Square284x284Logo.png', 284),
    ('Square310x310Logo.png', 310),
    ('StoreLogo.png', 50),
]

GRADIENT_TOP = (99, 102, 241)    # #6366f1 indigo
GRADIENT_BOT = (139, 92, 246)    # #8b5cf6 violet

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i])*t) for i in range(3))

def draw_icon(size):
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    d = ImageDraw.Draw(img)

    # Gradient circle background
    r = int(size * 0.47)
    cx, cy = size//2, size//2
    for y in range(cy-r, cy+r):
        for x in range(cx-r, cx+r):
            if (x-cx)**2 + (y-cy)**2 <= r**2:
                t = (y - (cy-r)) / (2*r)
                color = lerp(GRADIENT_TOP, GRADIENT_BOT, t)
                d.point((x, y), fill=color)

    # Ring border
    ring_r = int(size * 0.46)
    ring_w = max(2, size // 80)
    for y in range(cy-ring_r-ring_w, cy+ring_r+ring_w):
        for x in range(cx-ring_r-ring_w, cx+ring_r+ring_w):
            dist = ((x-cx)**2 + (y-cy)**2) ** 0.5
            if ring_r <= dist <= ring_r + ring_w:
                d.point((x, y), fill=(255,255,255,38))

    # A and D letters
    letter_h = int(size * 0.44)
    letter_w = int(letter_h * 0.75)
    letter_y = cy - letter_h // 2

    # A position
    ax = int(cx - letter_w * 0.7)
    ay = letter_y

    # A — two diagonal strokes + crossbar
    stroke = max(3, size // 28)
    a_top = (cx - int(letter_w*0.45), ay + letter_h)
    a_left = (ax, ay + letter_h)
    a_right = (ax + int(letter_w*0.8), ay + letter_h)
    cross_y = ay + int(letter_h * 0.55)

    # Left leg of A
    for s in range(stroke):
        dx = (a_top[0] - a_left[0])
        dy = (a_top[1] - a_left[1])
        steps = max(abs(dx), abs(dy))
        for i in range(steps):
            t = i / steps
            x = int(a_left[0] + dx*t + s*0.3)
            y = int(a_left[1] + dy*t)
            if 0 <= x < size and 0 <= y < size:
                d.point((x, y), fill=(255,255,255,242))

    # Right leg of A
    for s in range(stroke):
        dx = (a_top[0] - a_right[0])
        dy = (a_top[1] - a_right[1])
        steps = max(abs(dx), abs(dy))
        for i in range(steps):
            t = i / steps
            x = int(a_right[0] + dx*t - s*0.3)
            y = int(a_right[1] + dy*t)
            if 0 <= x < size and 0 <= y < size:
                d.point((x, y), fill=(255,255,255,242))

    # Crossbar
    bar_left = int(ax + letter_w * 0.15)
    bar_right = int(ax + letter_w * 0.65)
    for y in range(cross_y - stroke//2, cross_y + stroke//2):
        for x in range(bar_left, bar_right):
            if 0 <= x < size and 0 <= y < size:
                d.point((x, y), fill=(255,255,255,242))

    # D position
    dx = int(cx + letter_w * 0.15)
    dy = ay
    d_width = int(letter_w * 0.55)
    d_height = letter_h

    # D left vertical
    for y in range(dy, dy + d_height):
        for sx in range(dx, dx + stroke):
            if 0 <= sx < size and 0 <= y < size:
                d.point((sx, y), fill=(255,255,255,242))

    # D arc
    arc_cx = dx + d_width // 2
    arc_cy = dy + d_height // 2
    arc_rx = d_width // 2
    arc_ry = d_height // 2 - stroke // 2
    for y in range(dy + stroke, dy + d_height - stroke):
        for x in range(dx + stroke, dx + d_width):
            ex = (x - arc_cx) / arc_rx
            ey = (y - arc_cy) / arc_ry
            if 0.7 <= ex*ex + ey*ey <= 1.0:
                if 0 <= x < size and 0 <= y < size:
                    d.point((x, y), fill=(255,255,255,242))

    return img


def save_ico(png_path, ico_path):
    """Convert a 256x256 PNG to a multi-resolution ICO file."""
    img = Image.open(png_path)
    sizes = [(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]
    images = [img.resize(s, Image.LANCZOS) for s in sizes]

    # Write ICO
    with open(ico_path, 'wb') as f:
        # ICO header
        f.write(struct.pack('<HHH', 0, 1, len(images)))
        offset = 6 + 16 * len(images)
        datas = []
        for im in sizes:
            w, h = im
            b = w if w < 256 else 0
            f.write(struct.pack('<BBBBHHII', b, b, 0, 0, 1, 32, im[0]*im[1]*4, offset))
            offset += im[0] * im[1] * 4
        for im, (w,h) in zip(images, sizes):
            # Write as BGRA PNG data
            rgba = im.resize((w,h), Image.LANCZOS).convert('RGBA')
            raw = bytearray()
            for y in range(h):
                for x in range(w):
                    r,g,b,a = rgba.getpixel((x,y))
                    raw.extend([b,g,r,a])
            f.write(bytes(raw))


if __name__ == '__main__':
    print("Generating icons...")

    # Main PNG icons
    for s in SIZES:
        path = os.path.join(OUT, f'{s}x{s}.png')
        img = draw_icon(s)
        img.save(path, 'PNG')
        print(f'  {path}')

    # 2x versions
    for s in [128]:
        img2x = draw_icon(s * 2)
        path2x = os.path.join(OUT, f'{s}x{s}@2x.png')
        img2x.save(path2x, 'PNG')
        print(f'  {path2x}')

    # Square logos for Windows
    for name, s in SQUARE_SIZES:
        path = os.path.join(OUT, name)
        img = draw_icon(s)
        img.save(path, 'PNG')
        print(f'  {path}')

    # icon.png (512x512)
    icon_png = os.path.join(OUT, 'icon.png')
    img = draw_icon(512)
    img.save(icon_png, 'PNG')

    # icon.ico
    icon_ico = os.path.join(OUT, 'icon.ico')
    save_ico(icon_png, icon_ico)
    print(f'  {icon_ico}')

    # icon.icns (just copy PNG for now — macOS uses it)
    import shutil
    icns = os.path.join(OUT, 'icon.icns')
    shutil.copy(icon_png, icns)
    print(f'  {icns}')

    print("Done! All icons generated.")
