# MathBuild VR

**Spatial Grounding and Mathematical-Focus Containment in View-Conditioned VR Tutoring**

A virtual reality mathematics environment with **ViewTutor**, a view-conditioned LLM tutoring backend whose mathematical judgments come from a deterministic evaluator.

![Platform: Meta Quest 3](https://img.shields.io/badge/VR-Meta%20Quest%203-142F49)
![Engine: Unity](https://img.shields.io/badge/Engine-Unity-142F49)
![Backend: Python | FastAPI](https://img.shields.io/badge/Backend-Python%20%7C%20FastAPI-087E8B)
![Results: reproducible](https://img.shields.io/badge/Results-Reproducible-167B69)

![MathBuild VR classroom with a word problem, the virtual tutor, workspace objects, and the visibility panel](media/hero.png)

*MathBuild VR running on Meta Quest 3: classroom, mathematical workspace, and tutor interface.*

**Contents:** [Overview](#overview) · [Demo](#demo) · [How it works](#how-it-works) · [Results at a glance](#results-at-a-glance) · [Quick start](#quick-start) · [Reproduce the paper's results](#reproduce-the-papers-results) · [Repository structure](#repository-structure) · [Scope and limitations](#scope-and-limitations)

---

## Overview

In **MathBuild VR**, learners represent elementary mathematical word problems by arranging three-dimensional objects in labeled workspace regions. Its tutoring component, **ViewTutor**, separates deterministic checking of the construction from LLM-generated hints. A compact **visibility snapshot** lets hints account for whether a workspace region is visible, partially visible, or outside the learner's current view.

The accompanying research asks two questions:

- **Spatial grounding (RQ1):** Does a hint's workspace reference identify an appropriate region and agree with the recorded view?
- **Mathematical-focus containment (RQ2):** Does the mathematical issue a hint addresses stay the same when the view changes but the construction does not?

> **Research scope:** The reported experiments use scripted visibility snapshots, not learner sessions. This repository does **not** claim improvements in learning outcomes or pedagogical effectiveness.

## Demo

| Meet the tutor | Construct with objects | Request help |
|:---:|:---:|:---:|
| ![Virtual classroom and tutor](media/welcome.gif) | ![Learner placing objects in workspace regions](media/interact.gif) | ![Help controls in the classroom](media/controls.gif) |
| Explore the virtual classroom. | Build a mathematical representation. | Ask for help and move between problems. |

These clips show the VR interface. For view-conditioned hint examples and their evaluation, see [`examples/example_hints.json`](examples/example_hints.json) and the [supplementary material](paper/Supplementary_Material.pdf).

## How it works

```text
Meta Quest 3 (MathBuild VR)
 ├── Learner construction ──► Deterministic evaluator ──► Verified status + errors
 └── Visibility snapshot  ──► Visibility classes + label flags
                                        │
                           ViewTutor prompt construction
                                        │
                     LLM hint generation (non-correct states only)
                                        │
                                Answer protection
                                        │
                           Hint spoken and displayed in VR
```

- **Correct constructions** receive a fixed confirmation without an LLM call.
- **Incomplete or incorrect constructions** go to the LLM with the verified mathematical state and, in the view-conditioned setting, each region's visibility class and label flags.
- The LLM does **not** receive headset imagery, object coordinates, camera pose, or the numerical visible fraction.
- **Problem types:** join, remove, equal groups, equal sharing, and part-to-part ratio. The app includes **88 word problems adapted from ASDiv**.

<details>
<summary><b>What is in a visibility snapshot?</b></summary>

<br>

For each workspace region, the headset estimates a visible fraction *f* from **nine sample points** on the region's top face, counting points that are inside the viewport and not occluded. The backend converts *f* into a visibility class:

| Class | Visible fraction |
|---|---|
| Hidden | *f* < 0.10 |
| Partially visible | 0.10 ≤ *f* < 0.70 |
| Mostly visible | *f* ≥ 0.70 |

The prompt also receives whether each region's label is currently visible and whether it was previously seen. Serialized examples are in [`examples/visibility_snapshots.json`](examples/visibility_snapshots.json). The evaluation used directly assigned, scripted fractions rather than live headset sampling.

</details>

## Results at a glance

The preliminary evaluation used **20 non-correct construction states**, **five scripted view conditions**, and **two generations** per state, view condition, and prompt condition: **200 view-conditioned** and **200 view-blind** hints in total.

| Measure | Result |
|---|---:|
| Hints generated and annotated | **400** |
| View-conditioned hints with a specific workspace reference (coverage) | **143 / 200 (72%)** |
| Grounded success among evaluable reference-making hints | **138 / 142 (97%)** |
| Grounded yield (all hints except one annotation-indeterminate case) | **138 / 199 (69%)** |
| Mathematical-focus changes across view conditions | **15 / 120 (13%)** |
| Mathematical-focus changes within the same view condition | **1 / 60 (2%)** |

**Key observation:** all 15 cross-view focus changes involved **partial visibility** and came from **five construction states**. Grounded spatial references did not guarantee a stable mathematical focus.

These findings are **descriptive and preliminary**. The 20 states were also used during prompt development, one partially blinded author annotated all hints, and the design does not separate the effect of visibility information from that of the spatial-wording rules.

## Quick start

### Run the ViewTutor backend

**Windows (PowerShell)**

```powershell
cd ViewTutor-backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**macOS / Linux**

```bash
cd ViewTutor-backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`.env.example` sets `USE_MOCK_LLM=1`, so the backend starts **without an API key**.

- Health check: <http://127.0.0.1:8000/api/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>

Run the tests from a second terminal inside `ViewTutor-backend/`:

```bash
python -m pytest
```

To use a real model, add your own key to `.env` and set `USE_MOCK_LLM=0`. **Never commit `.env` or generated logs.** A new run can produce different text from the frozen evaluation outputs. The model and settings used in the paper are documented in the [supplementary material](paper/Supplementary_Material.pdf), and the current backend prompt may differ from the frozen evaluation prompts.

## Reproduce the paper's results

No API key or headset is needed. The script uses only the Python standard library and the released annotations:

```bash
cd evaluation
python reproduce_results.py
```

It prints:

- **RQ1:** coverage, grounded success, grounded yield, and orientation-phrase counts per view condition
- **RQ2:** cross-view and same-view focus changes, target changes, and the upper bound
- **Intervals:** descriptive 95% percentile bootstrap intervals over construction states (fixed seed, 100,000 resamples)

The script recomputes the reported analysis from the released CSV files; it does not regenerate or re-annotate the hints.

## Repository structure

| Path | Contents |
|---|---|
| [`ViewTutor-backend/`](ViewTutor-backend/) | Python/FastAPI tutoring service: deterministic evaluator, LLM integration, answer protection, question bank, sample captures, and tests |
| [`unity-integration/Scripts/`](unity-integration/Scripts/) | Selected MathBuild VR C# source for reference and integration (**not a complete Unity project**) |
| [`evaluation/evaluation_data.csv`](evaluation/evaluation_data.csv) | All **400** generated hints with annotations |
| [`evaluation/target_pair_classification.csv`](evaluation/target_pair_classification.csv) | The **76** differing-target pairs and their classifications |
| [`evaluation/annotation_guidelines.md`](evaluation/annotation_guidelines.md) | Annotation criteria and metric definitions |
| [`evaluation/reproduce_results.py`](evaluation/reproduce_results.py) | Recomputes the reported counts and bootstrap intervals |
| [`prompts/`](prompts/) | Frozen view-conditioned and view-blind evaluation prompts |
| [`examples/visibility_snapshots.json`](examples/visibility_snapshots.json) | One construction state under all five scripted view conditions |
| [`examples/example_hints.json`](examples/example_hints.json) | Unedited hints, the grounding failures, and a focus-change example |
| [`paper/Supplementary_Material.pdf`](paper/Supplementary_Material.pdf) | Pipeline, prompts, evaluation states, annotation protocol, and additional results |
| [`media/`](media/) | Classroom screenshot and short feature recordings |
| [`docs/`](docs/) | Supporting technical documentation |

### Naming in the data files

The software is presented as **MathBuild VR** (application) and **ViewTutor** (tutoring backend); some source files still use earlier names. In the evaluation data, the **view-blind** condition is labeled `reference`, and the hidden visibility class appears as `not_visible`. These identifiers are kept unchanged for traceability; `reference` prompts received **no** visibility information.

The frozen prompts are reproduced exactly as used in the study, including a reference to an `arrangement_description` field that was not in the evaluation payload (see Supplementary Material, S3.4). Do not edit them when reproducing the study.

## Scope and limitations

- **Unity release:** The full VR application, scenes, and third-party assets are not distributed. The C# scripts are reference source, not a buildable Unity project.
- **Reproduction:** The CSVs and script reproduce the reported analysis without a headset or API key. Regenerating hints requires an API key and can produce different text.
- **Evaluation:** All visibility snapshots were scripted, and the hidden-unseen condition is a synthetic stress test. No learner sessions or learning outcomes were evaluated.
- **Annotation:** One partially blinded author annotated all hints. Pairs with identical targets were counted as the same focus, and pair classifications were not independently checked.
- **Licensing:** The VR environment uses third-party dependencies. Commit only code and assets you are allowed to redistribute, and choose a `LICENSE` that matches the rights you hold.
