# Annotation guidelines (as given to the annotator)

Evaluation objective: check whether each hint identifies a specific VR region, addresses an appropriate mathematical target, and is consistent with the recorded view.

- **Specific spatial reference.** A phrase directing the student to a particular workspace region using a name, an object noun used spatially, a description, a pointing expression, or orientation. Story-only and whole-construction phrases are not specific references. A story noun is spatial only when used to identify a VR region; do not infer a region from story events alone.
- **Category.** 1 = uniquely resolved region or defined set; 2 = multiple plausible regions; 3 = no specific workspace reference; 4a = specific reference unresolvable from wording; 4b = cannot decide because scene information or criteria are insufficient.
- **Resolved referent(s).** Exact region name(s) or well-defined set named by the hint. Do not guess from the student error.
- **Referent role.** target = region with the issue; anchor = valid comparison; prospective = region the task requires creating; mixed; other; not_applicable.
- **Mathematical target.** Explicitly identified region(s), separated by +. `construction` for whole-construction issues, `none` for story-only hints. If a region is named alongside general language, keep the named region.
- **Admissibility.** yes if target and anchors suit the task; no if not; not_applicable for category 3; indeterminate for 4b. Interchangeable regions are equally admissible. A not-yet-created region is valid if the task requires creating it.
- **Visibility consistency.** Judged against the recorded view. Naming or turning toward a hidden region is allowed; claiming a hidden region is immediately visible is not. Do not infer directional errors without recorded geometry. Deixis on a partially visible region is not a contradiction; presupposing its full contents are visible is.
- **Hard grounding failures.** nonexistent_referent, inadmissible_target, visibility_contradiction, directional_contradiction, unsupported_spatial_claim, or other. Category 2 and 4a failures are counted from the category and not entered again.
- **Orientation phrase present.** yes for explicit instructions to turn, look around, or orient toward a region; otherwise no. Orientation alone is not a grounding failure.
- **Confidence.** High / Medium / Low.

## Metrics
- Coverage = hints with category 1, 2, 4a or 4b.
- Grounded success = category-1 hints that are admissible, visibility-consistent and without hard failure, over evaluable (1, 2, 4a) hints.
- Grounded yield = same numerator over all hints except category 4b.
- Category 4b is excluded from the denominators of grounded success and grounded yield, not from coverage.

## Mathematical focus (pair classification)
Same focus if both hints ask the same question about the same kind of quantity (swaps between regions with identical content count as the same). Different focus if a different quantity or part of the problem is addressed. Region swap = the same question about a different region with different content. Uncertain otherwise. Pairs with identical annotated targets are counted as the same focus without individual review. Region swaps and uncertain cases are not counted as focus changes (they define an upper bound). The classifications of the 76 differing-target pairs were not independently checked.
