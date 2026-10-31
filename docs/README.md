# Documentation

The oracle documentation describes the supported state-capture, restoration
and comparison contracts. The research archive records earlier performance
experiments and their limits; those observations are not engine optimizations
or guarantees for another installation.

## Oracle

- [First run and tool configuration](first-run.md)
- [Original-game reference profile](original-reference.md) and
  [RE_Kenshi deviations](rekenshi-deviations.md)
- [MeitouClient target](meitou-target.md) and
  [adapter design and fork maintenance](meitou-oracle-design.md)
- [Patch-series maintenance and version-change rules](maintenance.md)
- [State coverage](state-coverage.md), [saved NPC identities](npc-identities-phase1.md)
  and [complete protocol](protocol.md)
- [Cross-engine comparison](comparator.md)
- [Phase 1 delivery](oracle-phase1-delivery.md),
  [phase 1 validation](oracle-phase1-validation.md) and
  [acceptance scope](phase1-acceptance.md)
- [Quiet-town phase 1 supplement](oracle-ville-calme-validation.md),
  [phase 2 cold-profile milestone](phase2-step0-validation.md) and
  [phase 2 validation and real comparison](phase2-validation.md)
- [Mod-free campaigns on a fresh city save](mod-free-campaigns.md)
- [Paused automatic loading](autoload-pause-validation.md) and
  [pause-preserving speed control](pause-preserving-speed-validation.md)

## Performance research

Historical measurements, ETW, thread identities, stacks, minidumps, renderer
and subsystem timing notes live in [research/](research/README.md). Their
analysis and manual acquisition scripts are in
[tools/research/](../tools/research/README.md).

Raw captures, dumps, private settings and game files remain outside Git.
Links to ignored local evidence describe the validation provenance; they are
not distributed with the public source. Current oracle behavior is defined
by the documents above, not by older version numbers in research notes.
