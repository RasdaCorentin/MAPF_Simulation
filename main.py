#!/usr/bin/env python3
"""
main.py — entry point for a MAPF scenario.

    python main.py                                     # 15x15, 20 agents, PIBT + MRTA, window
    python main.py --tasks random                      # same, with self-generated work
    python main.py --frontend headless --tasks random --steps 20
    python main.py --algo random --mode static         # the historical random-walk demo
    python main.py --agents 40 --width 25 --height 25 --obstacles 20

In the window: select agents (click, or drag a rubber band), then click
a cell to send the batch there. Space plays/pauses, arrows step and
replay, A/C select all or clear, Q quits.

Everything below is argument parsing: building the scenario is
client.control.build()'s job, and driving it is the frontend's.
"""

import argparse

from client.control import ScenarioConfig, build
from report import CsvSink, NullSink, RunCollector


def parse_args() -> argparse.Namespace:
    """Input: none (reads sys.argv).
    Output: the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Run a MAPF scenario.")
    parser.add_argument("--width",     type=int, default=15)
    parser.add_argument("--height",    type=int, default=15)
    parser.add_argument("--agents",    type=int, default=20)
    parser.add_argument("--obstacles", type=int, default=0)
    parser.add_argument("--algo",      choices=("pibt", "random"), default="pibt",
                        help="navigation algorithm (default: pibt)")
    parser.add_argument("--mode",      choices=("mrta", "static"), default="mrta",
                        help="mrta = task allocation, static = fixed goals")
    parser.add_argument("--tasks",     choices=("none", "random"), default="none",
                        help="background task generation on top of the "
                             "interactive queue (default: none)")
    parser.add_argument("--frontend",  choices=("pygame", "headless"), default="pygame")
    parser.add_argument("--steps",     type=int, default=0,
                        help="step budget; 0 means run until quit (pygame only)")
    parser.add_argument("--seed",      type=int, default=0)
    parser.add_argument("--tick-ms",   type=int, default=350,
                        help="wall-clock duration of one step, pygame only")
    parser.add_argument("--results",   type=str, default="experiments.csv",
                        help="CSV appended with one row per run (default: experiments.csv)")
    parser.add_argument("--no-results", action="store_true",
                        help="run without logging the experiment")
    parser.add_argument("--label",     type=str, default="",
                        help="free-text tag stored with this run")
    return parser.parse_args()


def main() -> None:
    """Input: none. Output: None. Builds the scenario and runs it."""
    args = parse_args()

    config = ScenarioConfig(
        width=args.width,
        height=args.height,
        agents=args.agents,
        obstacles=args.obstacles,
        algo=args.algo,
        mode=args.mode,
        tasks=args.tasks,
        seed=args.seed,
    )

    # The collector decorates the controller, so the frontends drive it
    # unchanged and never learn they are being measured.
    collector = RunCollector(build(config), config, label=args.label)
    sink = NullSink() if args.no_results else CsvSink(args.results)

    try:
        if args.frontend == "headless":
            from client.frontends import HeadlessFrontend
            HeadlessFrontend(collector).run(args.steps or 20)
        else:
            from client.frontends import PygameFrontend
            PygameFrontend(collector, tick_ms=args.tick_ms).run(args.steps)
    finally:
        # Logged even on Ctrl-C or a closed window: a run that was interrupted
        # is still an observation, and losing it is how a session's worth of
        # experiments quietly goes missing.
        record = collector.record()
        try:
            sink.append(record)
            if not args.no_results:
                print(f"\nrun {record.run_id} ({record.steps} steps) -> {args.results}")
        except Exception as exc:
            # Never let a logging failure replace the reason the run ended —
            # if the run itself raised, that traceback is the useful one.
            print(f"\ncould not log run {record.run_id}: {exc}")


if __name__ == "__main__":
    main()
