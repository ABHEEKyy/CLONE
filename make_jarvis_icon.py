import math
from PIL import Image, ImageDraw, ImageFilter

def create_jarvis_icon(filename="jarvis_icon.ico"):
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = (128, 128)

    # 1. Dark outer metallic circle
    draw.ellipse([8, 8, 248, 248], fill=(10, 18, 30, 255), outline=(0, 200, 255, 255), width=4)

    # 2. Glowing Outer Ring
    for r, alpha in [(115, 60), (110, 100), (105, 180), (100, 255)]:
        bbox = [center[0] - r, center[1] - r, center[0] + r, center[1] + r]
        draw.ellipse(bbox, outline=(0, 230, 255, alpha), width=3)

    # 3. Futuristic Arc Reactor Segments (12 radial tick marks)
    for i in range(12):
        angle = math.radians(i * 30)
        x1 = center[0] + int(72 * math.cos(angle))
        y1 = center[1] + int(72 * math.sin(angle))
        x2 = center[0] + int(96 * math.cos(angle))
        y2 = center[1] + int(96 * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=(0, 240, 255, 230), width=4)

    # 4. Inner Core Ring & Glowing Orb
    draw.ellipse([64, 64, 192, 192], fill=(5, 40, 70, 255), outline=(0, 240, 255, 255), width=3)
    draw.ellipse([80, 80, 176, 176], fill=(0, 180, 240, 255))
    draw.ellipse([96, 96, 160, 160], fill=(220, 250, 255, 255))

    # Save as .ico containing standard Windows icon sizes
    img.save(
        filename,
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )
    print(f"[SUCCESS] Generated custom J.A.R.V.I.S. icon: {filename}")

if __name__ == "__main__":
    create_jarvis_icon()
