def generate_rb_and_flattened(N, W, P, S):
    """
    Generate Round Robin schedule using Circle Method.
    Return W,P,S matrix and flattened W*P, S array
    """
    rb = {}
    for p in P:
        for w in W:
            for s in S:
                if s == 0:  # Home team
                    if p == 0:
                        rb[(p, w, s)] = N - 1 if w % 2 == 0 else w
                    else:
                        rb[(p, w, s)] = (p + w) % (N - 1)
                else:  # Away team
                    if p == 0:
                        rb[(p, w, s)] = w if w % 2 == 0 else N - 1
                    else:
                        rb[(p, w, s)] = (N - p + w - 1) % (N - 1)

    # Flatten to matches array
    matches = {}
    for w in W:
        for p in P:
            for s in S:
                m = w * (N // 2) + p
                matches[m, s] = rb[p, w, s]

    return rb, matches


def print_solution(N, W, P, matches, solution):
    """Print the round robin schedule in a formatted table."""
    # Print solution
    print("\n" + "=" * 60)
    print(f"SOLUTION FOUND for N={N} teams")
    print("=" * 60)

    for w in W:
        print(f"\nWeek {w + 1}:\n")
        print("  ", end="")
        for p in P:
            print(f"Period {p + 1}\t", end="")
        print("\n    ", end="")
        for p in P:
            m = solution[p, w]
            home = matches[m, 0]
            away = matches[m, 1]
            print(f"{home} vs {away}\t", end="")
        print("\n")
