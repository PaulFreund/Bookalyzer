"""Draw the app's geometric book-spine mark; no external artwork or fonts."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
canvas = Image.new("RGBA", (1024, 1024))
draw = ImageDraw.Draw(canvas)
draw.rounded_rectangle((52, 52, 972, 972), radius=205, fill="#7360bd")
books = Image.new("RGBA", canvas.size)
pen = ImageDraw.Draw(books)
for box, color in [((268, 325, 375, 756), "#d6cef5"), ((425, 245, 550, 792), "#ffffff"), ((600, 349, 717, 718), "#bcb0e7")]:
    pen.rounded_rectangle(box, radius=24, fill=color)
canvas.alpha_composite(books.rotate(12, resample=Image.Resampling.BICUBIC))
canvas.save(root / "desktop/icon.png")
