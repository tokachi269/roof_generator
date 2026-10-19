# Kernel source mapping

Research snapshot at `62809e7`; the kernel contract owns implemented guarantees.

## Research and implementation reuse

| Primary source | Relevant mechanism / limitation | Mapping and decision |
| --- | --- | --- |
| [Held & Palfrader, 2017, sections 3.1–3.2, 4.1–4.3, Fig. 12](https://arxiv.org/html/1604.03362) | Finite delayed motion, vertical patches, non-elementary events; an edge that disappears before starting yields a gable without cap postprocessing. | Source speed schedule, event time and wall/roof separation. Permanent zero speed is not automatically covered by the finite-collapse premise; do not choose an arbitrary huge finite delay. |
| [Biedl et al., Weighted straight skeletons in the plane, sections 3–5](https://research-explorer.ista.ac.at/download/1584/5292) | Explicit weighted-event definition and degeneracies; the analyzed multiplicative model excludes zero weights. Negative weights can lose ordinary skeleton properties. | Keep only nonnegative speeds; treat zero-speed and parallel contacts as explicit obligations rather than importing a theorem for strictly positive weights. |
| [Huber & Held, 2011](https://www.sthu.org/research/publications/files/HuHe11.pdf) | Generalized motorcycle graph for PSLGs and global wavefront computation. | Global source lineage and degenerate-event research, not a ready stdlib Python weighted backend. |
| [Weiß, Jüttler & Aurenhammer, 2021, sections 2–4](https://www.ag.jku.at/pubs/2021wj.pdf) | Circular-arc offsets have vanish, terminal, contact and splice events; a splice requires a continuation convention. | Arc sources need an actual geometric evolution and curved patches. Retaining primitive IDs during tessellation alone does not implement this algorithm or prove weighted-gable correctness. |
| [Surfer2 source/build/license](https://github.com/cgalab/surfer2) | Triangulation-based CGAL/C++ implementation, GPLv3, native toolchain and arithmetic dependencies. | Strong event/arithmetic reference; candidate external proof backend. Windows builds and bundled Blender binaries would need validation; no native runtime dependency is added here. |
| [campskeleton source/build/license](https://github.com/twak/campskeleton) | Weighted Java engine, collision handling and per-edge machines; Apache-2.0, Maven/JVM dependencies. | Inspect complete same-height collision handling as a reference. A JVM adapter is not a stdlib Blender installation and its robustness must be tested, not presumed. |

No third-party algorithm source is copied. No new dependency or production fallback
is introduced. License/build information is not proof that a backend accepts all
zero-speed intents.

Concrete source inspection also distinguishes a cluster implementation from a
robustness guarantee. In campskeleton's
[HeightCollision.process](https://github.com/twak/campskeleton/blob/c5e88c9c7f1d0fb600e99efce43f60d47690f6a6/src/org/twak/camp/HeightCollision.java),
same-height collisions are grouped by location, chains are discovered and
validated before removals resume, then horizontal chains are processed. Spatial
grouping uses a fixed `0.01` distance, so this code cannot be assumed to meet the
proposed scale-independent predicate contract unchanged. It is useful researched
state handling, not a license to port its tolerances as certified predicates.
Surfer2 revision `c42f9a7f969cd661d060481cd3b8bac2bdfb8dfa` documents its CGAL/C++
build, including native arithmetic/library dependencies. Its weighted/zero-speed
domain and Windows distribution have not been verified here. Source-read receipts
are in [kernel/research-receipt.json](../evidence/results/kernel/research-receipt.json).


## Published mechanisms and their mapping

| Source | Actual mechanism | Implementation |
| --- | --- | --- |
| Held & Palfrader 2017, sections 3.1–3.2 and 4.1–4.3 | Source schedules, space-time surfaces, weakly z-monotone roofs with vertical facets, simultaneous non-elementary events | `sources.py` defines inclined and stationary source equations; `complex.py` separates inclined patches from walls. Permanent zero speed needs the explicit rules below; the paper's finite-delay premise is not claimed as a theorem for it. |
| Biedl et al., *Weighted straight skeletons in the plane*, sections 3–5 | Global front fragments and source identities; degeneracies depend on the speed domain | Active cyclic supports in `wavefront.py`. Only unit inward EAVE speed and zero GABLE speed are used. No negative weights or general weighted-roof guarantee is imported. |
| campskeleton, `HeightCollision.process`, `CoSitedCollision.findChains/processChains` | Gather coheight/co-sited contacts, discover all chains before mutation, remove collapsed chains, reconnect the surviving chains by angular order | Every current fragment is noded at the certified common time; coincident atomic intervals are resolved together; `rotation.py` constructs their planar cyclic link. The fixed 0.01 spatial grouping in the Java implementation is replaced by exact equality, not copied. |
| Huber & Held 2011, PSLG wavefront/motorcycle model | Global rather than shape-template processing of reflex and degenerate contacts | Vertex/fragment certificates include reflex contacts and components across the entire front. No motorcycle or native backend is called; the current implementation deliberately uses a small-input exhaustive certificate scan. |
| Surfer2, kinetic triangulation implementation | Native certified geometric state and event management | Inspected as a robustness reference. It is not a Blender runtime dependency: CGAL/native deployment and its exact zero-speed domain have not been validated here. |

No third-party algorithm source has been copied. campskeleton's Apache-2.0 Java
build needs a JVM; Surfer2 is GPLv3 with CGAL/C++ dependencies. The separately
inspected Python grassfire implementation uses MIT code but requires `tri`,
`geompreds` and `oseq`, and includes fixed near-zero/angle decisions. None is
presumed to satisfy this numeric contract without verification. The engine here
is GPL-3.0-or-later, matching repository licensing.
