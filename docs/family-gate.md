# Family gate — camera design candidate

54 rows: 42 PASS, 4 FINDING, 4 NOT RUN, 2 SKIP, 2 FAIL. Full acceptance is false.
See [deviations](acceptance-design.md#family-integration-run) and [JSON evidence](history/acceptance-through-0.4.0/artifacts/family-gate.json).

| Gate | Result | Status |
|---|---|---|
| revision pins | 8/8 exact; audited before builds | PASS |
| one plugin path | 6/6 libraries | PASS |
| core | 42/42 (unchanged pinned library; prior check) | PASS |
| buildup | 20/20 (unchanged pinned library; prior check) | PASS |
| wall | 48/48 (unchanged pinned library; prior check) | PASS |
| pipe | 41/41 (unchanged pinned library; prior check) | PASS |
| cctv | 118/118 | PASS |
| sync | no acceptance count; see log | FAIL |
| toolchain | 4/4 | PASS |
| datacentre | 53/53 | PASS |
| cctv scenarios | 30/30 (embree) | PASS |
| demo ifc + bonsai | IFC: 3 edits; Bonsai unavailable | NOT RUN |
| demo parity | 0/0 | NOT RUN |
| roundtrip profile | 0 errors on both demo stages | PASS |
| cctv demo derivation | 4/4 sensors | PASS |
| cctv demo steps | 6/6; findings printed | PASS |
| cctv demo render | toolchain usd-dev Python with Embree and usdrecord is unavailable | SKIP |
| Revit | live Revit acceptance not configured | NOT RUN |
| datacentre build | loadedMachineLimit=45; nominalBudget=15; seconds=14.806 | PASS |
| DC-build | files=8 | PASS |
| DC-convert | elements=2954; extents=33; phasePercent=100.0; phases=2954; unparented=0 | PASS |
| DC-system | cameras=45; recorderCapacity=45; retentionDays=90 | PASS |
| DC-import | cameras=45; pipes=476; presets=7; sensors=45; types=3; walls=92 | PASS |
| DC-derive | sectors=45; sensors=45; tours=3 | PASS |
| DC-profile | designErrors=9; implementationErrors=0; nativePortGaps=160; statusEnumsNormalized=3; warnings=4000 | PASS |
| DC-critical-doors | exclusions=0; fixedCovered=11; seconds=0.812; targets=11; views=11 | PASS |
| DC-external | exclusions=0; fixedCovered=4; seconds=0.576; targets=5; views=5 | FINDING |
| DC-corridors | exclusions=0; fixedCovered=7; seconds=4.949; targets=7; views=29 | PASS |
| DC-yard-day | exclusions=0; fixedCovered=4; seconds=0.727; targets=8; views=15 | FINDING |
| DC-yard-night | exclusions=0; fixedCovered=4; seconds=0.673; targets=8; views=11 | FINDING |
| DC-lobby | exclusions=0; fixedCovered=3; seconds=0.581; targets=3; views=5 | PASS |
| DC-privacy-baseline | exclusions=0; fixedCovered=0; seconds=1.499; targets=0; views=49 | PASS |
| DC-revit-parity | exclusions=0; fixedCovered=11; seconds=0.619; targets=11; views=11 | PASS |
| DC-column | columnBlockers=2 | FAIL |
| DC-idempotence | reused=136; views=136 | PASS |
| DC-determinism | builds=2; normalizedStageHash=76841cd0e919157221b8598c4b05902f819d0c28faddb3aad7433a4485bdbb04; secondHash=76841cd0e919157221b8598c4b05902f819d0c28faddb3aad7433a4485bdbb04; studies=8 | PASS |
| DC-tray | limitation=Tray edit retained; newly uncovered door and tray attribution are not proven.; loweredMetres=0.9; tray=/demo_datacentre_01/demo_datacentre_01_Site/demo_datacentre_01/L00_Ground/Data_Spine_A_Seg_1; uncovered=1 | FINDING |
| DC-temporary | blocker=/ScenarioEdits/LoadingHoarding; ignoredFraction=1.0; includedFraction=0.0 | PASS |
| DC-privacy | camera=/demo_datacentre_01/demo_datacentre_01_Site/demo_datacentre_01/L00_Ground/Corridor_West/sec_cam_corr_corr_w_1; panDegrees=20.0 | PASS |
| DC-hall-rule | camera=/demo_datacentre_01/demo_datacentre_01_Site/demo_datacentre_01/L00_Ground/Corridor_West/sec_cam_corr_corr_w_1; errors=1 | PASS |
| DC-noc-turn | limitation=NOC monitoring is allowed. Privacy-error demonstration uses a hall intrusion instead.; panDelta=20.0 | PASS |
| DC-ptz-duty | dutyFraction=0.6666666666666666; expectedHomeDuty=0.3333333333333333; limitation=Fixed lobby cameras removed from this negative control only; sole-PTZ grading remains required. | PASS |
| DC-night-override | fraction=0.0; irMetres=0.1 | PASS |
| DC-stale |  | PASS |
| DC-results-incomplete |  | PASS |
| DC-sync-ifc | accepted=3; guidPreserved=True; maxPositionError=0.0; mutations=3; pan=35.0; pending=0; repeatMutations=0; tilt=40.0; transactions=2 | PASS |
| DC-sync-bonsai | reason=Blender with Bonsai is unavailable | NOT RUN |
| DC-vanilla | stages=10 | PASS |
| DC-render | reason=toolchain usd-dev Python with Embree and usdrecord is unavailable; status=skipped | SKIP |
| datacentre sanitization | files=142 | PASS |
| DC-budget | kernel=embree; limit=240; seconds=149.771 | PASS |
| gate regression tests | 48 passed in 11.52s | PASS |
| links | 18/18 roots | PASS |
| sanitization | 53 text files, no matches | PASS |
