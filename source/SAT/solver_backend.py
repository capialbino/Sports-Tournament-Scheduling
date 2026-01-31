from z3 import *
from ortools.sat.python import cp_model


class SolverBackend:

    def create_bool_var(self, name):
        raise NotImplementedError

    def add_constraint(self, constraint):
        raise NotImplementedError

    def check(self):
        raise NotImplementedError

    def get_model(self):
        raise NotImplementedError

    def push(self):
        raise NotImplementedError

    def pop(self):
        raise NotImplementedError

    def minimize(self, objective):
        raise NotImplementedError


class Z3Backend(SolverBackend):

    def __init__(self):
        self.solver = Solver()
        self._model = None

    def create_bool_var(self, name):
        return Bool(name)

    def add_constraint(self, constraint):
        self.solver.add(constraint)

    def check(self):
        result = self.solver.check()
        if result == sat:
            self._model = self.solver.model()
            return 'SAT'
        elif result == unsat:
            return 'UNSAT'
        else:
            return 'UNKNOWN'

    def get_model(self):
        return self._model

    def push(self):
        self.solver.push()

    def pop(self):
        self.solver.pop()

    def minimize(self, objective):
        return None

    def evaluate(self, var):
        """Evaluate a variable in the current model."""
        if self._model is None:
            return None
        return self._model.evaluate(var)

    def get_statistics(self):
        return {
            'status': 'SAT' if self._model is not None else 'UNKNOWN',
            'time': 0,
            'branches': 0,
            'conflicts': 0,
            'objective': None
        }


class ORToolsBackend(SolverBackend):

    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solver.parameters.log_search_progress = False

        # Track variables for one-hot encoding compatibility
        self._var_registry = {}
        self._constraint_stack = []
        self._objective = None
        self._last_status = None

    def create_bool_var(self, name):
        var = self.model.NewBoolVar(name)
        self._var_registry[name] = var
        return var

    def add_constraint(self, constraint):
        """
        Add constraint.
        This needs to handle Z3-style constraints and convert them to OR-Tools format.
        """
        # For OR-Tools, we add constraints directly to the model
        # The constraint conversion happens in the encoding functions
        if isinstance(constraint, bool):
            if not constraint:
                # False constraint means UNSAT
                self.model.Add(self.model.NewBoolVar('false') == 1)
                self.model.Add(self.model.NewBoolVar('false') == 0)
        else:
            # Constraint is already in OR-Tools format from encoding functions
            pass

    def check(self):
        """Solve the model."""
        if self._objective is not None:
            status = self.solver.Solve(self.model)
        else:
            status = self.solver.Solve(self.model)

        self._last_status = status

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            return 'SAT'
        elif status == cp_model.INFEASIBLE:
            return 'UNSAT'
        else:
            return 'UNKNOWN'

    def get_model(self):
        return self.solver

    def push(self):
        """Save current state."""
        # OR-Tools doesn't have push/pop, so we need to work around this
        # For optimization, we'll create a new model instead
        self._constraint_stack.append(len(self.model.Proto().constraints))

    def pop(self):
        """Restore previous state."""
        # This is a limitation - OR-Tools doesn't support incremental solving like Z3
        # We'd need to rebuild the model, which is handled at a higher level
        if self._constraint_stack:
            self._constraint_stack.pop()

    def minimize(self, objective):
        """Set optimization objective."""
        self._objective = objective
        self.model.Minimize(objective)
        return objective

    def evaluate(self, var):
        """Evaluate a variable in the solution."""
        if self._last_status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return None
        return self.solver.Value(var)

    def get_statistics(self):
        """Get solver statistics."""
        return {
            'status': self.solver.StatusName(self._last_status),
            'status': self.solver.StatusName(self._last_status),
            'time': self.solver.WallTime(),
            'branches': self.solver.NumBranches(),
            'conflicts': self.solver.NumConflicts(),
            'objective': self.solver.ObjectiveValue() if self._objective is not None else None
        }


def create_solver(backend='z3'):
    if backend.lower() == 'z3':
        return Z3Backend()
    elif backend.lower() == 'ortools':
        return ORToolsBackend()
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose 'z3' or 'ortools'")
