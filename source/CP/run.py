import subprocess
import json
import os
import time
import math
import argparse
import re
from pathlib import Path

ALLOWED_SOLVERS = ["gecode", "chuffed", "cp-sat"]

def previous_unsolved(outdir, N, approach_name):
    prev_n = N - 2
    prev_file = os.path.join(outdir, f"{prev_n}.json")

    if not os.path.exists(prev_file):
        return False

    with open(prev_file, "r") as f:
        data = json.load(f)

    if approach_name not in data:
        return False

    return data[approach_name]["sol"] == []

def run_minizinc_model(mzn_file, solver, N, timeout_sec=300):
    cmd = [
        "minizinc",
        "--solver", solver,
        "--output-mode", "item",
        "--time-limit", str(timeout_sec * 1000),
        "-D", f"N={N}",
        str(mzn_file)
    ]

    start_time = time.time()

    # Execute MiniZinc process and capture output
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    end_time = time.time()

    # Measure actual runtime
    actual_runtime = end_time - start_time
    runtime_floor = math.floor(actual_runtime)

    stdout = result.stdout
    print(stdout)

    # Objective extraction
    obj = None
    obj_match = re.search(r"Total Imbalance:\s*(\d+)", stdout)
    if obj_match:
        obj = int(obj_match.group(1))

    # Solution extraction
    sol = parse_solution_matrix(stdout)

    # Optimality detection
    optimal = True
    if not sol or (obj and obj > N):
        optimal = False
        runtime_floor = timeout_sec

    return runtime_floor, optimal, obj, sol


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
    parser = argparse.ArgumentParser(
        description="Run MiniZinc models and produce grouped JSON results."
    )

    parser.add_argument("--dir", type=str,
                        help="Directory containing .mzn files")

    parser.add_argument("--model", type=str,
                        help="Single MiniZinc model file to run")

    parser.add_argument("--solver", type=str,
                        choices=ALLOWED_SOLVERS,
                        help="Specific solver to use (required if --model is used)")

    parser.add_argument("--N", type=int, required=True,
                        help="Instance size parameter")

    parser.add_argument("--timeout", type=int, default=300,
                        help="Timeout in seconds (default 300)")

    parser.add_argument("--outdir", type=str, default="res",
                        help="Directory where JSON file will be saved")

    parser.add_argument(
        "--no-skip-non-solvable",
        dest="skip_non_solvable",
        action="store_false",
        help="Disable skipping of model-solver pairs that had no solution at N-2."
    )

    parser.set_defaults(skip_non_solvable=True)

    args = parser.parse_args()

    # Validate execution mode
    if args.model:
        # Single model mode
        model_path = Path(args.model)

        if not model_path.exists() or not model_path.is_file():
            print("Invalid model file")
            return

        if not args.solver:
            print("--solver must be specified when using --model")
            return

        mzn_files = [model_path]
        solvers_to_use = [args.solver]

    elif args.dir:
        # Directory mode
        model_dir = Path(args.dir)

        if not model_dir.exists() or not model_dir.is_dir():
            print("Invalid directory")
            return

        mzn_files = list(model_dir.glob("*.mzn"))

        if not mzn_files:
            print("No .mzn files found")
            return

        solvers_to_use = ALLOWED_SOLVERS

    else:
        print("You must specify either --dir or --model")
        return

    results = {}

    # Run each model
    for mzn_file in mzn_files:
        file_name = mzn_file.stem

        for solver in solvers_to_use:

            approach_name = f"{file_name}-{solver}"
            print(f"Processing {approach_name} for N={args.N}...")

            # Skip logic
            if args.skip_non_solvable and args.N > 6:
                if previous_unsolved(args.outdir, args.N, approach_name):
                    print(f"Skipping {approach_name} at N={args.N} (unsolved at N={args.N - 2})")
                    results[approach_name] = {
                        "time": args.timeout,
                        "optimal": False,
                        "obj": None,
                        "sol": []
                    }
                    continue

            # Otherwise run normally
            runtime, optimal, obj, sol = run_minizinc_model(
                mzn_file=mzn_file,
                solver=solver,
                N=args.N,
                timeout_sec=args.timeout
            )

            results[approach_name] = {
                "time": runtime,
                "optimal": optimal,
                "obj": obj,
                "sol": sol if sol else []
            }

    # Save grouped results to JSON
    os.makedirs(args.outdir, exist_ok=True)
    output_path = os.path.join(args.outdir, f"{args.N}.json")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

    print(f"\nSaved grouped results to {output_path}")


if __name__ == "__main__":
    main()
