# Clash publication acceptance — 0.4.4

This patch retains the three exact circular IFC sweeps and the 5 mm clearance.
It changes the published tessellation of two pipes so the mesh route needs
more precise evidence to decide the near and tangent cases.
The [full gate receipt](../artifacts/generator-0.4.4.json) records
**201 checks, 0 failed**: 159 passes, 38 timings and four native variants NOT RUN.

| Case | Mesh signed distance, mm | Measured band, mm | Mesh verdict | Analytic exact verdict |
|---|---:|---:|---|---|
| (a) hard | −75.000003 | 0.2201 | hard | hard |
| (b) near | +5.000114 | 5.7582 | undecidable | clearance, 5 mm |
| (c) tangent | −1.063541 | 1.0636 | falsePenetration | touching, 0 mm |

All three source radii are 30.15 mm. The near pipe uses a 6 mm maximum
inscribed deflection, giving five sides and a vertex toward the tray.
The tangent pipe uses a 1.2 mm maximum circumscribed deflection, giving twelve
sides and a vertex toward the wall. The source body remains tangent; the
circumscribed vertex causes the mesh penetration.

The [published manifest](../dist/clash/dc.manifest.json) records the source
geometry, settings, measured bands, witnesses and verdicts. Tolerances are
measured from serialized vertices and chord interiors and rounded outward
to 0.1 µm. Both tolerance attributes are authored on the bodies in the
derived geometry layer. The planar partners have zero chordal error.

The [released clash engine probe](../manifests/clash-engine-probe-0.4.4.json)
independently reproduces these three signed distances. It reads the pipe
stamps, measures the planar partners, and reports the band decides only (a).
This is a recorded consumer probe; the permanent gate has no dependency on
the consumer package. Its finite-face checks, two fresh publications per
variant and source/manifest comparison prevent the expectations from drifting.

| Verification | Result |
|---|---|
| Full gate | 201 checks, 0 failed |
| pytest | 186 passed |
| Structure lint | 28 checks, 0 failed |
| IFC schema and semantics | 42 files clean across five variants |
| Reproducibility | 10 fresh publications; all layers/manifests match committed bytes |
| Vanilla freshness | 5/5 independently rendered, fresh and non-uniform |
| Core validation | 8/8 callbacks loaded through UsdValidation; 5/5 stages, zero errors; two existing proxy warnings each |
| Sanitization | 0 hits, including decoded USD and image metadata |
| Focused clash regression tests | 12 passed |
| Four unchanged variants | 32/32 files match v0.4.3 Git blobs: 24 publication files, four source manifests, four cameras |
| Unchanged rendering receipts | 8/8 records, four overview plus four vanilla |
| Hard pipe | Original points, topology and world transform retained; measured tolerance added |
| Clash shape arrays | 3,013/3,015 meshes unchanged; only the two selected pipes differ |
| Clash vanilla | 1280×800, 144,689 bytes, stock USD / Embree |
| Clash overview | 1280×800, 144,199 bytes |
| Clash publication | 2,140,493 bytes including both images; below the 10 MB cap |
| Licence | MIT |

Reproduce with the pinned environment and separate source overrides described
in the [README](../README.md#build-and-check):

```sh
env -u PYTHONPATH "$PY" -m dcbuild publish --variant clash
env -u PYTHONPATH "$PY" -m dcbuild render --variant clash
env -u PYTHONPATH "$PY" run.py --variant clash --publish
env -u PYTHONPATH PYTHONPATH="$AECO_VALIDATION_CORE_ROOT:$PWD" "$PY" check.py
```

## Deviations

- Converter 0.1.0 exposes no per-product deflection controls. A local
  conversion adapter tessellates the two selected IFC circular sweeps before
  the pinned converter authors USD. No dependency checkout changes. The
  five-sided near pipe is intentionally coarse comparison data. The setting
  is 6 mm; the measured band is 5.7582 mm. The tangent mesh penetration is
  1.06354 mm rather than the earlier illustrative 1.2 mm.
- Exact verdicts are analytic source-fixture checks, also tied to the
  generated IFC sweeps by tests. An exact-body engine is not run here.
- The single offline Nix attempt, with direct source overrides and outbound
  connections disabled, could not connect to the Nix daemon socket. Evaluation
  did not start; no lockfile was written. Nix packaging is **not proven**.
- Stock USD flattening warns when dropping the unregistered `aecoDerived`
  metadata annotation. Mesh coordinates and numerical tolerance attributes
  survive; the original published geometry retains the annotation. The
  vanilla render runs without family plugins.
- Native execution is unchanged; four native variant rows remain NOT RUN.
  The exterior previews show the facility; inspect the published bodies and
  measured receipts for the internal millimetre-scale cases.
