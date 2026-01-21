% SPORTS SCHEDULING PROBLEM (ROUND ROBIN)
% This model schedules a Round Robin tournament for N teams.
% Key constraints:
% 1. Every team plays every other team exactly once.
% 2. Every team plays exactly once per week.
% 3. No team plays more than twice in the same period (time slot).

include "globals.mzn";

% PARAMETERS AND SETS

int: N;               
% Number of teams. Must be even.
constraint assert(N mod 2 = 0, "Number of teams must be even");

set of int: T = 0..N-1;
% Set of all teams.

set of int: S = 0..1;
% Slots per match (0 = Home, 1 = Away).

set of int: W = 0..N-2;
% Weeks in the season.

set of int: P = 0..N div 2 - 1;
% Periods (time slots) per week.

set of int: M = 0..(N - 1) * (N div 2) - 1;
% Total number of matches to be played.

set of int: TeamsInSamePeriod = 0..2 * (N - 1) - 1;
% Helper set for the total number of team slots in a specific period across all weeks.

% DATA GENERATION (CIRCLE METHOD)

array[P, W, S] of int: rb = array3d(P, W, S,
  [ if s == 0 then
        if p == 0 then 
            if w mod 2 == 0 then N-1 else w endif 
        else (p + w) mod (N-1) endif
    else
        if p == 0 then 
            if w mod 2 == 0 then w else N-1 endif 
        else (N - p + w - 1) mod (N-1) endif
    endif
    | p in P, w in W, s in S
  ]);

% Flatten to list of matches
array[M, S] of int: matches =
  array2d(M, S, [
    rb[p, w, s]
    | w in W, p in P, s in S
  ]);

% DECISION VARIABLES

% The Match ID assigned to period p in week w.
array[P, W] of var M: matches_idx; 

% Count of how many times team t played in week w.
array[W, T] of var P: Cw;  

% RE-INSERTED: Count of how many times team t plays in period p.
% We calculate this explicitly to enforce the limit.
array[P, T] of var W: Cp;

% CORE CONSTRAINTS

% 1. VALIDITY
constraint alldifferent(matches_idx);

% 2. CHANNELING FOR WEEKS (Cw)
constraint forall(w in W)(
    global_cardinality(
        [matches[matches_idx[p, w], s] | p in P, s in S], 
        [t | t in T],
        [Cw[w, t] | t in T]
    )
);

% 3. WEEKLY CONSTRAINT
constraint forall(w in W, t in T)( Cw[w, t] = 1);

% 4. PERIOD CONSTRAINT 
% We calculate Cp using the 'count' function.
constraint forall(p in P)(
  let{
    % Get the list of match IDs for this period across all weeks
    array[W] of var int: indexes_of_matches = 
        array1d(W, [matches_idx[p, w] | w in W]);
    
    % Get the list of actual teams playing in those matches
    array[TeamsInSamePeriod] of var int: teams_in_period = 
        array1d(TeamsInSamePeriod, [matches[i, s] | i in indexes_of_matches, s in S])
  } in
  forall(t in T)(
    % Use 'count' to calculate how many times team t appears in this period
    Cp[p, t] = count(teams_in_period, t)
  )
);

% 5. LIMIT ON CP
% Each team can play at most twice in the same period.
constraint forall(p in P, t in T)(
    Cp[p, t] <= 2
);

% SYMMETRY BREAKING

% Fix the first week to the default Circle Method order
constraint forall(p in P)(
    matches_idx[p, 0] = p
);

% Lexicographic ordering of weeks
constraint symmetry_breaking_constraint(
    forall(w in min(W)..max(W)-1)(
        lex_less(
            [matches_idx[p, w] | p in P],      
            [matches_idx[p, w+1] | p in P]     
        )
    )
);

% SOLVE STRATEGY

solve 
:: restart_luby(100) 
:: relax_and_reconstruct([matches_idx[p, w] | p in P, w in W], 60)  
:: int_search([matches_idx[p, w] | p in P, w in W], dom_w_deg, indomain_min, complete)  
satisfy;

% OUTPUT

output [
  concat([
    "Week \(w+1):\n\n",
    "  ",  
    concat([ "Period \(p+1)\t" | p in P ]), 
    "\n    ",  
    concat([
      "\(matches[matches_idx[p, w], 0]) vs \(matches[matches_idx[p, w], 1]) \t"
      | p in P
    ]),
    "\n\n"  
  ])
  | w in W
];