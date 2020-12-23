import os
import sys
import time
import argparse
import eventlet
import itertools
import yaml
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
    Monto manualmente o parser do nameko, para utilizar o command RunExtra,
    onde adicionei a nova opção --restart
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v", "--version", action="version", version=get_distribution("nameko").version
    )
    subparsers = parser.add_subparsers()
    commands.append(RunExtra)
    for command in commands:
        # Ignora o command Run, pois ele foi substituído pelo RunExtra
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
    Recarrega os módulos dos serviços para que as alterações feitas no código
    sejam carregadas.
    """
    for module in modules:
        reload(module)


def reload_classes(services):
    """
    Recarrega as classes dos módulos, para que as alterações feitas nas mesmas
    sejam carregadas.
    """
    classes = [import_service(service) for service in services]
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
        with open(args.config) as fle:
            config = yaml.unsafe_load(fle)
    else:
        config = {AMQP_URI_CONFIG_KEY: args.broker}

    try:
        if args.reload:
            modules = [import_module(module) for module in args.services]
            file_paths = [module.__file__ for module in modules]
            classes = reload_classes(args.services)
            print("Starting services...")
            runner = ServiceRunner(config=config)
            [runner.add_service(class_) for class_ in classes]
            last_update_time_files = [os.stat(file).st_mtime for file in file_paths]
            runner.start()
            print("Services up!")

            while True:
                for file in file_paths:
                    last_update_time = os.stat(file).st_mtime
                    if last_update_time not in last_update_time_files:
                        last_update_time_files.append(last_update_time)
                        print(f"Changes detected in {file}")
                        print("Reloading services...")
                        # Para o serviço atual
                        runner.stop()
                        runner.wait()
                        # Recarrega os módulos com as novas alterações
                        reload_modules(modules)
                        # Inicia o serviço novamente
                        classes = reload_classes(args.services)
                        runner = ServiceRunner(config=config)
                        [runner.add_service(class_) for class_ in classes]
                        runner.start()
                        print("Services reloaded")
                    else:
                        time.sleep(1)
        else:
            args.main(args)
    except (CommandError, ConfigurationError) as exc:
        print("Error: {}".format(exc))


if __name__ == "__main__":
    main()
