from itertools import combinations

from z3 import *

try:
    from ortools.sat.python import cp_model

    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False


# ============================================================================
# Helper functions to detect backend type
# ============================================================================

def is_ortools_var(var):
    """Check if a variable is from OR-Tools."""
    return ORTOOLS_AVAILABLE and hasattr(var, '__module__') and 'ortools' in str(type(var))


def is_ortools_backend(solver):
    """Check if solver is OR-Tools backend."""
    return hasattr(solver, 'model') and ORTOOLS_AVAILABLE


# ============================================================================
# Unified encoding functions
# ============================================================================

def at_least_one(bool_vars, solver=None):
    """At least one variable must be true."""
    if not bool_vars:
        return True

    if is_ortools_var(bool_vars[0]):
        # OR-Tools
        solver.model.AddBoolOr(bool_vars)
        return True
    else:
        # Z3
        return Or(bool_vars)


def at_most_one(bool_vars, solver=None, name=""):
    """At most one variable can be true."""
    if len(bool_vars) <= 1:
        return True

    if is_ortools_var(bool_vars[0]):
        # OR-Tools has native support
        solver.model.AddAtMostOne(bool_vars)
        return True
    else:
        # Z3 - use pairwise encoding
        return And([Not(And(pair[0], pair[1])) for pair in combinations(bool_vars, 2)])


def exactly_one(bool_vars, solver=None, name=""):
    if not bool_vars:
        return False

    if is_ortools_var(bool_vars[0]):
        solver.model.AddExactlyOne(bool_vars)
    else:
        solver.add_constraint(
            And(at_least_one(bool_vars),
                at_most_one(bool_vars, solver, name))
        )

def at_most_k(bool_vars, k, solver=None, name=""):
    """At most k variables can be true."""
    if len(bool_vars) <= k:
        return True

    if is_ortools_var(bool_vars[0]):
        # OR-Tools - use linear constraint
        solver.model.Add(sum(bool_vars) <= k)
        return True
    else:
        # Z3 - use sequential encoding
        solver.add_constraint(at_most_k_seq_z3(bool_vars, k, name))


def at_most_k_seq_z3(bool_vars, k, name):
    """Sequential counter encoding for at-most-k constraint."""
    n = len(bool_vars)
    if n <= k:
        return True
    if k == 0:
        return And([Not(v) for v in bool_vars])

    s = [[Bool(f"s_{name}_{i}_{j}") for j in range(k)] for i in range(n - 1)]

    return And(
        Implies(bool_vars[0], s[0][0]),
        Implies(s[n - 2][k - 1], Not(bool_vars[n - 1])),
        And(*[Not(s[0][j]) for j in range(1, k)]),
        And(
            *[
                And(
                    Implies(Or(bool_vars[i], s[i - 1][0]), s[i][0]),
                    And(
                        *[
                            Implies(
                                Or(And(bool_vars[i], s[i - 1][j - 1]), s[i - 1][j]),
                                s[i][j],
                            )
                            for j in range(1, k)
                        ]
                    ),
                    Implies(s[i - 1][k - 1], Not(bool_vars[i])),
                )
                for i in range(1, n - 1)
            ]
        ),
    )


def encode_integer_onehot(solver, name, max_val):
    """Create one-hot encoded integer variables."""
    if is_ortools_backend(solver):
        # OR-Tools
        vars = [solver.model.NewBoolVar(f'{name}_val_{i}') for i in range(max_val + 1)]
    else:
        # Z3
        vars = [Bool(f'{name}_val_{i}') for i in range(max_val + 1)]
    return vars


def encode_exact_count(solver, indicators, count_vars, max_count, name):
    """Encode that exactly count_vars[k] is true iff exactly k indicators are true."""

    if is_ortools_backend(solver):
        # OR-Tools version
        for k in range(max_count + 1):
            if k > len(indicators):
                solver.model.Add(count_vars[k] == 0)
            else:
                solver.model.Add(sum(indicators) == k).OnlyEnforceIf(count_vars[k])
                solver.model.Add(sum(indicators) != k).OnlyEnforceIf(count_vars[k].Not())
    else:
        # Z3 version
        for k in range(max_count + 1):
            if k > len(indicators):
                solver.add_constraint(Not(count_vars[k]))
            elif k == 0:
                solver.add_constraint(Implies(count_vars[0], And([Not(ind) for ind in indicators])))
                if len(indicators) > 0:
                    solver.add_constraint(Implies(And([Not(ind) for ind in indicators]), count_vars[0]))
            elif k == len(indicators):
                solver.add_constraint(Implies(count_vars[k], And(indicators)))
                solver.add_constraint(Implies(And(indicators), count_vars[k]))
            else:
                at_least_k = at_most_k_seq_z3([Not(ind) for ind in indicators],
                                              len(indicators) - k, f'{name}_atleast_{k}')
                at_most_k_cond = at_most_k_seq_z3(indicators, k, f'{name}_atmost_{k}')

                solver.add_constraint(Implies(count_vars[k], And(at_least_k, at_most_k_cond)))
                solver.add_constraint(Implies(And(at_least_k, at_most_k_cond), count_vars[k]))


def constrain_total_imbalance(solver, diff_vars, T, N, target):
    """Add constraint that sum of all team differences equals target."""

    if is_ortools_backend(solver):
        # OR-Tools version - use integer variables
        team_diffs = []
        for t in T:
            diff_val = solver.model.NewIntVar(0, N - 1, f'team_{t}_diff_val')
            for k in range(N):
                solver.model.Add(diff_val == k).OnlyEnforceIf(diff_vars[t][k])
            team_diffs.append(diff_val)
        solver.model.Add(sum(team_diffs) == target)
    else:
        # Z3 version - enumerate valid combinations
        def find_combinations(teams_left, current_sum, current_assignment):
            if teams_left == 0:
                if current_sum == target:
                    yield current_assignment
                return
            for diff in range(min(N, target - current_sum + 1)):
                yield from find_combinations(teams_left - 1, current_sum + diff,
                                             current_assignment + [diff])

        valid_combinations = list(find_combinations(N, 0, []))

        if not valid_combinations:
            solver.add_constraint(False)
            return

        combination_constraints = []
        for combo in valid_combinations:
            combo_constraint = And([diff_vars[t][combo[t]] for t in T])
            combination_constraints.append(combo_constraint)

        solver.add_constraint(Or(combination_constraints))
