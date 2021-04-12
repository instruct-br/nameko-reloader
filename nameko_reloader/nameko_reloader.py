import os
import sys
import time
import argparse
import eventlet
import itertools
import yaml
import logging
from importlib import reload, import_module
from pkg_resources import get_distribution
from nameko.constants import AMQP_URI_CONFIG_KEY
from nameko.cli.main import setup_yaml_parser, CommandError, ConfigurationError
from nameko.cli.run import import_service
from nameko.cli.commands import commands
from nameko.runners import ServiceRunner
from nameko_reloader.cli_commands import RunExtra


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


def reload_classes(services):
    """
    Reloads modules classes, so changes made to them can be loaded.
    """
    classes = [import_service(service) for service in services]
    classes = list(itertools.chain(*classes))
    return classes


def main():
    eventlet.monkey_patch()
    parser = custom_setup_parser()
    args = parser.parse_args()
    setup_yaml_parser()

    if args.config:
        with open(args.config) as file:
            config = yaml.unsafe_load(file)
    else:
        config = {
            AMQP_URI_CONFIG_KEY: args.broker,
            "LOGGING": {
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
            },
        }
    logging.config.dictConfig(config.get('LOGGING'))

    try:
        if args.reload:
            modules = [import_module(module) for module in args.services]
            file_paths = [module.__file__ for module in modules]

            # Check if services arg is a folder with an __init__ file:
            # If true, file_paths must contain the path of every service
            if len(file_paths) == 1 and '__init__' in file_paths[0]:
                file_paths = os.path.join(os.getcwd(), file_paths[0]).replace(
                    '__init__.py', ''
                )
                file_paths = [file_paths + i for i in os.listdir(file_paths)]

            classes = reload_classes(args.services)
            logging.info("Starting services...")
            runner = ServiceRunner(config=config)
            [runner.add_service(class_) for class_ in classes]
            last_update_time_files = [
                os.stat(file).st_mtime for file in file_paths
            ]
            runner.start()
            logging.info("Services up!")

            while True:
                for file in file_paths:
                    last_update_time = os.stat(file).st_mtime
                    if last_update_time not in last_update_time_files:
                        last_update_time_files.append(last_update_time)
                        logging.info(f"Changes detected in {file}")
                        logging.info("Reloading services...")
                        runner.stop()
                        runner.wait()
                        reload_modules(modules)
                        classes = reload_classes(args.services)
                        runner = ServiceRunner(config=config)
                        [runner.add_service(class_) for class_ in classes]
                        runner.start()
                        logging.info("Services reloaded")
                    else:
                        time.sleep(1)
        else:
            args.main(args)
    except (CommandError, ConfigurationError) as exc:
        logging.error("Error: {}".format(exc))


if __name__ == "__main__":
    main()
