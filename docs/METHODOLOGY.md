# Methodology

## Design principle

The optimizer is a deterministic decision-support model. The schedule, campus geography, parking characteristics, permit rules, semester timing, and user weights determine the ranking. Confidence is calculated separately so uncertainty does not silently alter the nominal winner.

## 1. Schedule → parking sessions

Each class needs only:

- day
- building
- start time
- end time

The validator rejects incomplete rows, unknown buildings, end times that are not after start times, and overlapping classes on the same day.

A gap of at least two hours triggers a question asking whether the commuter normally leaves campus. A **Yes** answer ends the current parking session and creates another arrival later that day. A **No** answer keeps both classes in the same parking session.

## 2. Walking cost

For each candidate lot and parking session, the model considers:

- walking from the lot to the session's first class; and
- walking from the session's final class back to the lot.

Walking inconvenience is capped at a 15-minute one-way walk:

```text
WalkCost(seconds) = min(seconds / 900, 1) × 100
SessionWalkingCost = 0.55 × arrival_walk + 0.45 × final_walk
```

The arrival walk receives slightly more weight because it occurs under a class-start deadline.

## 3. Search-risk model

Search risk is a relative 0–100 inconvenience score, not a probability that a lot will be full.

The baseline combines:

```text
occupancy pressure
+ time-of-day modifier
+ semester-phase modifier
+ lot-specific searchability effects
```

Examples of lot-specific behavior include:

- **Central Lot 1:** its slanted geometry and poor visibility create a crowding-dependent searchability penalty; the penalty increases as the lot becomes busier.
- **Central Lot 2:** it can be crowded while remaining easier to scan because of its more conventional layout.
- **West Deck:** an additional circulation penalty is applied only when the deck is already busy.

The opening weeks receive a higher demand modifier, while late-semester weeks are modeled as somewhat easier.

## 4. Arrival-by time

The model converts search risk into a parking-search reserve. Higher-risk sessions receive more buffer time. It then works backward from class start time:

```text
arrival-by = class start
             - mapped walk to class
             - search reserve
             - 5-minute entry buffer
```

Arrival is solved iteratively because arriving earlier can itself reduce the modeled search risk.

## 5. Shade

Shade combines shade potential and reliability. A lot with consistent structural coverage can score differently from a lot where only some spaces are shaded.

Shade is also scaled by how long the car remains parked:

```text
ShadeExposureFactor = clamp(session_minutes / 360, 0.20, 1.00)
EffectiveShadePenalty = RawShadePenalty × ShadeExposureFactor
```

This prevents a short visit from receiving the same shade penalty as an all-day stay.

## 6. User preferences

Default weights are:

```text
Walking     50
Reliability 35
Shade       10
Price        5
```

Users may enter any non-negative values; the engine normalizes them automatically.

For each parking session, the model selects the lowest-scoring commuter-legal lot available to that permit:

```text
SessionScore =
    walking_weight × walking_cost
  + reliability_weight × search_risk
  + shade_weight × effective_shade_penalty
```

## 7. Weekly permit score

A permit should perform well across the whole recurring week, not merely on its easiest day:

```text
FunctionalPermitScore =
    0.80 × mean(best session scores)
  + 0.20 × worst(best session score)
```

Price is then added as a separate weighted term. The price scale is intentionally compressed so that small price differences do not overwhelm schedule fit under balanced preferences.

Lower final scores are better.

## 8. Flex parking

For sessions beginning at or after 5:00 PM, the model permits the after-hours commuter flex behavior represented in the current ruleset. Residential parking is not treated as an ordinary commuter recommendation.

## 9. Confidence

Confidence does **not** choose the winner. It measures how robust the nominal winner is to plausible uncertainty in search-risk and shade inputs.

The current demo repeatedly perturbs uncertain lot characteristics and reruns the full optimizer. It combines:

- how often the nominal winner remains first; and
- the score separation between first and second place.

Opening-week recommendations receive an additional uncertainty penalty. Therefore, a coherent nominal recommendation can still have low confidence when the top two permits are nearly tied.

## 10. Preference sensitivity

The app's “How changing your priorities affects the recommendation” section does not use 100/0 extremes. For each factor, the engine increases that factor substantially while reducing the remaining weights proportionally, then reruns the **same schedule through the full optimizer**.

This makes the comparison schedule-aware. For example, emphasizing reliability can change the recommendation only if another permit actually provides a better reliability tradeoff for that student's classes and arrival times.

## 11. Low-frequency commuter guidance

Commuting only one or two days per week does not automatically change the score. Instead, the UI separately points out cheaper permits that may be worth considering because the user experiences their inconvenience less frequently.

## Evidence and limitations

The model combines official permit/map constraints, a mapped walking-distance matrix, firsthand campus observations, and structured community reports. Community reports are treated as imperfect evidence and extreme Fall 2025 disruption reports are not averaged into the normal baseline.
