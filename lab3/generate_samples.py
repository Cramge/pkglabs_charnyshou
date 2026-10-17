import random
from pathlib import Path

from PIL import Image, ImageDraw


def salt_pepper(folder):
    random.seed(10)
    width, height = 720, 460
    image = Image.new("RGB", (width, height), "#d9e7f2")
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 70, 650, 390), fill="#36618c")
    draw.ellipse((180, 105, 520, 360), fill="#efb366")
    draw.rectangle((285, 145, 435, 320), fill="#3e8f76")
    image.save(folder / "01_salt_pepper_clean.png")
    pixels = image.load()
    for _ in range(width * height // 12):
        x = random.randrange(width)
        y = random.randrange(height)
        value = 0 if random.random() < 0.5 else 255
        pixels[x, y] = (value, value, value)
    image.save(folder / "01_salt_pepper.png")


def bimodal(folder):
    width, height = 720, 460
    image = Image.new("L", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            base = 55 if x < width // 2 else 205
            texture = ((x * 13 + y * 7) % 25) - 12
            pixels[x, y] = max(0, min(255, base + texture))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 110, 300, 350), fill=215)
    draw.rectangle((440, 120, 610, 345), fill=45)
    image.convert("RGB").save(folder / "02_bimodal.png")


def uneven(folder):
    width, height = 760, 460
    image = Image.new("L", (width, height))
    truth = Image.new("L", (width, height), 255)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            light = 65 + int(175 * x / (width - 1))
            wave = int(10 * ((y % 80) / 80))
            pixels[x, y] = min(255, light + wave)
    draw = ImageDraw.Draw(image)
    mask = ImageDraw.Draw(truth)
    for row in range(6):
        top = 55 + row * 62
        for column in range(8):
            left = 38 + column * 88
            right = left + 58 + (column % 3) * 5
            draw.rectangle((left, top, right, top + 25), fill=max(0, pixels[left, top] - 48))
            mask.rectangle((left, top, right, top + 25), fill=0)
    image.convert("RGB").save(folder / "03_uneven_lighting.png")
    truth.save(folder / "03_uneven_ground_truth.png")


def small_details(folder):
    width, height = 720, 460
    image = Image.new("RGB", (width, height), "#202936")
    draw = ImageDraw.Draw(image)
    for row in range(7):
        for column in range(11):
            x = 35 + column * 63
            y = 35 + row * 58
            color = (45 + column * 15, 80 + row * 18, 160)
            draw.ellipse((x, y, x + 22 + row % 3, y + 22 + column % 4), fill=color)
    image.save(folder / "04_order_statistics.png")


def main():
    folder = Path(__file__).resolve().parent / "test_images"
    folder.mkdir(exist_ok=True)
    salt_pepper(folder)
    bimodal(folder)
    uneven(folder)
    small_details(folder)


if __name__ == "__main__":
    main()
