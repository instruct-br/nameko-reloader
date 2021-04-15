import argparse
import itertools
import logging
import os
import sys
import time
from importlib import import_module, reload
from types import ModuleType

import eventlet
import yaml
from nameko.cli.commands import commands
from nameko.cli.main import CommandError, ConfigurationError, setup_yaml_parser
from nameko.cli.run import import_service
from nameko.constants import AMQP_URI_CONFIG_KEY
from nameko.runners import ServiceRunner
from pkg_resources import get_distribution

from nameko_reloader.cli_commands import RunExtra

LOGGING = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "[%(asctime)s][%(levelname)s] %(name)s - %(message)s",
            "datefmt": "%H:%M:%S",
        }
    },
    "handlers": {
        "default": {
            "level": "INFO",
            "formatter": "default",
            "class": "logging.StreamHandler",
        }
    },
    "root": {
        "level": "INFO",
        "propagate": True,
        "handlers": ["default"],
    },
}


def custom_setup_parser():
    """
    Manually mount nameko parser, adding the RunExtra command, where the
    --restart option exists.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=get_distribution("nameko").version,
    )
    subparsers = parser.add_subparsers()
    commands.append(RunExtra)
    for command in commands:
        # Ignore the Run command, we change it to RunExtra
        if command.name == "Run":
            continue
        command_parser = subparsers.add_parser(
            command.name, description=command.__doc__
        )
        command.init_parser(command_parser)
        command_parser.set_defaults(main=command.main)
    return parser


def reload_modules(modules):
    """
    Reloads the services modules, so changes made in code can be loaded.
    """
    for module in modules:
        reload(module)


def reload_classes(modules):
    """
    Reloads modules classes, so changes made to them can be loaded.
    """
    classes = [import_service(module.__name__) for module in modules]
    classes = list(itertools.chain(*classes))
    return classes


def main():
    eventlet.monkey_patch()
    parser = custom_setup_parser()
    args = parser.parse_args()
    setup_yaml_parser()

    if "." not in sys.path:
        sys.path.insert(0, ".")

    if args.config:
        with open(args.config) as file:
            config = yaml.unsafe_load(file)
    else:
        config = {AMQP_URI_CONFIG_KEY: args.broker}

    if config.get('LOGGING'):
        logging.config.dictConfig(config["LOGGING"])
    else:
        logging.config.dictConfig(LOGGING)

    try:
        if args.reload:
            modules = []
            for module in [import_module(module) for module in args.services]:
                if module.__file__.endswith("__init__.py"):
                    modules.extend(
                        [
                            getattr(module, m)
                            for m in dir(module)
                            if type(getattr(module, m)) == ModuleType
                        ]
                    )
                else:
                    modules.append(module)
            file_paths = [module.__file__ for module in modules]

            classes = reload_classes(modules)
            class_names = ", ".join([c.name for c in classes])
            logging.info('Starting services: %s', class_names)

            runner = ServiceRunner(config=config)
            [runner.add_service(class_) for class_ in classes]
            last_update_time_files = [
                os.stat(file).st_mtime for file in file_paths
            ]
            runner.start()
            logging.debug('Services started: %s', class_names)

            while True:
                for path in file_paths:
                    last_update_time = os.stat(path).st_mtime
                    if last_update_time not in last_update_time_files:
                        last_update_time_files.append(last_update_time)
                        logging.debug(f"Changes detected in {path}")
                        logging.info("Reloading services...")
                        runner.stop()
                        runner.wait()
                        reload_modules(modules)
                        classes = reload_classes(modules)
                        runner = ServiceRunner(config=config)
                        [runner.add_service(class_) for class_ in classes]
                        runner.start()
                        logging.info("Services reloaded: %s", class_names)
                    else:
                        time.sleep(1)
        else:
            args.main(args)
    except (CommandError, ConfigurationError) as exc:
        logging.error("Error: {}".format(exc))


if __name__ == "__main__":
    main()
