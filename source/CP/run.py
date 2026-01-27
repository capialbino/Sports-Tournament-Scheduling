import subprocess
import json
import os
import time
import math
import argparse
import re
from pathlib import Path


ALLOWED_SOLVERS = ["gecode", "chuffed", "cp-sat"]


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

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    end_time = time.time()
    actual_runtime = end_time - start_time
    runtime_floor = math.floor(actual_runtime)

    stdout = result.stdout

    # ---------------------------
    # Objective extraction
    # ---------------------------
    obj = None
    obj_match = re.search(r"Total Imbalance:\s*(\d+)", stdout)
    if obj_match:
        obj = int(obj_match.group(1))

    # ---------------------------
    # Solution extraction
    # ---------------------------
    sol = parse_solution_matrix(stdout)

    # ---------------------------
    # Optimality detection
    # ---------------------------
    optimal = True
    if not sol or (obj and obj > N):
        optimal = False
        runtime_floor = timeout_sec  # required by spec

    return runtime_floor, optimal, obj, sol


def parse_solution_matrix(stdout):
    """
    Parses output formatted as:

    Week i:
      Period 1  Period 2 ...
        X vs Y   A vs B ...

    Returns matrix of size (n/2) x (n-1) where:
    - Rows represent periods
    - Columns represent weeks
    - Each entry is [home_team, away_team]
    """

    # Extract all weeks
    week_blocks = re.findall(
        r"Week\s+\d+:(.*?)(?=Week\s+\d+:|Home/Away Balance:|----------)",
        stdout,
        re.DOTALL
    )

    if not week_blocks:
        return None

    weeks = []

    for block in week_blocks:
        # Extract all matches "X vs Y" in order
        matches = re.findall(r"(\d+)\s+vs\s+(\d+)", block)
        week_matches = [[int(a), int(b)] for a, b in matches]
        if week_matches:
            weeks.append(week_matches)

    if not weeks:
        return None

    # Convert from week-major to period-major matrix
    # Current structure: weeks[week_index][period_index] = [home, away]
    # Desired structure: matrix[period_index][week_index] = [home, away]

    num_weeks = len(weeks)
    num_periods = len(weeks[0]) if weeks else 0

    if num_periods == 0:
        return None

    matrix = []

    for p in range(num_periods):
        row = []
        for w in range(num_weeks):
            if p < len(weeks[w]):
                row.append(weeks[w][p])
            else:
                # Handle potential inconsistency
                return None
        matrix.append(row)

    # add one to all number
    for p in range(num_periods):
        for w in range(num_weeks):
            for t in range(2):
                matrix[p][w][t] += 1

    return matrix



# --------------------------------------------------------
# MAIN
# --------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run all .mzn models in a directory with all solvers and produce ONE grouped JSON."
    )

    parser.add_argument("--dir", type=str, required=True,
                        help="Directory containing .mzn files")

    parser.add_argument("--N", type=int, required=True,
                        help="Instance size parameter")

    parser.add_argument("--timeout", type=int, default=300,
                        help="Timeout in seconds (default 300)")

    parser.add_argument("--outdir", type=str, default="res",
                        help="Directory where JSON file will be saved (default: res)")

    args = parser.parse_args()

    model_dir = Path(args.dir)

    if not model_dir.exists() or not model_dir.is_dir():
        print("Invalid directory")
        return

    mzn_files = list(model_dir.glob("*.mzn"))

    if not mzn_files:
        print("No .mzn files found")
        return

    results = {}

    for mzn_file in mzn_files:
        file_name = mzn_file.stem

        for solver in ALLOWED_SOLVERS:
            approach_name = f"{file_name}-{solver}"
            print(f"Running {approach_name}...")

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

    # Create output directory
    os.makedirs(args.outdir, exist_ok=True)

    output_path = os.path.join(args.outdir, f"{args.N}.json")

    with open(output_path, "w") as f:
        json.dump(results, f, indent=4)

    print(f"\nSaved grouped results to {output_path}")


if __name__ == "__main__":
    main()
