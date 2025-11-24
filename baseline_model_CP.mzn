include "globals.mzn";

int: n;  % Number of teams
constraint assert(n mod 2 == 0, "Number of teams must be even");

int: weeks = n-1;       % Number of weeks (rounds)
int: periods = n div 2; % Number of matches per week
int: slots = 2;         % Slot for each match: 1 = first team, 2 = second team

% Array of teams excluding the pivot (team 1)
array[1..n-1] of int: teams = [i | i in 2..n];

% Schedule array: [period, week, slot], slot 1 = team1, slot 2 = team2
% Deterministic Round-Robin using the Circle Method
array[1..periods, 1..weeks, 1..slots] of int: schedule = 
  array3d(1..periods, 1..weeks, 1..slots,
    [ if p == 1 then
          % First period: pivot (team 1) vs last in rotated circle
          if s == 1 then 1 else teams[((n-2 + w-1) mod (n-1)) + 1] endif
      else
          % Other periods: outside-in pairing
          if s == 1 then teams[p-1] else teams[n-p] endif
      endif
      | w in 1..weeks, p in 1..periods, s in 1..slots
    ]
  );

% Output schedule week by week
output [
  "Week \(w):\n" ++
  concat([
    "Period \(p): " ++ show(schedule[p,w,1]) ++ " vs " ++ show(schedule[p,w,2]) ++ "\n"
    | p in 1..periods
  ])
  | w in 1..weeks
];
