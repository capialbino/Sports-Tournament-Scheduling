include "globals.mzn";

int: N;               % Number of teams (even)
constraint N mod 2 = 0;

set of int: T = 0..N-1;
set of int: S = 0..1;
set of int: W = 0..N-2;
set of int: P = 0..N div 2 - 1;
set of int: M = 0..(N - 1) * (N div 2) - 1;
set of int: TeamsInSamePeriod = 0..2 * (N - 1) - 1;

% creating roung robin tournament
array[P, W, S] of int: rb = array3d(P, W, S,
  [ if s == 0 then
        if p == 0 then N-1 else (p + w) mod (N-1) endif
    else
        if p == 0 then w else (N - p + w - 1) mod (N-1) endif
    endif
    | p in P, w in W, s in S
  ]);

% creating matches
array[M, S] of int: matches =
  array2d(M, S, [
    rb[p, w, s]
    | w in W, p in P, s in S
  ]);


% Var
array[P, W] of var M: matches_idx; % index of the match
array[P, T] of var W: Cp;  % Count how many times team j played in period i
array[W, T] of var P: Cw;  % Count how many times team j played in week w


% each team must play once a week
constraint forall(w in W, t in T)( Cw[w, t] = 1);
% each team should play at most twice in the same period
constraint forall(p in P, t in T) (Cp[p, t] <= 2);
constraint alldifferent(matches_idx); % we need a simmetry braking constraints such as lex because the simmetry is both inverting rows, and columns. Maybe this become redundant

% channeling constraints with Cw
constraint forall(w in W) (
    let {
      array[P] of var int: indexes_of_matches_played_in_week_w = array1d(P, [matches_idx[p, w] | p in P]),
      array[T] of var T: teams_playing_in_week_w  = array1d(T, [matches[i, s] | i in indexes_of_matches_played_in_week_w, s in S])
    } in 
    forall(t in T)(
      Cw[w, t] = count(teams_playing_in_week_w, t)  % Cw[w, t] = c means team t has played c times in week w
    )
);

% channeling constraints with Cp
constraint forall(p in P)(
  let{
    array[W] of var int: indexes_of_matches_played_in_period_p = array1d(W, [matches_idx[p, w] | w in W]),
    array[TeamsInSamePeriod] of var T: teams_playing_in_period_p  = array1d(TeamsInSamePeriod, [matches[i, s] | i in indexes_of_matches_played_in_period_p, s in S])
  } in
  forall(t in T)(
    Cp[p, t] = count(teams_playing_in_period_p, t)  % Cp[p, t] = c means team t has played c times in period p
  )
);

solve satisfy;

output [
  "P: \(p) W: \(w) - \(matches[matches_idx[p, w], 0]) vs \(matches[matches_idx[p, w], 1])\n"
  | w in W, p in P
];

