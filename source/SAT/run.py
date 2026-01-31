import subprocess
import json
import os
import time
import math
import argparse
import re
from pathlib import Path



def previous_unsolved(outdir, N, solver, mode):
    prev_n = N - 2
    prev_file = os.path.join(outdir, f"{prev_n}.json")

    if not os.path.exists(prev_file):
        return False

    with open(prev_file, "r") as f:
        data = json.load(f)

    key = f"{solver}-{mode}"

    if key not in data:
        return False

    return data[key]["sol"] == []


def run_model(script_path, mode, solver, N, timeout_sec=300):
    cmd = [
        "python",
        str(script_path),
        "-n", str(N),
        "--mode", mode,
        "--solver", solver
    ]

    start_time = time.time()

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec
        )

    except subprocess.TimeoutExpired:
        return timeout_sec, False, None, []

    runtime = math.floor(time.time() - start_time)
    stdout = result.stdout

    print(stdout)

    # Objective extraction
    obj = None
    obj_match = re.search(r"Total Imbalance:\s*(\d+)", stdout)
    if obj_match:
        obj = int(obj_match.group(1))

    # Solution extraction
    sol = parse_solution_matrix(stdout)

    optimal = True
    if not sol:
        optimal = False
        runtime = timeout_sec

    return runtime, optimal, obj, sol


def parse_solution_matrix(stdout):
    # Extract week blocks
    week_blocks = re.findall(
        r"Week\s+\d+:(.*?)(?=Week\s+\d+:|Home/Away Balance:|Total Imbalance:|----------|$)",
        stdout,
        re.DOTALL
    )

    if not week_blocks:
        return None

    weeks = []

    # Extract matches per period for each week
    for block in week_blocks:
        period_matches = re.findall(
            r"Period\s+\d+:\s*(\d+)\s+vs\s+(\d+)",
            block
        )

        week_matches = [[int(a), int(b)] for a, b in period_matches]

        if week_matches:
            weeks.append(week_matches)

    if not weeks:
        return None

    num_weeks = len(weeks)
    num_periods = len(weeks[0])

    # Ensure all weeks have same number of periods
    for w in weeks:
        if len(w) != num_periods:
            return None

    # Convert week-major to period-major structure
    matrix = []

    for p in range(num_periods):
        row = []
        for w in range(num_weeks):
            row.append(weeks[w][p])
        matrix.append(row)

    # Convert team numbering from 0-based to 1-based
    for p in range(num_periods):
        for w in range(num_weeks):
            for t in range(2):
                matrix[p][w][t] += 1

    return matrix


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--outdir", type=str, default="res")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["satisfy", "optimize", "both"],
        required=True
    )
    parser.add_argument(
        "--solver",
        type=str,
        choices=["z3", "ortools"],
        required=True
    )

    parser.add_argument(
        "--no-skip-non-solvable",
        dest="skip_non_solvable",
        action="store_false",
        help="Disable skipping if previous N-2 had no solution."
    )

    parser.set_defaults(skip_non_solvable=True)

    args = parser.parse_args()

    script_path = Path("source/SAT/solve.py")

    if not script_path.exists():
        print("Invalid script path")
        return

    if args.N % 2 != 0:
        print("N must be even")
        return

    os.makedirs(args.outdir, exist_ok=True)

    modes_to_run = ["satisfy", "optimize"] if args.mode == "both" else [args.mode]

    results = {}

    for mode in modes_to_run:
        key = f"{args.solver}-{mode}"

        # Skip logic here
        if args.skip_non_solvable and args.N > 6:
            if previous_unsolved(args.outdir, args.N, args.solver, mode):
                print(f"Skipping {key} at N={args.N} (unsolved at N={args.N-2})")
                results[key] = {
                    "time": args.timeout,
                    "optimal": False,
                    "obj": None,
                    "sol": []
                }
                continue

        print(f"Running {key}...")

        runtime, optimal, obj, sol = run_model(
            script_path,
            mode,
            args.solver,
            args.N,
            args.timeout
        )

        results[key] = {
            "time": runtime,
            "optimal": optimal,
            "obj": obj,
            "sol": sol if sol else []
        }

    output_path = os.path.join(args.outdir, f"{args.N}.json")

    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            existing = json.load(f)
    else:
        existing = {}

    existing.update(results)

    with open(output_path, "w") as f:
        json.dump(existing, f, indent=4)

    print(f"\nSaved results to {output_path}")


if __name__ == "__main__":
    main()
