# User screenshot evidence

The user supplied four top-view screenshots and described the result as separate
buildings stuck together. A single mesh object is consistent with this symptom:
connected, planar, valid mesh incidence does not establish architectural unity.

## Inputs and observed outputs

[The four screenshots](authority/user-images/image-1.png) are preserved, alongside
[image 2](authority/user-images/image-2.png), [image 3](authority/user-images/image-3.png)
and [image 4](authority/user-images/image-4.png). The ordered XY approximations are
in [a separate fixture](../tests/fixtures/user_roof_images_v1.json). They use grid
ratios from the screenshots. Absolute scale, exact original vertices, source
face connectivity and the loaded addon revision have not been recovered.

Image 4 approximates a 6×3 lower rectangle and a 7×3 upper rectangle, shifted
right by one grid unit, touching along a partial long edge. Its outline is:

```text
(0,0),(6,0),(6,3),(8,3),(8,6),(1,6),(1,3),(0,3)
```

## Historical causal reproduction

The historical public core API at `222037b23d396fb082ac00e24c0a1333221689d9`
successfully generates the four approximate inputs. The isolated source lives
only in ignored diagnostic output; no old generator was restored to production.
The resulting meshes pass that version's mesh validator.

| Screenshot | Historical parts | Ridges | Valleys | Hips |
| --- | ---: | ---: | ---: | ---: |
| 1 | 4 | 4 | 3 | 0 |
| 2 | 3 | 3 | 2 | 0 |
| 3 | 3 | 3 | 2 | 2 |
| 4 | 2 | 2 | 1 | 0 |

The [recorded historical meshes](authority/user-images/historical-core.json)
were transported unchanged into Blender and rendered from above:
[1](authority/user-images/historical-image-1.png),
[2](authority/user-images/historical-image-2.png),
[3](authority/user-images/historical-image-3.png),
[4](authority/user-images/historical-image-4.png).
These are renders of historical core results, not proof that the historical
installed operator was running in the user's live Blender session.

For image 4, the lower ridge is at y=1.5, the upper ridge at y=4.5, both with
height 0.75 for pitch 0.5. The shared interval `(1,3)–(6,3)` remains a valley at
height zero. It is welded into one validated roof mesh, but both rectangle roofs
retain their separate slope pairs and ridge systems. This reproduces the
visible separate-building structure rather than merely identifying a valley
label.

The source chain is `roof_building.generate_roof → decompose → connect →
roof_graph._supports → roof_planes.primitive(part)`. `_supports` starts from a
roof solid for every part. `primitive` chooses an opposing eave pair for each
gable quadrilateral. On this input the adjacent long sides become the zero-height
supports of the separate slopes. `classify_crease` subsequently labels the
shared boundary a valley. That label explains construction; it does not justify
adopting the boundary as a roof junction.

## Scope of the current fix

Both the task's starting canonical revision `0210d79` and current production
`38657f6` reject all four approximations in actual installed-ZIP Blender operator
tests. See [starting operator](authority/user-images/operator-baseline.json)
and [current operator](authority/user-images/operator-current.json).
Each rejection is atomic; no roof object was created. Parallel contacts block
all four inputs, with an additional partial-end contact in image 3.

Consequently, the reported appearance has a historical causal witness, but it
was not reproduced as a successful output of the task's starting canonical
pipeline. The images alone do not identify the loaded live version. That
distinction must not be erased by calling the current rejection a successful
natural-roof repair.

The photographed parallel bands meet on **long sides**, not short gable ends.
Hu's short-end R constraints and the implemented shared/T end choices cannot
alone make these bands one architectural roof. The remaining question is how
the parallel rectangle analysis should be aggregated or replaced by another
roof interpretation. The surveyed references do not establish a complete indexed
offset RoofGraph rule, so no arbitrary connection was added. Natural roof
generation for this input remains incomplete.

The current [partition and relation records](authority/user-images/inspection-current.json)
are diagnostic partitions without a selected final roof. They must not be shown
as an accepted ArchitecturalPart solution. The
[starting records](authority/user-images/inspection-baseline.json) likewise have
no selected roof.
