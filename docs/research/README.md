# Performance research archive

These notes preserve the historical experiments, measurements and uncertainty
that preceded the functional oracle. No new campaign or performance improvement
is implied by moving them here. Numeric results keep their recorded versions
and scope. Earlier notes may retain decimal commas and literal runtime output.

- [Research questions and history](open-questions.md),
  [benchmark protocol](benchmark-protocol.md) and
  [diagnostic workflow](performance-diagnostic.md)
- [Scene snapshots](scene-snapshot-measurements.md),
  [observer overhead protocol](observer-overhead-protocol.md) and
  [randomized observer protocol](randomized-observer-protocol.md)
- [Thread CPU](thread-cpu-measurements.md),
  [startup metadata](thread-start-metadata.md),
  [SDK thread roles](sdk-thread-roles-measurements.md) and
  [user-stack captures](user-stack-capture-measurements.md)
- [ETW camera validation](etw-camera-validation.md),
  [static worker-stack observations](worker-stack-static-085.md) and
  [worker-object validation](worker-object-validation.md)
- [Root frame](root-frame-measurements.md),
  [root CPU](root-cpu-measurements.md),
  [root battle](root-battle-measurements.md) and
  [aggregate statistics](aggregate-statistics-measurements.md)
- [Historical build and runtime validation](validation.md)

The remaining `*-measurements.md` files in this directory retain their
individual evidence and limitations. `performance-cohorts*.json` contains
reviewable campaign definitions, not captured game content.

Use the [research tools guide](../../tools/research/README.md) for the current
locations of scripts. Return to the [oracle documentation](../README.md)
for the phase 2 reference profile, state schema and comparator.
