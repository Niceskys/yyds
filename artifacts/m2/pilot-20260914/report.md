# M2 Agent A/B/C Experiment Report

- Phase: `pilot`
- Model: `mimo-v2.5`
- Matches: 36
- Provider calls: 462
- Reserved cost: USD 0.3250
- Provisional Gate 2: **REDESIGN AI ROLE**

| Arm | Matches | Capture rate | Fallback rate | Mean rounds |
|---|---:|---:|---:|---:|
| A | 12 | 0.396 | 0.000 | 12.92 |
| B | 12 | 0.389 | 0.009 | 8.92 |
| C | 12 | 0.368 | 0.012 | 10.33 |

- B−A capture rate: 0.071; bootstrap 95% CI [-0.10411445279866334, 0.2715247715247715]
- C−B capture rate: -0.034; bootstrap 95% CI [-0.2635416666666667, 0.21236772486772484]
- Planner snapshot issues: 0
- Engine invalid-attack events: 261
- Model fallbacks: 5
- Protocol fallbacks: 0
- Replay reconstructability: 100.0%

Pilot results are provisional. Confirm samples and blinded Replay scoring are required before a final product decision. Provider token usage was not returned through the current adapter, so the report separates conservative reserved cost from the UTF-8 character estimate.
