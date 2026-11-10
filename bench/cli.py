"""Command line entry point: run one scenario or print a report."""
import argparse
import sys

from . import report
from .runner import run


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bench", description="Детерминированный стенд сравнения стратегий")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", help="выполнить один сценарий")
    run_parser.add_argument("--scenario", required=True, help="путь к TOML-сценарию")
    run_parser.add_argument("--agent", required=True, help="frugal, greedy или sloppy")
    run_parser.add_argument("--results", default="results", help="каталог результатов")

    report_parser = commands.add_parser("report", help="свести результаты в таблицу")
    report_parser.add_argument("results", nargs="?", default="results")

    args = parser.parse_args(argv)
    if args.command == "run":
        try:
            record = run(args.scenario, args.agent, args.results)
        except (OSError, ValueError, KeyError) as error:
            print("Ошибка:", error, file=sys.stderr)
            return 2
        verdict = "пройдено" if record["passed"] else "не пройдено"
        print(f"{record['scenario']} / {record['agent']}: {verdict} ({record['output_chars']} символов)")
        return 0 if record["passed"] else 1

    records = report.load(args.results)
    if not records:
        print("Нет результатов в", args.results, file=sys.stderr)
        return 2
    print(report.render(report.summarise(records)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
