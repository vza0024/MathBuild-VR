using System;
using System.Collections.Generic;
using System.Text;
using MathConstructVR.Networking.DTOs;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class WorkspacePovDebug : MonoBehaviour
    {
        [Header("References")]
        [SerializeField]
        private WorkspaceController workspaceController;

        [SerializeField]
        private ExperienceController experienceController;

        [SerializeField]
        private SessionController sessionController;

        [SerializeField]
        private Camera hmdCamera;


        [Header("POV Sampling")]
        [Min(0.02f)]
        [SerializeField]
        private float sampleIntervalSeconds = 0.10f;

        [Header("Debug")]
        [Min(0.1f)]
        [SerializeField]
        private float printIntervalSeconds = 1.0f;


        [Header("Region Visibility")]
        [SerializeField]
        private LayerMask occlusionMask = ~0;

        [SerializeField]
        private float raycastTolerance = 0.03f;


        [Header("Label Visibility")]
        [Range(0f, 1f)]
        [SerializeField]
        private float labelVisibilityThreshold = 0.5f;


        private float nextSampleTime;
        private float nextPrintTime;

        private string attemptId;

        private readonly HashSet<string>
            labelsSeenThisAttempt =
                new HashSet<string>();


        private void OnEnable()
        {
            if (experienceController != null)
            {
                experienceController.StateChanged +=
                    HandleExperienceStateChanged;
            }

            if (sessionController != null)
            {
                sessionController.CurrentQuestionChanged +=
                    HandleQuestionChanged;
            }

            StartNewAttemptIdentity();

            nextSampleTime = 0f;
            nextPrintTime = 0f;
        }


        private void OnDisable()
        {
            if (experienceController != null)
            {
                experienceController.StateChanged -=
                    HandleExperienceStateChanged;
            }

            if (sessionController != null)
            {
                sessionController.CurrentQuestionChanged -=
                    HandleQuestionChanged;
            }
        }


        private void Update()
        {
            if (workspaceController == null ||
                hmdCamera == null)
            {
                return;
            }

            if (Time.time >= nextSampleTime)
            {
                nextSampleTime =
                    Time.time + sampleIntervalSeconds;

                SamplePov();
            }

            if (Time.time >= nextPrintTime)
            {
                nextPrintTime =
                    Time.time + printIntervalSeconds;

                PrintVisibility();
            }
        }


        private void HandleExperienceStateChanged(
            ExperienceState state)
        {
            if (state != ExperienceState.Attempt)
                return;

            ResetAttemptTracking(
                "new attempt");
        }


        private void HandleQuestionChanged(
            QuestionDto question)
        {
            string questionId =
                question != null
                    ? question.Id
                    : "unknown";

            ResetAttemptTracking(
                $"question changed → {questionId}");
        }


        private void ResetAttemptTracking(
            string reason)
        {
            labelsSeenThisAttempt.Clear();

            StartNewAttemptIdentity();

            Debug.Log(
                $"[POV] Cleared POV memory: {reason}. " +
                $"attemptId={attemptId}",
                this);
        }


        private void StartNewAttemptIdentity()
        {
            attemptId =
                Guid.NewGuid().ToString("N");
        }


        // ============================================================
        // LOCAL POV SAMPLING
        // ============================================================

        private void SamplePov()
        {
            // Keep label_seen_this_attempt up to date during normal
            // workspace viewing. This samples only; it does not cache
            // a viewpoint for later tutoring requests.
            BuildCurrentViewSnapshot();
        }


        // ============================================================
        // REQUEST-TIME SNAPSHOT SELECTION
        // ============================================================

        public ViewDataDto CaptureViewSnapshot()
        {
            if (workspaceController == null ||
                hmdCamera == null)
            {
                Debug.LogWarning(
                    "[POV] Cannot capture current snapshot: missing " +
                    "WorkspaceController or HMD Camera.",
                    this);
                return null;
            }

            // Capture the headset's actual mathematical view NOW.
            // No rolling window or recent-best selection.
            ViewDataDto snapshot = BuildCurrentViewSnapshot();
            if (snapshot == null)
                return null;

            snapshot.SnapshotSource = "current";

            // BackendClient computes age at the actual HTTP send time.
            snapshot.SnapshotAgeMs = null;

            Debug.Log(
                $"[POV] Captured current view. " +
                $"timestamp={snapshot.TimestampMs}, " +
                $"regions={snapshot.Regions?.Length ?? 0}, " +
                $"attemptId={snapshot.AttemptId}",
                this);

            return snapshot;
        }


        // ============================================================
        // BUILD STRUCTURED POV SNAPSHOT
        // ============================================================

        private ViewDataDto BuildCurrentViewSnapshot()
        {
            if (workspaceController == null ||
                hmdCamera == null)
            {
                return null;
            }

            if (string.IsNullOrWhiteSpace(
                    attemptId))
            {
                StartNewAttemptIdentity();
            }

            List<RegionViewDto> regionViews =
                new List<RegionViewDto>();

            foreach (WorkspaceRegion region
                     in workspaceController.ActiveRegions)
            {
                if (region == null)
                    continue;

                Collider regionCollider =
                    region.GetComponent<Collider>();

                if (regionCollider == null)
                    continue;

                string regionId =
                    GetStableRegionId(region);

                VisibilityResult regionResult =
                    CalculateRegionVisibility(
                        region,
                        regionCollider);

                LabelVisibilityResult labelResult =
                    CalculateLabelVisibility(
                        region);

                bool labelVisible =
                    labelResult.visibleFraction >=
                    labelVisibilityThreshold;

                if (labelVisible)
                {
                    labelsSeenThisAttempt.Add(
                        regionId);
                }

                bool labelSeen =
                    labelsSeenThisAttempt.Contains(
                        regionId);

                regionViews.Add(
                    new RegionViewDto
                    {
                        RegionId =
                            regionId,

                        VisibleFraction =
                            regionResult.visibleFraction,

                        LabelVisible =
                            labelVisible,

                        LabelSeenThisAttempt =
                            labelSeen
                    });
            }

            Vector3 headPosition =
                hmdCamera.transform.position;

            Vector3 headForward =
                hmdCamera.transform.forward;

            float verticalFov =
                hmdCamera.fieldOfView;

            float horizontalFov =
                CalculateHorizontalFov(
                    verticalFov,
                    hmdCamera.aspect);

            return new ViewDataDto
            {
                TimestampMs =
                    DateTimeOffset.UtcNow
                        .ToUnixTimeMilliseconds(),

                GazeTarget =
                    null,

                HeadPosition =
                    ToArray(
                        headPosition),

                HeadForward =
                    ToArray(
                        headForward),

                FovDeg =
                    new[]
                    {
                        horizontalFov,
                        verticalFov
                    },

                Regions =
                    regionViews.ToArray(),

                LastTouchedRegionId =
                    null,

                AttemptId =
                    attemptId
            };
        }


        // ============================================================
        // DEBUG OUTPUT
        // ============================================================

        [ContextMenu("Print POV Visibility")]
        public void PrintVisibility()
        {
            if (workspaceController == null)
            {
                Debug.LogWarning(
                    "[POV] WorkspaceController is not assigned.",
                    this);

                return;
            }

            if (hmdCamera == null)
            {
                Debug.LogWarning(
                    "[POV] HMD Camera is not assigned.",
                    this);

                return;
            }

            StringBuilder message =
                new StringBuilder();

            message.AppendLine(
                "[POV] HMD visibility snapshot");

            message.AppendLine(
                $"Head position: " +
                $"{hmdCamera.transform.position}");

            message.AppendLine(
                $"Head forward: " +
                $"{hmdCamera.transform.forward}");

            message.AppendLine(
                $"Attempt ID: {attemptId}");

            foreach (WorkspaceRegion region
                     in workspaceController.ActiveRegions)
            {
                if (region == null)
                    continue;

                Collider regionCollider =
                    region.GetComponent<Collider>();

                if (regionCollider == null)
                {
                    message.AppendLine(
                        $"  • {region.name} | NO COLLIDER");

                    continue;
                }

                string regionId =
                    GetStableRegionId(region);

                VisibilityResult regionResult =
                    CalculateRegionVisibility(
                        region,
                        regionCollider);

                LabelVisibilityResult labelResult =
                    CalculateLabelVisibility(
                        region);

                bool labelVisible =
                    labelResult.visibleFraction >=
                    labelVisibilityThreshold;

                if (labelVisible)
                {
                    labelsSeenThisAttempt.Add(
                        regionId);
                }

                bool labelSeen =
                    labelsSeenThisAttempt.Contains(
                        regionId);

                string status;

                if (regionResult.visibleFraction <= 0f)
                {
                    status =
                        "NOT VISIBLE";
                }
                else if (
                    regionResult.visibleFraction < 0.5f)
                {
                    status =
                        "PARTIALLY VISIBLE";
                }
                else
                {
                    status =
                        "VISIBLE";
                }

                message.AppendLine(
                    $"  • {region.name}" +
                    $" | id={regionId}" +
                    $" | inFOV={regionResult.fovFraction:F2}" +
                    $" | visible={regionResult.visibleFraction:F2}" +
                    $" | occluded={regionResult.occludedSamples}" +
                    $" | labelFraction={labelResult.visibleFraction:F2}" +
                    $" | labelVisible={labelVisible.ToString().ToLowerInvariant()}" +
                    $" | labelSeen={labelSeen.ToString().ToLowerInvariant()}" +
                    $" | {status}");
            }

            Debug.Log(
                message.ToString(),
                this);
        }


        // ============================================================
        // STABLE REGION IDS
        // ============================================================

        private string GetStableRegionId(
            WorkspaceRegion region)
        {
            string regionName =
                region.name ?? "";

            if (regionName.StartsWith(
                    "Group_",
                    StringComparison.OrdinalIgnoreCase))
            {
                string suffix =
                    regionName.Substring(
                        "Group_".Length);

                return
                    $"group_{suffix}"
                        .ToLowerInvariant();
            }

            if (regionName.StartsWith(
                    "Recipient_",
                    StringComparison.OrdinalIgnoreCase))
            {
                string suffix =
                    regionName.Substring(
                        "Recipient_".Length);

                return
                    $"recipient_{suffix}"
                        .ToLowerInvariant();
            }

            switch (regionName)
            {
                // JOIN
                case "JoinCombinedCollection":
                    return "destination";

                case "JoinPartA":
                    return "part_a";

                case "JoinPartB":
                    return "part_b";

                case "JoinStartingCollection":
                    return "part_a";

                case "JoinAvailableObjects":
                    return "bank";


                // REMOVE
                case "StartingCollection":
                    return "start";

                case "Removed":
                    return "removed";


                // EQUAL SHARING
                case "SharingObjectBank":
                    return "bank";


                // PART-TO-PART RATIO
                case "RatioTargetA":
                    return "part_a";

                case "RatioTargetB":
                    return "part_b";

                case "RatioBankA":
                    return "bank_a";

                case "RatioBankB":
                    return "bank_b";


                default:
                    return NormalizeRegionName(
                        regionName);
            }
        }


        private string NormalizeRegionName(
            string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "unknown_region";

            StringBuilder builder =
                new StringBuilder();

            for (int index = 0;
                 index < value.Length;
                 index++)
            {
                char current =
                    value[index];

                if (char.IsUpper(current) &&
                    index > 0 &&
                    value[index - 1] != '_')
                {
                    builder.Append('_');
                }

                if (char.IsLetterOrDigit(current))
                {
                    builder.Append(
                        char.ToLowerInvariant(
                            current));
                }
                else
                {
                    builder.Append('_');
                }
            }

            return builder
                .ToString()
                .Trim('_');
        }


        // ============================================================
        // CAMERA / FOV
        // ============================================================

        private float[] ToArray(
            Vector3 value)
        {
            return new[]
            {
                value.x,
                value.y,
                value.z
            };
        }


        private float CalculateHorizontalFov(
            float verticalFovDegrees,
            float aspect)
        {
            float verticalRadians =
                verticalFovDegrees *
                Mathf.Deg2Rad;

            float horizontalRadians =
                2f *
                Mathf.Atan(
                    Mathf.Tan(
                        verticalRadians * 0.5f) *
                    Mathf.Max(
                        0.01f,
                        aspect));

            return
                horizontalRadians *
                Mathf.Rad2Deg;
        }


        // ============================================================
        // REGION VISIBILITY
        // ============================================================

        private VisibilityResult
            CalculateRegionVisibility(
                WorkspaceRegion region,
                Collider regionCollider)
        {
            Vector3[] samplePoints =
                GetRegionSamplePoints(
                    regionCollider);

            int inFovSamples = 0;
            int visibleSamples = 0;
            int occludedSamples = 0;

            foreach (Vector3 samplePoint
                     in samplePoints)
            {
                if (!IsInsideCameraView(
                        samplePoint))
                {
                    continue;
                }

                inFovSamples++;

                if (HasRegionLineOfSight(
                        region,
                        regionCollider,
                        samplePoint))
                {
                    visibleSamples++;
                }
                else
                {
                    occludedSamples++;
                }
            }

            int totalSamples =
                samplePoints.Length;

            VisibilityResult result =
                new VisibilityResult();

            result.fovFraction =
                totalSamples > 0
                    ? (float)inFovSamples /
                      totalSamples
                    : 0f;

            result.visibleFraction =
                totalSamples > 0
                    ? (float)visibleSamples /
                      totalSamples
                    : 0f;

            result.occludedSamples =
                occludedSamples;

            return result;
        }


        // ============================================================
        // LABEL VISIBILITY
        // ============================================================

        private LabelVisibilityResult
            CalculateLabelVisibility(
                WorkspaceRegion region)
        {
            LabelVisibilityResult result =
                new LabelVisibilityResult();

            WorkspaceRegionView regionView =
                region.View;

            if (regionView == null ||
                regionView.TitleText == null ||
                !regionView.TitleText.enabled ||
                !regionView.TitleText
                    .gameObject.activeInHierarchy)
            {
                return result;
            }

            RectTransform rectTransform =
                regionView.TitleText.rectTransform;

            if (rectTransform == null)
                return result;

            Vector3[] corners =
                new Vector3[4];

            rectTransform.GetWorldCorners(
                corners);

            Vector3 center =
                (corners[0] +
                 corners[1] +
                 corners[2] +
                 corners[3]) * 0.25f;

            Vector3[] samplePoints =
            {
                center,
                corners[0],
                corners[1],
                corners[2],
                corners[3]
            };

            int visibleSamples = 0;

            foreach (Vector3 samplePoint
                     in samplePoints)
            {
                if (!IsInsideCameraView(
                        samplePoint))
                {
                    continue;
                }

                if (HasLabelLineOfSight(
                        region,
                        samplePoint))
                {
                    visibleSamples++;
                }
            }

            result.visibleFraction =
                (float)visibleSamples /
                samplePoints.Length;

            return result;
        }


        // ============================================================
        // REGION SAMPLE POINTS
        // ============================================================

        private Vector3[] GetRegionSamplePoints(
            Collider regionCollider)
        {
            Bounds bounds =
                regionCollider.bounds;

            Vector3 min =
                bounds.min;

            Vector3 max =
                bounds.max;

            Vector3 center =
                bounds.center;

            float y =
                max.y;

            return new Vector3[]
            {
                new Vector3(
                    center.x,
                    y,
                    center.z),

                new Vector3(
                    min.x,
                    y,
                    min.z),

                new Vector3(
                    min.x,
                    y,
                    max.z),

                new Vector3(
                    max.x,
                    y,
                    min.z),

                new Vector3(
                    max.x,
                    y,
                    max.z),

                new Vector3(
                    center.x,
                    y,
                    min.z),

                new Vector3(
                    center.x,
                    y,
                    max.z),

                new Vector3(
                    min.x,
                    y,
                    center.z),

                new Vector3(
                    max.x,
                    y,
                    center.z)
            };
        }


        // ============================================================
        // VIEWPORT TEST
        // ============================================================

        private bool IsInsideCameraView(
            Vector3 worldPoint)
        {
            Vector3 viewportPoint =
                hmdCamera.WorldToViewportPoint(
                    worldPoint);

            return
                viewportPoint.z > 0f &&
                viewportPoint.x >= 0f &&
                viewportPoint.x <= 1f &&
                viewportPoint.y >= 0f &&
                viewportPoint.y <= 1f;
        }


        // ============================================================
        // REGION OCCLUSION
        // ============================================================

        private bool HasRegionLineOfSight(
            WorkspaceRegion region,
            Collider regionCollider,
            Vector3 samplePoint)
        {
            Vector3 origin =
                hmdCamera.transform.position;

            Vector3 direction =
                samplePoint - origin;

            float distance =
                direction.magnitude;

            if (distance <= 0.001f)
                return true;

            direction.Normalize();

            RaycastHit[] hits =
                Physics.RaycastAll(
                    origin,
                    direction,
                    distance +
                    raycastTolerance,
                    occlusionMask,
                    QueryTriggerInteraction.Ignore);

            if (hits == null ||
                hits.Length == 0)
            {
                return true;
            }

            Array.Sort(
                hits,
                (a, b) =>
                    a.distance.CompareTo(
                        b.distance));

            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null)
                    continue;

                if (hit.collider ==
                    regionCollider)
                {
                    return true;
                }

                if (hit.transform != null &&
                    hit.transform.IsChildOf(
                        region.transform))
                {
                    return true;
                }

                return false;
            }

            return true;
        }


        // ============================================================
        // LABEL OCCLUSION
        // ============================================================

        private bool HasLabelLineOfSight(
            WorkspaceRegion region,
            Vector3 samplePoint)
        {
            Vector3 origin =
                hmdCamera.transform.position;

            Vector3 direction =
                samplePoint - origin;

            float distance =
                direction.magnitude;

            if (distance <= 0.001f)
                return true;

            direction.Normalize();

            RaycastHit[] hits =
                Physics.RaycastAll(
                    origin,
                    direction,
                    Mathf.Max(
                        0f,
                        distance -
                        raycastTolerance),
                    occlusionMask,
                    QueryTriggerInteraction.Ignore);

            if (hits == null ||
                hits.Length == 0)
            {
                return true;
            }

            Array.Sort(
                hits,
                (a, b) =>
                    a.distance.CompareTo(
                        b.distance));

            foreach (RaycastHit hit in hits)
            {
                if (hit.collider == null)
                    continue;

                if (hit.transform ==
                    region.transform)
                {
                    continue;
                }

                if (hit.transform.IsChildOf(
                        region.transform))
                {
                    continue;
                }

                return false;
            }

            return true;
        }


        // ============================================================
        // RESULTS
        // ============================================================

        private struct VisibilityResult
        {
            public float fovFraction;

            public float visibleFraction;

            public int occludedSamples;
        }


        private struct LabelVisibilityResult
        {
            public float visibleFraction;
        }
    }
}