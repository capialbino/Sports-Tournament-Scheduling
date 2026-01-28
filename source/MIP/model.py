from pulp import *


def optimize(n):
    # Validate input
    if n % 2 != 0:
        raise ValueError("Number of teams must be even")
    if n < 6:
        raise ValueError("Number of teams must be at least 6")

    teams = range(n)  # T = 0..N-1
    weeks = range(n - 1)  # W = 0..N-2
    periods = range(n // 2)  # P = 0..N div 2 - 1
    slots = range(2)  # S = 0..1 (0=Home, 1=Away)
    total_matches = range((n - 1) * (n // 2))  # M = 0..(N-1)*(N div 2)-1

    # Generate Round Robin schedule using circle method
    # rb[p][w][s] gives the team for period p, week w, slot s
    rb = {}
    for p in periods:
        rb[p] = {}
        for w in weeks:
            rb[p][w] = {}
            for s in slots:
                if s == 0:  # Home team
                    if p == 0:
                        rb[p][w][s] = n - 1 if w % 2 == 0 else w
                    else:
                        rb[p][w][s] = (p + w) % (n - 1)
                else:  # Away team
                    if p == 0:
                        rb[p][w][s] = w if w % 2 == 0 else n - 1
                    else:
                        rb[p][w][s] = (n - p + w - 1) % (n - 1)

    # Flatten to list of matches: matches[m][0/1]
    matches = {}
    match_id = 0
    for w in weeks:
        for p in periods:
            matches[match_id] = {}
            matches[match_id][0] = rb[p][w][0]
            matches[match_id][1] = rb[p][w][1]
            match_id += 1

    # Create the optimization problem
    prob = LpProblem("Single_Round_Robin_Scheduler_Optimization", LpMinimize)

    # Decision Variables
    # matches_idx[p][w] = the match ID assigned to period p in week w
    matches_idx = LpVariable.dicts(
        "MatchIdx",
        indices=(periods, weeks),
        lowBound=0,
        upBound=len(total_matches) - 1,
        cat="Integer"
    )

    # which_is_home[p][w] = 0 if first team in pair is home, 1 if second team is home
    which_is_home = LpVariable.dicts(
        "WhichIsHome",
        indices=(periods, weeks),
        cat="Binary"
    )

    # Cha[t][s] = count of how many times team t plays in slot s (0=home, 1=away)
    Cha = LpVariable.dicts(
        "SlotCount",
        indices=(teams, slots),
        lowBound=0,
        upBound=n - 1,
        cat="Integer"
    )

    # Objective variable: total imbalance
    imbalance = LpVariable("Imbalance", lowBound=n, cat="Integer")

    # Auxiliary variables for linking matches to teams and home/away
    # is_match[p][w][m] = 1 if matches_idx[p][w] == m (one-hot encoding of match m in period p and week w)
    is_match = LpVariable.dicts(
        "IsMatch",
        indices=(periods, weeks, total_matches),
        cat="Binary"
    )

    # team_in_period[t][p][w] = 1 if team t plays in period p in week w
    team_in_period = LpVariable.dicts(
        "TeamInPeriod",
        indices=(teams, periods, weeks),
        cat="Binary"
    )

    # team_plays_home[t][p][w] = 1 if team t plays at home in period p, week w
    team_plays_home = LpVariable.dicts(
        "TeamPlaysHome",
        indices=(teams, periods, weeks),
        cat="Binary"
    )

    # team_plays_away[t][p][w] = 1 if team t plays away in period p, week w
    team_plays_away = LpVariable.dicts(
        "TeamPlaysAway",
        indices=(teams, periods, weeks),
        cat="Binary"
    )

    # Auxiliary variables for products: is_match[p][w][m] * (1 - which_is_home[p][w])
    match_and_home_first = LpVariable.dicts(
        "MatchAndHomeFirst",
        indices=(periods, weeks, total_matches),
        cat="Binary"
    )

    # Auxiliary variables for products: is_match[p][w][m] * which_is_home[p][w]
    match_and_home_second = LpVariable.dicts(
        "MatchAndHomeSecond",
        indices=(periods, weeks, total_matches),
        cat="Binary"
    )

    # Constraints

    # 1. SYMMETRY BREAKING: matches_idx[0][0] = 0
    prob += matches_idx[0][0] == 0

    # 2. CHANNELING CONSTRAINT: Link is_match to matches_idx
    for p in periods:
        for w in weeks:
            # Exactly one match is selected
            prob += lpSum([is_match[p][w][m] for m in total_matches]) == 1

            # Link to the integer value
            prob += matches_idx[p][w] == lpSum([m * is_match[p][w][m] for m in total_matches])

    # 3. Validity: each match appears exactly once (alldifferent)
    for m in total_matches:
        prob += lpSum([is_match[p][w][m] for p in periods for w in weeks]) == 1

    # 4. Intuition: every p (N / 2) matches generated from round robin method, a week is formed
    for w in weeks:
        for p in periods:
            min_match = w * (n // 2)
            max_match = (w + 1) * (n // 2) - 1
            # Only matches in valid range can be selected
            prob += lpSum([
                is_match[p][w][m]
                for m in total_matches
                if min_match <= m <= max_match
            ]) == 1

    # 5. CHANNELING CONSTRAINT: link team_in_period - team t plays in period p, week w if assigned match contains t
    for t in teams:
        for p in periods:
            for w in weeks:
                prob += team_in_period[t][p][w] == lpSum([
                    is_match[p][w][m]
                    for m in total_matches
                    if matches[m][0] == t or matches[m][1] == t
                ])

    # 6. Each team plays at most twice in any period
    for t in teams:
        for p in periods:
            prob += lpSum([team_in_period[t][p][w] for w in weeks]) <= 2

    # 7. CHANNELING CONSTRAINT: link match_and_home_first and match_and_home_second
    for p in periods:
        for w in weeks:
            for m in total_matches:
                # match_and_home_first[p][w][m] = is_match[p][w][m] AND (1 - which_is_home[p][w])
                prob += match_and_home_first[p][w][m] <= is_match[p][w][m]
                prob += match_and_home_first[p][w][m] <= 1 - which_is_home[p][w]
                prob += match_and_home_first[p][w][m] >= is_match[p][w][m] + (1 - which_is_home[p][w]) - 1

                # match_and_home_second[p][w][m] = is_match[p][w][m] AND (1 - home_is_first[p][w])
                prob += match_and_home_second[p][w][m] <= is_match[p][w][m]
                prob += match_and_home_second[p][w][m] <= which_is_home[p][w]
                prob += match_and_home_second[p][w][m] >= is_match[p][w][m] + which_is_home[p][w] - 1

    # 8. CHANNELING CONSTRAINT: link home/away assignments
    for t in teams:
        for p in periods:
            for w in weeks:
                # Team t plays home if:
                # - match has t as first team AND which_is_home == 1, OR
                # - match has t as second team AND which_is_home == 0
                prob += team_plays_home[t][p][w] == lpSum([
                    match_and_home_first[p][w][m]
                    for m in total_matches
                    if matches[m][0] == t
                ]) + lpSum([
                    match_and_home_second[p][w][m]
                    for m in total_matches
                    if matches[m][1] == t
                ])

                # Team t plays away if:
                # - match has t as first team AND which_is_home == 0, OR
                # - match has t as second team AND which_is_home == 1
                prob += team_plays_away[t][p][w] == lpSum([
                    match_and_home_second[p][w][m]
                    for m in total_matches
                    if matches[m][0] == t
                ]) + lpSum([
                    match_and_home_first[p][w][m]
                    for m in total_matches
                    if matches[m][1] == t
                ])

    # 9. Count total home and away games for each team
    for t in teams:
        prob += Cha[t][0] == lpSum([team_plays_home[t][p][w] for p in periods for w in weeks])
        prob += Cha[t][1] == lpSum([team_plays_away[t][p][w] for p in periods for w in weeks])

    # 10. Define imbalance as sum of absolute differences
    abs_diff = LpVariable.dicts(
        "AbsDiff",
        indices=teams,
        lowBound=0,
        cat="Integer"
    )

    for t in teams:
        prob += abs_diff[t] >= Cha[t][0] - Cha[t][1]
        prob += abs_diff[t] >= Cha[t][1] - Cha[t][0]

    prob += imbalance == lpSum([abs_diff[t] for t in teams])

    # Objective: minimize imbalance
    prob += imbalance

    # Solve
    prob.solve(PULP_CBC_CMD(msg=False))

    # Extract results
    result = {
        'status': LpStatus[prob.status],
        'schedule': {},
        'imbalance': None,
        'home_away_counts': {}
    }

    if LpStatus[prob.status] == "Optimal" or LpStatus[prob.status] == "Not Solved":
        # Extract schedule
        for p in periods:
            for w in weeks:
                match_id = int(value(matches_idx[p][w]))
                is_first_home = int(value(not which_is_home[p][w]))

                if is_first_home == 1:
                    home_team = matches[match_id][0]
                    away_team = matches[match_id][1]
                else:
                    home_team = matches[match_id][1]
                    away_team = matches[match_id][0]

                result['schedule'][(p, w)] = (home_team, away_team)

        # Extract home/away counts
        for t in teams:
            home_count = int(value(Cha[t][0]))
            away_count = int(value(Cha[t][1]))
            result['home_away_counts'][t] = (home_count, away_count)

        # Extract imbalance
        result['imbalance'] = int(value(imbalance))

    return result


def print_schedule(result, n):
    if result['status'] not in ["Optimal", "Not Solved"]:
        print(f"\nOptimization Status: {result['status']}")
        print("Unable to find a solution.\n")
        return

    weeks = range(n - 1)
    periods = range(n // 2)

    print("\n" + "=" * 80)
    print(f"SOLUTION FOUND FOR N = {n}")
    print("=" * 80 + "\n")

    for w in weeks:
        print(f"Week {w + 1}:\n")

        for p in periods:
            home_team, away_team = result['schedule'][(p, w)]
            print(f"  Period {p + 1}: {home_team} vs {away_team}")

        print()

    print("=" * 80)
    print("HOME/AWAY BALANCE")
    print("=" * 80)

    for t in range(n):
        home_count, away_count = result['home_away_counts'][t]
        diff = abs(home_count - away_count)
        print(
            f"Team {t:2d}: Home={home_count:2d}, "
            f"Away={away_count:2d}, Difference={diff}"
        )

    print("\n" + "=" * 80)
    print(f"TOTAL IMBALANCE: {result['imbalance']}")
    print("=" * 80 + "\n")


def main():
    if len(sys.argv) != 2:
        print("Usage: python round_robin_scheduler.py <number_of_teams>")
        print("Example: python round_robin_scheduler.py 12")
        sys.exit(1)

    try:
        n = int(sys.argv[1])
    except ValueError:
        print(f"Error: '{sys.argv[1]}' is not a valid integer")
        sys.exit(1)

    # Validate input
    if n < 6:
        print(f"Error: Number of teams must be at least 6 (got {n})")
        sys.exit(1)
    if n % 2 != 0:
        print(f"Error: Number of teams must be even (got {n})")
        sys.exit(1)

    print(f"\nGenerating schedule for {n} teams...")
    print(f"Total weeks: {n - 1}")
    print(f"Matches per week: {n // 2}")
    print(f"Total matches: {(n - 1) * (n // 2)}")
    print("\nOptimizing...\n")

    try:
        # Solve the problem
        result = optimize(n)

        # Print the results
        print_schedule(result, n)

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
