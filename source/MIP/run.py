#!/usr/bin/env python3
"""
Run script for Round Robin Tournament Scheduler

This script executes the round_robin_scheduler.py script with a timeout
and formats the output as a JSON file according to the competition format.

Usage:
    python run.py -n 12 -o results/MIP -t 300
"""

import argparse
import time as tm
from pathlib import Path

from pulp import *

# Import the solver function directly
from model import *


def run_scheduler(n, timeout=300):
    """
    Run the round-robin solver directly and return result in required format.
    """
    result = {
        "time": timeout,
        "optimal": False,
        "obj": None,
        "sol": []
    }

    start_time = tm.time()

    try:
        prob, matches_idx, home_is_first, match_pairs, Cha, imbalance, teams, weeks, periods = create_schedule(n)
        print_schedule(prob, matches_idx, home_is_first,
                       match_pairs, Cha, imbalance,
                       teams, weeks, periods)

        elapsed_time = int(tm.time() - start_time)  # floor runtime
        status = LpStatus[prob.status]

        # If no feasible solution
        if status not in ["Optimal", "Not Solved"]:
            result["time"] = timeout
            return result

        obj_value = int(value(imbalance)) if value(imbalance) is not None else None

        # Build solution matrix (periods x weeks)
        schedule_matrix = []
        for p in periods:
            period_row = []
            for w in weeks:
                match_id = int(value(matches_idx[p][w]))
                is_first_home = int(value(home_is_first[p][w]))

                if is_first_home == 1:
                    home = match_pairs[match_id][0] + 1
                    away = match_pairs[match_id][1] + 1
                else:
                    home = match_pairs[match_id][1] + 1
                    away = match_pairs[match_id][0] + 1

                period_row.append([home, away])
            schedule_matrix.append(period_row)

        # Determine optimality
        is_optimal = (
            status == "Optimal"
            and obj_value is not None
            and obj_value == n
        )

        # Apply competition rule:
        # time = 300  ⇔  optimal = False
        if not is_optimal:
            result["time"] = timeout
        else:
            result["time"] = elapsed_time

        result["optimal"] = is_optimal
        result["obj"] = obj_value
        result["sol"] = schedule_matrix if obj_value is not None else []

    except Exception as e:
        print("Error running solver:", e)
        result["time"] = timeout
        result["optimal"] = False
        result["obj"] = None
        result["sol"] = []

    return result



def main():
    """Main function to parse arguments and run the scheduler."""
    parser = argparse.ArgumentParser(
        description='Run the round-robin scheduler and output results in JSON format.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -n 12 -o results/MIP -t 300
  %(prog)s -n 8 -o results/MIP -t 60
  %(prog)s --teams 10 --outdir results/CP --timeout 300

The output JSON file will be created at: <outdir>/<n>.json
        """
    )

    parser.add_argument(
        '-n', '--teams',
        type=int,
        required=True,
        metavar='N',
        help='Number of teams (must be even, minimum 4)'
    )

    parser.add_argument(
        '-o', '--outdir',
        type=str,
        required=True,
        metavar='DIR',
        help='Output directory for results (e.g., results/MIP)'
    )

    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=300,
        metavar='SECONDS',
        help='Timeout in seconds (default: 300)'
    )

    args = parser.parse_args()

    # Validate input
    if args.teams < 4:
        print(f"Error: Number of teams must be at least 4 (got {args.teams})")
        sys.exit(1)
    if args.teams % 2 != 0:
        print(f"Error: Number of teams must be even (got {args.teams})")
        sys.exit(1)
    if args.timeout <= 0:
        print(f"Error: Timeout must be positive (got {args.timeout})")
        sys.exit(1)

    # Create output directory if it doesn't exist
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Output file path
    output_file = outdir / f"{args.teams}.json"

    print(f"\nRunning scheduler for {args.teams} teams...")
    print(f"Timeout: {args.timeout} seconds")
    print(f"Output will be saved to: {output_file}\n")

    # Run the scheduler
    result = run_scheduler(args.teams, args.timeout)

    # Create the final JSON structure
    # The approach name is derived from the output directory name
    approach_name = "MIP-CBC_MILP"
    json_output = {
        approach_name: result
    }

    # Write to JSON file
    with open(output_file, 'w') as f:
        json.dump(json_output, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Teams: {args.teams}")
    print(f"Time: {result['time']} seconds")
    print(f"Optimal: {result['optimal']}")
    print(f"Objective (Total Imbalance): {result['obj']}")
    print(f"Solution: {'Found' if result['sol'] is not None else 'Not found'}")
    print(f"\nResults saved to: {output_file}")
    print("=" * 80 + "\n")

    # Return appropriate exit code
    sys.exit(0 if result['optimal'] else 1)


if __name__ == "__main__":
    main()