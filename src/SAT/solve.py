from z3 import *

from utils import *
from sat_encodings import *

def solve_sports_scheduling(N):
    """Solve the sports scheduling problem for N teams using pure boolean SAT."""
    assert N % 2 == 0, "Number of teams must be even"

    # Parameters
    T = range(N)  # Teams
    S = range(2)  # Slots (0=Home, 1=Away)
    W = range(N - 1)  # Weeks
    P = range(N // 2)  # Periods per week
    M = range((N - 1) * (N // 2))  # Total matches

    rb, matches = generate_rb_and_flattened(N, W, P, S)

    # Create solver
    solver = Solver()

    # Decision variables: matches_idx[p][w] using one-hot encoding
    # matches_idx_vars[p][w][m] is true iff period p in week w has match m
    matches_idx_vars = {}
    for p in P:
        for w in W:
            vars = encode_integer_onehot(f'midx_{p}_{w}', len(M) - 1)
            matches_idx_vars[p, w] = vars

    # Each position has exactly one match assigned (one-hot constraint)
    for p in P:
        for w in W:
            # Use Heule encoding for exactly-one (most efficient for this)
            solver.add(exactly_one_he(matches_idx_vars[p, w], f'eo_midx_{p}_{w}'))

    # CONSTRAINT 1: matches_idx[0, 0] = 0
    solver.add(matches_idx_vars[0, 0][0])

    # CONSTRAINT 2: All different (each match ID used exactly once across all positions)
    for m in M:
        # Collect all positions that could have match m
        indicators = []
        for p in P:
            for w in W:
                indicators.append(matches_idx_vars[p, w][m])

        # Exactly one position has this match
        # Use Heule encoding for exactly-one
        solver.add(exactly_one_he(indicators, f'alldiff_m_{m}'))

    # CONSTRAINT 3: Range constraint - week w uses matches [w*(N/2), (w+1)*(N/2))
    for w in W:
        for p in P:
            low = w * (N // 2)
            high = (w + 1) * (N // 2)
            # Only matches in [low, high) can be true
            for m in M:
                if not (low <= m < high):
                    solver.add(Not(matches_idx_vars[p, w][m]))

    # CONSTRAINT 4: Each team plays at most twice in any period
    for period in P:
        for team in T:
            # Collect indicators: team appears in matches_idx[period, w]
            team_appears = []

            for w in W:
                # For this week, check which matches are valid (due to range constraint)
                low = w * (N // 2)
                high = (w + 1) * (N // 2)

                for m in range(low, high):
                    # Does match m contain this team?
                    match_has_team = (matches[m, 0] == team or matches[m, 1] == team)

                    if match_has_team:
                        # If matches_idx[period, w] = m, then team appears
                        team_appears.append(matches_idx_vars[period, w][m])

            # At most 2 of these can be true
            # Use sequential encoding for at-most-k (efficient for small k)
            if len(team_appears) > 2:
                solver.add(at_most_k_seq(team_appears, 2, f'amt2_t{team}_p{period}'))
            elif len(team_appears) == 2:
                # Just use pairwise
                solver.add(at_most_one_np(team_appears))

    # Solve
    result = solver.check()

    if result == sat:
        model = solver.model()

        # Extract solution
        solution = {}
        for p in P:
            for w in W:
                for m in M:
                    if is_true(model.evaluate(matches_idx_vars[p, w][m])):
                        solution[p, w] = m
                        break

        # Print solution
        print_solution(N, W, P, matches, solution)

        return solution
    else:
        print("No solution found (UNSAT)")
        return None
