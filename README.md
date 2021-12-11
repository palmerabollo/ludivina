# Ludivina

Ludivina - Thermal Printer Bot for Telegram

## How to run it

You need a Telegram bot and its token [provided by BotFather](https://t.me/BotFather). This is the only required env var.

```sh
export TELEGRAM_TOKEN=xyz
```

Dependencies are managed with [poetry](https://python-poetry.org/docs/#osx--linux--bashonwindows-install-instructions). Python 3.10+ is needed.

```sh
poetry install
poetry run python main.py
```

It has been tested with [Adafruit's Tiny Thermal Receipt Printer](https://www.adafruit.com/product/2751). The thermal printer should be available at `/dev/serial0`. Otherwise export the `PRINTER_DEVICE` environment variable.

# License

Ludivina - Thermal Printer Bot for Telegram
Copyright (C) 2021  Guido García

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.