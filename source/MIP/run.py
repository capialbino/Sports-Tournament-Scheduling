#!/usr/bin/env python3
"""
Run script for Round Robin Tournament Scheduler

This script executes the round_robin_scheduler.py script with a timeout
and formats the output as a JSON file according to the competition format.

Usage:
    python run.py -n 12 -o results/MIP -t 300
"""

import argparse
import subprocess
import time as tm
from pathlib import Path
import re
import sys
import json


# Import the solver function directly
from model import *

def parse_solver_output(output, n):
    """
    Parse solver stdout and extract:
    - objective value (TOTAL IMBALANCE)
    - schedule matrix of shape (n-1) x (n/2)
      Each entry: [home_team, away_team] (1-indexed)
    """

    weeks = []
    current_week = None

    # Regex patterns
    week_pattern = re.compile(r"^Week\s+\d+:")
    match_pattern = re.compile(r"Team\s+(\d+)\s+vs\s+Team\s+(\d+)")
    imbalance_pattern = re.compile(r"TOTAL IMBALANCE:\s*(\d+)")

    for line in output.splitlines():
        line = line.strip()

        # Detect new week
        if week_pattern.match(line):
            if current_week is not None:
                weeks.append(current_week)
            current_week = []
            continue

        # Detect match line(s)
        matches = match_pattern.findall(line)
        for home, away in matches:
            # Convert to 1-based indexing
            home = int(home) + 1
            away = int(away) + 1
            current_week.append([home, away])

    # Append last week
    if current_week is not None:
        weeks.append(current_week)

    # Extract objective
    imbalance = None
    imbalance_match = imbalance_pattern.search(output)
    if imbalance_match:
        imbalance = int(imbalance_match.group(1))

    # Optional sanity check
    expected_weeks = n - 1
    expected_matches_per_week = n // 2

    if len(weeks) != expected_weeks:
        raise ValueError(f"Expected {expected_weeks} weeks, got {len(weeks)}")

    for w in weeks:
        if len(w) != expected_matches_per_week:
            raise ValueError(
                f"Each week must have {expected_matches_per_week} matches, got {len(w)}"
            )

    return imbalance, weeks


def run_scheduler(n, timeout=300):

    result = {
        "time": timeout,
        "optimal": False,
        "obj": None,
        "sol": []
    }

    start_time = tm.time()

    try:
        process = subprocess.run(
            [sys.executable, "source/MIP/model.py", str(n)],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        elapsed_time = int(tm.time() - start_time)

        if process.returncode != 0:
            print(f"Warning: Solver failed with return code {process.returncode}")
            if process.stderr:
                print("STDERR:", process.stderr[:500])
            return result  # time already = timeout, optimal=False

        # Print solver output so schedule is visible
        print(process.stdout)

        imbalance, schedule_matrix = parse_solver_output(process.stdout, n)

        if imbalance is None or not schedule_matrix:
            print("Failed to extract solution.")
            return result

        # Transpose to (n/2) x (n-1)
        schedule_matrix = list(map(list, zip(*schedule_matrix)))

        # Competition optimality rule
        is_optimal = imbalance and imbalance <= n

        if is_optimal:
            result["time"] = elapsed_time
        else:
            result["time"] = timeout  # required rule

        result["optimal"] = is_optimal
        result["obj"] = imbalance
        result["sol"] = schedule_matrix

        if not is_optimal:
            print(f"Warning: Objective {imbalance} > N={n}, setting optimal=False")

    except subprocess.TimeoutExpired:
        print(f"Timeout: Solver exceeded {timeout} seconds")
        result["time"] = timeout
        result["optimal"] = False

    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        result["time"] = timeout
        result["optimal"] = False

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