from io import BytesIO
from PIL import Image, ImageEnhance


def beautify(imagearray: bytearray, width: int, height: int, max_width: int) -> Image:
    image = Image.open(BytesIO(imagearray))

    is_landscape = width > height
    if is_landscape:
        # Set expand=True to change the aspect ratio of the image, otherwise it is rotated&cropped
        image = image.rotate(90, expand=True)

    # Some tests trying to improve the quality of the printed image.
    # see https://hhsprings.bitbucket.io/docs/programming/examples/python/PIL/ImageOps.html
    # image = ImageOps.autocontrast(image)
    # image = ImageOps.grayscale(image)
    # image = ImageOps.equalize(image)
    image = ImageEnhance.Sharpness(image).enhance(2.5)

    scale = image.width / float(max_width)
    image = image.resize((max_width, int(image.height / scale)))

    # Uncomment for debugging
    # image.show()

    # Dither the image (floyd-steinberg algorithm seems fine https://www.google.com/search?q=floyd-steinberg+dithering+python)
    # is NOT needed for now because the ThermalPrinter lib does it for us.
    # see https://thermalprinter.readthedocs.io/en/latest/api.html#thermalprinter.ThermalPrinter.image

    return image