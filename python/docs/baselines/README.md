# Starting-SHA performance baseline

Source: `0150f901fbda2240bd4b8639f84b3dbdda311089`. Two warmups and 11 measured unprofiled samples per case/mode. Times below are milliseconds. Cold clears all geometry/partition caches before each sample; warm retains them. Stage medians need not sum to the median total. These are baseline observations, not a speedup claim.

Core: Python 3.10.11, NumPy 2.1.2, Shapely 2.1.2, GEOS 3.13.1.

| Case | Normalize | Decompose | Connect | Tessellate | Validate | Cold total | Cold p95 | Warm total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rectangle_gable | 1.07 | 2.75 | 4.99 | 1.34 | 1.60 | 12.25 | 14.17 | 10.72 |
| orthogonal_L | 1.67 | 15.00 | 21.73 | 2.78 | 2.87 | 43.91 | 93.35 | 29.22 |
| orthogonal_T | 2.47 | 24.13 | 18.91 | 2.72 | 2.83 | 52.49 | 66.53 | 24.07 |
| orthogonal_U | 2.33 | 73.14 | 46.17 | 4.77 | 3.73 | 132.56 | 140.74 | 88.12 |
| residential_multi_reflex | 5.33 | 840.37 | 73.97 | 6.64 | 5.34 | 944.30 | 1245.28 | 87.94 |
| oblique_L | 1.51 | 24.36 | 29.87 | 3.27 | 2.85 | 63.94 | 66.87 | 39.37 |
| general_convex_quad | 1.12 | 2.89 | 5.74 | 1.60 | 1.58 | 13.38 | 15.69 | 9.19 |

Blender 5.1.0: Python 3.13.9, NumPy 2.3.4, Shapely 2.1.2, GEOS 3.13.1. Input covers evaluated mesh extraction/placement and adapter validation; mesh creation includes UV/materials. Full core validation remains active.

| Case | Adapter input | Mesh creation / UV / materials | Cold core | Cold total | Cold p95 | Warm total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rectangle_gable | 1.51 | 0.44 | 10.68 | 12.68 | 15.08 | 13.89 |
| orthogonal_L | 1.60 | 0.51 | 55.09 | 57.49 | 92.88 | 29.12 |
| orthogonal_T | 1.67 | 0.54 | 50.00 | 52.30 | 59.63 | 31.02 |
| orthogonal_U | 1.68 | 0.53 | 100.72 | 102.84 | 116.21 | 45.24 |
| residential_multi_reflex | 1.80 | 0.57 | 750.25 | 752.69 | 813.73 | 74.19 |
| oblique_L | 1.68 | 0.46 | 51.78 | 53.93 | 64.33 | 35.26 |
| general_convex_quad | 1.51 | 0.41 | 10.45 | 12.43 | 13.00 | 11.03 |

Raw samples: [core](roof_core_0150f90.json), [Blender](roof_blender_0150f90.json). Separate diagnostic [profile](roof_profile_0150f90.json) and [overlay audit](roof_overlay_0150f90.json). Profiler cumulative times overlap and must not be summed or substituted for the unprofiled numbers.

Regression at this baseline: 28 unit tests pass; 27 semantic snapshots match the archived starting addon; installed Blender 5.1 smoke passes all 16 mandatory cases, all four roof types, transformed input, failure without scene mutation, UV/material checks and disable/re-enable. The smoke still performs the existing dependency-install step. The pre-existing cyclic automatic-shed directional ambiguity is recorded separately in the harness; it is not claimed as a passing invariant.
