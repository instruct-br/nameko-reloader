from nameko.cli.commands import Run


class RunExtra(Run):
    """
    Nameko run command with additional args
    """

    name = "run"

    @staticmethod
    def init_parser(parser):
        parser.add_argument(
            "services",
            nargs="+",
            metavar="module[:service class]",
            help="python path to one or more service classes to run",
        )
        parser.add_argument(
            "--config", default="", help="The YAML configuration file"
        )
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Reload services on file changes",
        )
        parser.add_argument(
            "--broker",
            default="pyamqp://guest:guest@localhost",
            help="RabbitMQ broker url",
        )
        parser.add_argument(
            "--backdoor-port",
            type=int,
            help="Specify a port number to host a backdoor, which can be"
            " connected to for an interactive interpreter within the running"
            " service process using `nameko backdoor`.",
        )

        return parser
