#!/usr/bin/env python
"""
Telegram Bot that prints the contents it receives in a thermal printer.
"""

# pylint: disable=C0116,W0613,C0301,W0511
# This program is dedicated to the public domain under the CC0 license.

import html
import json
import logging
import os
import subprocess
import sys
import traceback

from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from PIL import Image
from telegram import ParseMode, Update
from telegram.ext import (CallbackContext, CommandHandler, Filters,
                          MessageHandler, Updater)
from thermalprinter import CodePage, ThermalPrinter
from exceptions import NoPaperLeftException, NoPrinterFoundException

from image import beautify
from utils import split_text
from config import read_config, write_config

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=os.getenv('LOG_LEVEL', default='INFO'),
)

logger = logging.getLogger(__name__)

ADMIN_TELEGRAM_USER_ID = int(os.getenv('ADMIN_TELEGRAM_USER_ID', default=-1))
ALLOWED_TELEGRAM_USER_IDS = read_config(default_config = set([ADMIN_TELEGRAM_USER_ID]))

MAX_WIDTH = 384

PRINTER_DEVICE = os.getenv("PRINTER_DEVICE", default="/dev/serial0")
PRINTER_SETTINGS = {
  'port': PRINTER_DEVICE,
  'baudrate': 9600, # only valid value for tiny thermal printer
  'heat_time': 120,
  'heat_interval': 40,
  'most_heated_point': 3
}


def auth(admin: bool = False):
    def decorator(func):
        def wrapper(update: Update, context: CallbackContext, **kwargs):
            if admin:
                is_admin = update.effective_user.id == ADMIN_TELEGRAM_USER_ID
                if not is_admin:
                    update.message.reply_text(f'{update.effective_user.first_name}, no tienes permisos de administración.')
                    return

            is_allowed = update.effective_user.id in ALLOWED_TELEGRAM_USER_IDS
            if not is_allowed:
                update.message.reply_text(f'{update.effective_user.first_name}, todavía no tienes permiso.')

                message = f"El usuario {update.effective_user.first_name} {update.effective_user.last_name} " \
                        f"con id {update.effective_user.id} ({update.effective_user.username}) no tiene autorización."
                context.bot.send_message(chat_id=ADMIN_TELEGRAM_USER_ID, text=message)

                return

            update.message.reply_text('Recibido')
            result = func(update, context, **kwargs)
            update.message.reply_text('OK')
            return result

        return wrapper
    return decorator


def printer_installed() -> bool:
    device_found = Path(PRINTER_DEVICE).exists()
    if not device_found:
        logger.info('Printer not found')
    return device_found


# see printer docs at https://pypi.org/project/thermalprinter/
def require_printer(func):
    def wrapper(*args, **kwargs):
        if not printer_installed():
            # Uncomment for debugging if you don't have a printer
            # return
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
    def wrapper(update: Update, context: CallbackContext, **kwargs):
        is_old = update.message.date < datetime.now(update.message.date.tzinfo) - timedelta(hours=24)
        if is_old:
            return None

        return func(update, context, **kwargs)

    return wrapper


def command_start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user.first_name
    update.message.reply_text(f'Hola {user}. Mándame fotos y se las imprimo a la abuela')


@auth(admin=True)
def command_exec(update: Update, context: CallbackContext) -> None:
    """
    Executes a command and replies with the stdout/stderr.
    This is useful to control the device without physical access to it.
    """
    try:
        result = subprocess.run(context.args, capture_output=True, timeout=30, text=True)
        update.message.reply_text(f'return code {result.returncode}')
        if result.stdout:
            update.message.reply_text('stdout\n' + result.stdout)
        if result.stderr:
            update.message.reply_text('stderr\n' + result.stderr)
    except Exception as e:
        update.message.reply_text(f'Error: {e}')


@auth(admin=True)
def command_add(update: Update, context: CallbackContext) -> None:
    """
    Authorizes users so it can interact with the bot.
    """
    ALLOWED_TELEGRAM_USER_IDS.update(map(int, context.args))
    write_config(ALLOWED_TELEGRAM_USER_IDS)
    update.message.reply_text(f'Authorized users {ALLOWED_TELEGRAM_USER_IDS}')


@auth(admin=True)
def command_remove(update: Update, context: CallbackContext) -> None:
    """
    Deauthorizes a user so it can't use the bot anymore.
    """
    if str(ADMIN_TELEGRAM_USER_ID) in context.args:
        update.message.reply_text(f'Not able to deauthorize admin user {ADMIN_TELEGRAM_USER_ID}')
        return

    ALLOWED_TELEGRAM_USER_IDS.difference_update(map(int, context.args))
    write_config(ALLOWED_TELEGRAM_USER_IDS)
    update.message.reply_text(f'Authorized users {ALLOWED_TELEGRAM_USER_IDS}')


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


@auth()
@ignore_old_updates
def text_handler(update: Update, context: CallbackContext) -> None:
    print_message(update.message.text)
    print_signature(update.effective_user.first_name, update.message.date)
    print_feed()


@auth()
@ignore_old_updates
def image_handler(update: Update, context: CallbackContext) -> None:
    best_quality_file = update.message.photo[-1] # last image is the biggest one
    file_id = best_quality_file.file_id
    file = context.bot.get_file(file_id)

    # see docs https://python-telegram-bot.readthedocs.io/en/stable/telegram.file.html#telegram.File.download
    # image.download() would download the file. We prefer not to use the SD card to extend its life.
    imagearray = file.download_as_bytearray()

    image = beautify(imagearray, best_quality_file.width, best_quality_file.height, max_width=MAX_WIDTH)
    print_image(image)

    if update.message.caption:
        print_message(update.message.caption)

    print_signature(update.effective_user.first_name, update.message.date)
    print_feed()


# see https://github.com/python-telegram-bot/python-telegram-bot/blob/master/examples/errorhandlerbot.py
def error_handler(update: object, context: CallbackContext) -> None:
    if isinstance(context.error, NoPaperLeftException):
        update.message.reply_text("No queda papel")
    else:
        update.message.reply_text("Algo no ha ido bien")

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
    if not os.getenv('ADMIN_TELEGRAM_USER_ID'):
        logger.error("ADMIN_TELEGRAM_USER_ID is not set")
        sys.exit(1)

    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        logger.error("TELEGRAM_TOKEN is not set")
        sys.exit(1)

    updater = Updater(token)

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", command_start))
    dispatcher.add_handler(CommandHandler("exec", command_exec))
    dispatcher.add_handler(CommandHandler("add", command_add))
    dispatcher.add_handler(CommandHandler("remove", command_remove))
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
