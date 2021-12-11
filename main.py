#!/usr/bin/env python
"""
Telegram Bot that prints the contents it receives in a thermal printer.
"""

# pylint: disable=C0116,W0613,C0301,W0511
# This program is dedicated to the public domain under the CC0 license.

import logging
import os
import sys
import subprocess
import html
import json
import logging
import traceback

from time import sleep
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from thermalprinter import ThermalPrinter, CodePage
from exceptions import NoPaperLeftException, NoPrinterFoundException

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=os.getenv('LOG_LEVEL', default='INFO'),
)

logger = logging.getLogger(__name__)

ADMIN_TELEGRAM_USER_ID = int(os.getenv('ADMIN_TELEGRAM_USER_ID', default=-1))
MAX_WIDTH = 384

PRINTER_DEVICE = os.getenv("PRINTER_DEVICE", default="/dev/serial0")
PRINTER_SETTINGS = {
  'port': PRINTER_DEVICE,
  'baudrate': 9600, # only valid value for tiny thermal printer
  'heat_time': 120,
  'heat_interval': 40,
  'most_heated_point': 3
}


def command_start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user.first_name
    update.message.reply_text(f'Hola {user}. Mándame fotos y se las imprimo a la abuela')


def command_exec(update: Update, context: CallbackContext) -> None:
    """
    Executes a command and replies with the stdout/stderr.
    This is useful to control the device without physical access to it.
    """
    # Limit this command to admins because it can be a security risk.
    is_admin = update.effective_user.id == ADMIN_TELEGRAM_USER_ID
    if not is_admin:
        update.message.reply_text(f'{update.effective_user.first_name}, no tienes permisos.')
        return

    update.message.reply_text('OK')
    commands = filter(None, update.message.text.split()[1:])
    try:
        result = subprocess.run(commands, capture_output=True, timeout=30, text=True)
        update.message.reply_text(f'return code {result.returncode}')
        if result.stdout:
            update.message.reply_text('stdout\n' + result.stdout)
        if result.stderr:
            update.message.reply_text('stderr\n' + result.stderr)
    except Exception as e:
        update.message.reply_text(f'Error: {e}')


def printer_installed() -> bool:
    device_found = Path(PRINTER_DEVICE).exists()
    if not device_found:
        logger.info('Printer not found')
    return device_found


def split_text(text: str, max_line_length: int = 32) -> list[str]:
    # Split in words removing multiple consecutive whitespaces
    words = filter(None, text.split())
    lines = ['']

    for word in words:
        # Truncate words longer than max_line_length to max_line_length
        word = word[0:max_line_length]
        last_line = lines[-1]

        if len(last_line) + 1 + len(word) <= max_line_length:
            lines[-1] = (last_line + ' ' + word) if last_line else word
        else:
            lines.append(word)

    return list(filter(None, lines))


# see printer docs at https://pypi.org/project/thermalprinter/
def require_printer(func):
    def wrapper(*args, **kwargs):
        if not printer_installed():
            raise NoPrinterFoundException()

        with ThermalPrinter(**PRINTER_SETTINGS) as printer:
            printer.online()

            # A small pause seems to be needed after coming online.
            # Otherwise calling printer.status() raises an exception
            sleep(0.05)

            # status is a dict {'movement': False, 'paper': True, 'temp': True, 'voltage': True}
            has_paper = printer.status(raise_on_error=False)['paper']
            if not has_paper:
                raise NoPaperLeftException()

            ret = func(printer, *args, **kwargs)

            printer.offline() # This should save some power
            return ret

    return wrapper


def ignore_old_updates(func):
    def wrapper(update, context, **kwargs):
        is_old = update.message.date < datetime.now(update.message.date.tzinfo) - timedelta(hours=24)
        if is_old:
            return None

        return func(update, context, **kwargs)

    return wrapper


@require_printer
def print_message(printer: ThermalPrinter, text: str) -> None:
    for line in split_text(text, max_line_length=printer.max_column):
        printer.out(line, double_height=True, bold=True, codepage=CodePage.ISO_8859_1)


@require_printer
def print_signature(printer: ThermalPrinter, author: str = None, timestamp = datetime.now()) -> None:
    human_date = timestamp.strftime("%d/%m/%Y")

    signature = f"{author}, {human_date}" if author else f"{human_date}"
    printer.out(signature, double_height=True, codepage=CodePage.ISO_8859_1)


@require_printer
def print_feed(printer: ThermalPrinter, amount: int = 2) -> None:
    printer.feed(amount)


@require_printer
def print_image(printer: ThermalPrinter, image: Image) -> None:
    printer.image(image)


@ignore_old_updates
def text_handler(update: Update, context: CallbackContext) -> None:
    print_message(update.message.text)
    print_signature(update.effective_user.first_name, update.message.date)
    print_feed()

    update.message.reply_text("OK")


@ignore_old_updates
def image_handler(update: Update, context: CallbackContext) -> None:
    best_quality_file = update.message.photo[-1] # last image is the biggest one
    file_id = best_quality_file.file_id
    file = context.bot.get_file(file_id)

    update.message.reply_text("Imprimiendo")

    image = prepare_image(file, best_quality_file.width, best_quality_file.height)
    print_image(image)

    if update.message.caption:
        print_message(update.message.caption)

    print_signature(update.effective_user.first_name, update.message.date)
    print_feed()

    update.message.reply_text("OK")


def prepare_image(file, width, height) -> Image:
    # see docs https://python-telegram-bot.readthedocs.io/en/stable/telegram.file.html#telegram.File.download
    # image.download() would download the file. We prefer not to use the SD card to extend its life.
    imagearray = file.download_as_bytearray()

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

    scale = image.width / float(MAX_WIDTH)
    image = image.resize((MAX_WIDTH, int(image.height / scale)))

    # Uncomment for debugging
    # image.show()

    # Dither the image (floyd-steinberg algorithm seems fine https://www.google.com/search?q=floyd-steinberg+dithering+python)
    # is NOT needed for now because the ThermalPrinter lib does it for us.
    # see https://thermalprinter.readthedocs.io/en/latest/api.html#thermalprinter.ThermalPrinter.image

    return image


# see https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/errorhandlerbot.py
def error_handler(update: object, context: CallbackContext) -> None:
    if isinstance(context.error, NoPaperLeftException):
        update.message.reply_text("No queda papel")

    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # XXX: add some logic to deal with messages longer than the 4096 char limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f'Exception\n'
        f'<pre>{html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n'
        f'<pre>{html.escape(tb_string)}</pre>'
    )

    context.bot.send_message(chat_id=ADMIN_TELEGRAM_USER_ID, text=message, parse_mode=ParseMode.HTML)


def main() -> None:
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        sys.exit(1)

    updater = Updater(token)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", command_start))
    dispatcher.add_handler(CommandHandler("exec", command_exec))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, text_handler))
    dispatcher.add_handler(MessageHandler(Filters.photo, image_handler))

    dispatcher.add_error_handler(error_handler)

    # use a higher poll interval when data usage is a constraint
    poll_interval=int(os.getenv('POLL_INTERVAL', default=30))
    updater.start_polling(poll_interval, allowed_updates=['message', 'photo'])

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
