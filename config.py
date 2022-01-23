import pickle
from pathlib import Path

CONFIG_FILE = Path("ludivina.conf")


def read_config(default_config: set = {}) -> set:
    first_launch = not Path(CONFIG_FILE).exists()
    if first_launch:
        write_config(default_config)

    with open(CONFIG_FILE, 'rb') as file:
        return pickle.load(file)


def write_config(config) -> None:
    with open(CONFIG_FILE, 'wb') as file:
        pickle.dump(config, file)

