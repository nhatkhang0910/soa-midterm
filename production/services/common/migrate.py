import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def main():
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parents[1] / os.environ["SERVICE_NAME"] / "migrations"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
