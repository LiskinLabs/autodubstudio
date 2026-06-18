"""Generate all app icon sizes from user's source icon."""
import os

from PIL import Image

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


def save_ico_pillow(png_src, ico_path):
    """Use Pillow's built-in ICO save (produces valid DIB)."""
    img = Image.open(png_src).convert('RGBA')
    sizes = [(256,256), (128,128), (64,64), (48,48), (32,32), (16,16)]
    images = [img.resize(s, Image.LANCZOS) for s in sizes]
    # Save first image as ICO with all sizes embedded
    images[0].save(ico_path, format='ICO', sizes=[s for s in sizes], append_images=images[1:])


if __name__ == '__main__':
    print(f"Loading source: {SOURCE}")
    src = Image.open(SOURCE).convert('RGBA')
    w, h = src.size
    # Fit into square with transparent padding (NO crop)
    side = max(w, h)
    base = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    paste_x = (side - w) // 2
    paste_y = (side - h) // 2
    base.paste(src, (paste_x, paste_y))
    print(f"  Source: {w}x{h} -> fitted to: {side}x{side} (no crop)")

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

    # icon.ico (using Pillow's built-in ICO writer — valid DIB)
    icon_ico = os.path.join(OUT, 'icon.ico')
    save_ico_pillow(icon_png, icon_ico)
    print(f'  {icon_ico}')

    # icon.icns (copy PNG)
    import shutil
    shutil.copy(icon_png, os.path.join(OUT, 'icon.icns'))
    print('  icon.icns')

    # Copy for web UI
    logo_png = os.path.normpath(os.path.join(OUT, '..', '..', 'public', 'logo-icon.png'))
    base.resize((128, 128), Image.LANCZOS).save(logo_png, 'PNG')
    print(f'  {logo_png}')

    print("\nDone!")
