"""Generate all app icon sizes from user's source icon."""
from PIL import Image
import os, struct, shutil

OUT = os.path.dirname(os.path.abspath(__file__))
SOURCE = r"C:\Users\silvestr.liskin\Downloads\edited-photo (2).png"

SQUARE_SIZES = [
    ('Square30x30Logo.png', 30), ('Square44x44Logo.png', 44),
    ('Square71x71Logo.png', 71), ('Square89x89Logo.png', 89),
    ('Square107x107Logo.png', 107), ('Square142x142Logo.png', 142),
    ('Square150x150Logo.png', 150), ('Square284x284Logo.png', 284),
    ('Square310x310Logo.png', 310), ('StoreLogo.png', 50),
]

STANDARD = [32, 44, 71, 89, 107, 128, 142, 150, 284, 310]


def save_ico(png256, ico_path):
    img = Image.open(png256).convert('RGBA')
    sizes = [(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]
    images = [img.resize(s, Image.LANCZOS) for s in sizes]
    with open(ico_path, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 1, len(images)))
        offset = 6 + 16 * len(images)
        for (w, h), im in zip(sizes, images):
            b = w if w < 256 else 0
            f.write(struct.pack('<BBBBHHII', b, b, 0, 0, 1, 32, w*h*4, offset))
            offset += w * h * 4
        for (w, h), im in zip(sizes, images):
            rgba = im.resize((w, h), Image.LANCZOS).convert('RGBA')
            raw = bytearray()
            for y in range(h):
                for x in range(w):
                    r, g, b, a = rgba.getpixel((x, y))
                    raw.extend([b, g, r, a])
            f.write(bytes(raw))


if __name__ == '__main__':
    print(f"Loading source: {SOURCE}")
    base = Image.open(SOURCE).convert('RGBA')
    print(f"  Original size: {base.size}")

    # Crop to square (center crop)
    w, h = base.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    base = base.crop((left, top, left + side, top + side))
    print(f"  Cropped to square: {base.size}")

    # Standard PNG icons
    for s in STANDARD:
        path = os.path.join(OUT, f'{s}x{s}.png')
        base.resize((s, s), Image.LANCZOS).save(path, 'PNG')
        print(f'  {path}')

    # 2x retina
    path2x = os.path.join(OUT, '128x128@2x.png')
    base.resize((256, 256), Image.LANCZOS).save(path2x, 'PNG')
    print(f'  {path2x}')

    # Square logos for Windows
    for name, s in SQUARE_SIZES:
        path = os.path.join(OUT, name)
        base.resize((s, s), Image.LANCZOS).save(path, 'PNG')
        print(f'  {path}')

    # icon.png (512x512)
    icon_png = os.path.join(OUT, 'icon.png')
    base.resize((512, 512), Image.LANCZOS).save(icon_png, 'PNG')

    # icon.ico
    icon_ico = os.path.join(OUT, 'icon.ico')
    save_ico(icon_png, icon_ico)
    print(f'  {icon_ico}')

    # icon.icns (copy PNG)
    shutil.copy(icon_png, os.path.join(OUT, 'icon.icns'))
    print('  icon.icns')

    # Also copy as logo for web UI
    logo_png = os.path.normpath(os.path.join(OUT, '..', '..', 'public', 'logo-icon.png'))
    base.resize((128, 128), Image.LANCZOS).save(logo_png, 'PNG')
    print(f'  {logo_png}')

    print("\nDone! All icons generated from user's source image.")
