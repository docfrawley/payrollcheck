"""Work one case with the PayrollCheck Agent: uv run -m agent PC-1201"""

import argparse
import sys

from dotenv import load_dotenv

from agent import api
from agent.checkpoints import checkpoint_pool
from agent.connection import Refused
from agent.console import show_reports
from agent.harness import payroll_graphs, work_case


def main(args: list[str]) -> None:
    """Work the case named on the command line on the current version, with no
    run."""
    parser = argparse.ArgumentParser(
        prog="uv run -m agent", description="Work one case in the queue."
    )
    parser.add_argument("case_id", help="the case to work")
    options = parser.parse_args(args)
    with checkpoint_pool() as pool:
        try:
            agent = payroll_graphs(api.get_current_version(), pool)()
            work_case(options.case_id, None, agent)
        except (Refused, ConnectionError) as refusal:
            parser.exit(1, f"{options.case_id}  not started: {refusal}\n")


if __name__ == "__main__":
    load_dotenv(override=True)
    show_reports()
    main(sys.argv[1:])
