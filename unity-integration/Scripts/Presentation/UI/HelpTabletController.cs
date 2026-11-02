
using System;
using System.Collections.Generic;
using MathConstructVR.Core;
using MathConstructVR.Networking.DTOs;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.XR;

namespace MathConstructVR.Presentation.UI
{
    public sealed class HelpTabletController : MonoBehaviour
    {
        [Header("Application")]
        [SerializeField] private ExperienceController experienceController;
        [SerializeField] private SessionController sessionController;
        [SerializeField] private WorkspaceController workspaceController;
        [SerializeField] private WorkspacePovDebug workspacePovDebug;

        [Header("Tablet")]
        [SerializeField] private GameObject tabletModel;
        [SerializeField] private Renderer tabletGlassRenderer;
        [SerializeField] private Canvas tabletScreenCanvas;

        [Header("Typography")]
        [SerializeField] private TMP_FontAsset titleFont;
        [SerializeField] private TMP_FontAsset bodyFont;

        [Header("Screen Alignment")]
        [SerializeField] private Vector3 screenRotationEuler =
            new Vector3(-90f, 0f, 0f);

        [Header("Headset X Tracking")]
        [SerializeField] private Camera hmdCamera;

        private const float TabletLeftX = 0.1695f;
        private const float TabletRightX = -0.2631f;

        private InputDevice rightController;
        private bool previousButtonPressed;
        private bool tabletOpen;
        private bool originalGlassRendererEnabled;

        private ViewDataDto capturedView;
        private JToken capturedLearnerState;
        private string capturedQuestionId;
        private string capturedStateSignature;

        private readonly List<string> capturedRegionTitles =
            new List<string>();

        private readonly List<int> capturedRegionCounts =
            new List<int>();

        private RectTransform previewRoot;

        public bool IsOpen => tabletOpen;
        public ViewDataDto CapturedView => capturedView;

        private void Awake()
        {
            if (tabletGlassRenderer != null)
            {
                originalGlassRendererEnabled =
                    tabletGlassRenderer.enabled;
            }

            if (tabletScreenCanvas != null)
            {
                ConfigureScreenCanvas();
                tabletScreenCanvas.gameObject.SetActive(false);
            }

            if (tabletModel != null)
                tabletModel.SetActive(false);
        }

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

            if (tabletOpen)
                CloseTablet();
        }

        private void Update()
        {
            AlignTabletXToCamera();
            if (!rightController.isValid)
            {
                rightController =
                    InputDevices.GetDeviceAtXRNode(
                        XRNode.RightHand);

                previousButtonPressed = false;
            }

            if (!rightController.isValid)
                return;

            if (!rightController.TryGetFeatureValue(
                CommonUsages.secondaryButton,
                out bool pressed))
            {
                previousButtonPressed = false;
                return;
            }

            if (pressed && !previousButtonPressed)
                ToggleTablet();

            previousButtonPressed = pressed;
        }

        [ContextMenu("Toggle Tablet (Play Mode Test)")]
        public void ToggleTablet()
        {
            if (experienceController == null ||
                experienceController.CurrentState !=
                    ExperienceState.Attempt)
            {
                Debug.Log(
                    "[HelpTablet] Available only during Attempt.",
                    this);
                return;
            }

            if (tabletOpen)
                CloseTablet();
            else
                OpenTablet();
        }

        private void OpenTablet()
        {
            if (tabletModel == null ||
                workspacePovDebug == null ||
                workspaceController == null ||
                sessionController == null)
            {
                Debug.LogWarning(
                    "[HelpTablet] Missing required references.",
                    this);
                return;
            }

            if (!CaptureCurrentTutorView())
                return;

            tabletModel.SetActive(true);
            AlignTabletXToCamera();
            DrawTutorView();

            if (tabletScreenCanvas != null)
                tabletScreenCanvas.gameObject.SetActive(true);

            tabletOpen = true;

            Debug.Log(
                "[HelpTablet] Opened. " +
                $"timestamp={capturedView.TimestampMs}, " +
                $"regions={capturedView.Regions?.Length ?? 0}",
                this);
        }

        private void AlignTabletXToCamera()
        {
            if (hmdCamera == null)
                return;

            const float minX = -1.083f; // Far right
            const float maxX =  0.212f; // Far left

            Transform parent = transform.parent;

            // Plane through the tablet, using its parent's Z axis.
            Vector3 normal = parent != null
                ? parent.TransformDirection(Vector3.forward)
                : Vector3.forward;

            Plane tabletPlane = new Plane(normal, transform.position);

            Ray gaze = new Ray(
                hmdCamera.transform.position,
                hmdCamera.transform.forward);

            if (!tabletPlane.Raycast(gaze, out float distance))
                return;

            Vector3 lookPoint = gaze.GetPoint(distance);

            // Convert gaze to the SAME coordinates as the Inspector.
            float targetX = parent != null
                ? parent.InverseTransformPoint(lookPoint).x
                : lookPoint.x;

            Vector3 position = transform.localPosition;

            position.x = Mathf.Clamp(targetX, minX, maxX);

            transform.localPosition = position;
        }

        private bool CaptureCurrentTutorView()
        {
            if (sessionController == null ||
                workspaceController == null ||
                workspacePovDebug == null ||
                sessionController.CurrentQuestion == null)
            {
                return false;
            }

            if (!workspaceController.TryGetLearnerState(
                out object learnerState))
            {
                Debug.LogWarning(
                    "[HelpTablet] Learner state unavailable.",
                    this);
                return false;
            }

            ViewDataDto view =
                workspacePovDebug.CaptureViewSnapshot();

            if (view == null)
            {
                Debug.LogWarning(
                    "[HelpTablet] POV capture failed.",
                    this);
                return false;
            }

            capturedLearnerState =
                JToken.Parse(
                    JsonConvert.SerializeObject(learnerState));

            capturedView = view;

            capturedQuestionId =
                sessionController.CurrentQuestion.Id;

            capturedStateSignature =
                workspaceController.GetStateSignature();

            capturedRegionTitles.Clear();
            capturedRegionCounts.Clear();

            foreach (WorkspaceRegion region
                     in workspaceController.ActiveRegions)
            {
                if (region == null ||
                    region.GetComponent<Collider>() == null)
                {
                    continue;
                }

                string title =
                    region.View != null &&
                    region.View.TitleText != null
                        ? region.View.TitleText.text
                        : null;

                capturedRegionTitles.Add(title);

                capturedRegionCounts.Add(
                    region.OccupantCount);
            }

            return true;
        }

        public void RefreshCapture()
        {
            if (!tabletOpen)
                return;

            if (tabletScreenCanvas != null)
                tabletScreenCanvas.gameObject.SetActive(false);

            if (tabletModel != null)
                tabletModel.SetActive(false);

            bool success = CaptureCurrentTutorView();

            if (tabletModel != null)
                tabletModel.SetActive(true);

            if (success)
                DrawTutorView();

            if (tabletScreenCanvas != null)
                tabletScreenCanvas.gameObject.SetActive(true);

            Debug.Log(
                success
                    ? "[HelpTablet] Tutor View refreshed."
                    : "[HelpTablet] Refresh failed.",
                this);
        }

        public bool TryGetFrozenCapture(
            out string questionId,
            out object learnerState,
            out string stateSignature,
            out ViewDataDto view)
        {
            questionId = capturedQuestionId;
            learnerState = capturedLearnerState;
            stateSignature = capturedStateSignature;
            view = capturedView;

            return tabletOpen &&
                   view != null &&
                   learnerState != null &&
                   !string.IsNullOrEmpty(questionId);
        }

        public bool IsCaptureStillValid()
        {
            return
                tabletOpen &&
                capturedView != null &&
                sessionController != null &&
                workspaceController != null &&
                sessionController.CurrentQuestion != null &&
                sessionController.CurrentQuestion.Id ==
                    capturedQuestionId &&
                workspaceController.GetStateSignature() ==
                    capturedStateSignature;
        }

        private void CloseTablet()
        {
            if (tabletScreenCanvas != null)
                tabletScreenCanvas.gameObject.SetActive(false);

            if (tabletModel != null)
                tabletModel.SetActive(false);

            tabletOpen = false;

            capturedView = null;
            capturedLearnerState = null;
            capturedQuestionId = null;
            capturedStateSignature = null;

            capturedRegionTitles.Clear();
            capturedRegionCounts.Clear();

            Debug.Log("[HelpTablet] Closed.", this);
        }

        private void HandleExperienceStateChanged(
            ExperienceState state)
        {
            if (state != ExperienceState.Attempt &&
                tabletOpen)
            {
                CloseTablet();
            }
        }

        private void HandleQuestionChanged(
            QuestionDto question)
        {
            if (tabletOpen)
                CloseTablet();
        }

        private void ConfigureScreenCanvas()
        {
            if (tabletGlassRenderer == null ||
                tabletScreenCanvas == null)
            {
                return;
            }

            MeshFilter meshFilter =
                tabletGlassRenderer.GetComponent<MeshFilter>();

            if (meshFilter == null ||
                meshFilter.sharedMesh == null)
            {
                Debug.LogWarning(
                    "[HelpTablet] Glass mesh unavailable.",
                    this);
                return;
            }

            Bounds bounds = meshFilter.sharedMesh.bounds;

            RectTransform rect =
                tabletScreenCanvas.GetComponent<RectTransform>();

            rect.SetParent(
                tabletGlassRenderer.transform,
                false);

            rect.localPosition =
                new Vector3(
                    bounds.center.x,
                    bounds.max.y + 0.002f,
                    bounds.center.z);

            rect.localRotation =
                Quaternion.Euler(screenRotationEuler);

            rect.anchorMin = new Vector2(0.5f, 0.5f);
            rect.anchorMax = new Vector2(0.5f, 0.5f);
            rect.pivot = new Vector2(0.5f, 0.5f);

            rect.sizeDelta =
                new Vector2(1000f, 680f);

            rect.localScale =
                new Vector3(
                    bounds.size.x * 0.90f / 1000f,
                    bounds.size.z * 0.88f / 680f,
                    1f);

            tabletScreenCanvas.renderMode =
                RenderMode.WorldSpace;

            tabletGlassRenderer.enabled = false;
        }

        // ============================================================
        // WHAT THE TUTOR RECEIVES
        // ============================================================

        private void DrawTutorView()
        {
            if (tabletScreenCanvas == null)
                return;

            if (previewRoot != null)
            {
                previewRoot.gameObject.SetActive(false);
                Destroy(previewRoot.gameObject);
                previewRoot = null;
            }

            previewRoot =
                CreatePanel(
                    "TutorView",
                    tabletScreenCanvas.transform,
                    Vector2.zero,
                    new Vector2(960f, 640f),
                    new Color(0.075f, 0.105f, 0.17f, 1f));

            previewRoot.SetAsFirstSibling();

            // Keep the heading; remove the explanatory subtitle.
            CreateText(
                previewRoot,
                "What the Tutor Receives",
                new Vector2(0f, 268f),
                new Vector2(900f, 76f),
                65f,
                Color.white,
                true);

            RegionViewDto[] regions =
                capturedView?.Regions ??
                Array.Empty<RegionViewDto>();

            CreateText(
                previewRoot,
                $"{regions.Length} workspace regions",
                new Vector2(0f, 201f),
                new Vector2(850f, 35f),
                25f,
                new Color(0.65f, 0.77f, 0.88f),
                false);

            int count = Mathf.Min(regions.Length, 9);

            if (count == 0)
            {
                CreateText(
                    previewRoot,
                    "No workspace regions yet",
                    new Vector2(0f, 0f),
                    new Vector2(820f, 100f),
                    43f,
                    Color.white,
                    true);
                return;
            }

            int columns = count <= 4 ? 2 : 3;

            int rows = Mathf.CeilToInt(
                (float)count / columns);

            float cardWidth =
                columns == 2 ? 404f : 288f;

            float cardHeight =
                rows == 3 ? 116f : 154f;

            float columnSpacing =
                columns == 2 ? 438f : 305f;

            float rowSpacing =
                rows == 3 ? 130f : 170f;

            float firstRowY =
                rows == 1 ? 10f :
                rows == 2 ? 70f : 105f;

            for (int i = 0; i < count; i++)
            {
                RegionViewDto region = regions[i];

                if (region == null)
                    continue;

                int column = i % columns;
                int row = i / columns;

                Vector2 position =
                    new Vector2(
                        (column - (columns - 1) * 0.5f)
                            * columnSpacing,
                        firstRowY - row * rowSpacing);

                string displayTitle =
                    i < capturedRegionTitles.Count
                        ? capturedRegionTitles[i]
                        : null;

                int objectCount =
                    i < capturedRegionCounts.Count
                        ? capturedRegionCounts[i]
                        : 0;

                DrawRegionCard(
                    region,
                    position,
                    displayTitle,
                    objectCount,
                    cardWidth,
                    cardHeight,
                    rows == 3);
            }

            if (regions.Length > 9)
            {
                CreateText(
                    previewRoot,
                    $"Showing 9 of {regions.Length} regions",
                    new Vector2(0f, -257f),
                    new Vector2(680f, 36f),
                    23f,
                    Color.white,
                    false);
            }
        }

        // ============================================================
        // REGION CARD — LEFT-ALIGNED CONTENT
        // ============================================================

        private void DrawRegionCard(
            RegionViewDto region,
            Vector2 position,
            string displayTitle,
            int objectCount,
            float width,
            float height,
            bool compact)
        {
            float fraction =
                Mathf.Clamp01(
                    region.VisibleFraction ?? 0f);

            string status =
                fraction >= 0.5f
                    ? "Visible"
                    : fraction > 0f
                        ? "Partly visible"
                        : "Not visible";

            Color accent =
                fraction >= 0.5f
                    ? new Color(0.30f, 0.78f, 0.63f)
                    : fraction > 0f
                        ? new Color(0.96f, 0.72f, 0.35f)
                        : new Color(0.58f, 0.63f, 0.73f);

            RectTransform card =
                CreatePanel(
                    "Region_" + region.RegionId,
                    previewRoot,
                    position,
                    new Vector2(width, height),
                    new Color(0.15f, 0.20f, 0.29f, 1f));

            string semanticId =
                region.RegionId ?? "unknown_region";

            string title =
                !string.IsNullOrWhiteSpace(displayTitle)
                    ? displayTitle
                    : semanticId.Replace("_", " ");

            const float padding = 18f;

            float textWidth = width - 2f * padding;

            float leftTextCenterX = 0f;

            float titleY = compact ? 33f : 50f;
            float badgeWidth = compact ? 90f : 110f;

            float titleWidth =
                width - badgeWidth - 3f * padding - 4f;

            float titleCenterX =
                -width * 0.5f +
                padding +
                titleWidth * 0.5f;

            // Region title: left aligned.
            CreateText(
                card,
                title,
                new Vector2(-badgeWidth * 0.5f, titleY),
                new Vector2(
                    width - badgeWidth - 30f,
                    compact ? 44f : 54f),
                compact ? 35f : 44f,
                Color.white,
                true,
                true);

            // Object count: top right.
            RectTransform countBadge =
                CreatePanel(
                    "ObjectCountBadge",
                    card,
                    new Vector2(
                        width * 0.5f -
                        padding -
                        badgeWidth * 0.5f,
                        titleY),
                    new Vector2(
                        badgeWidth,
                        compact ? 29f : 32f),
                    new Color(0.27f, 0.34f, 0.44f, 1f));

            string countText =
                objectCount == 1
                    ? "1 object"
                    : $"{objectCount} objects";

            CreateText(
                countBadge,
                countText,
                Vector2.zero,
                new Vector2(
                    badgeWidth - 8f,
                    compact ? 26f : 29f),
                compact ? 21f : 25f,
                Color.white,
                false);

            // Stable region ID: same left edge as title.
            CreateText(
                card,
                semanticId,
                new Vector2(
                    leftTextCenterX,
                    compact ? 4f : 18f),
                new Vector2(
                    textWidth,
                    compact ? 19f : 28f),
                compact ? 21f : 25f,
                new Color(0.67f, 0.77f, 0.88f),
                false,
                true);

            // Visibility: same left edge.
            CreateText(
                card,
                $"{status} · {fraction:P0}",
                new Vector2(
                    leftTextCenterX,
                    compact ? -20f : -18f),
                new Vector2(
                    textWidth,
                    compact ? 24f : 32f),
                compact ? 23f : 28f,
                accent,
                false,
                true);

            // Visibility bar: starts at that same left edge.
            float trackWidth = textWidth;
            float trackY = compact ? -45f : -57f;

            CreatePanel(
                "VisibilityTrack",
                card,
                new Vector2(0f, trackY),
                new Vector2(trackWidth, 12f),
                new Color(0.28f, 0.33f, 0.42f));

            if (fraction > 0f)
            {
                CreatePanel(
                    "VisibilityFill",
                    card,
                    new Vector2(
                        -trackWidth * 0.5f +
                        trackWidth * fraction * 0.5f,
                        trackY),
                    new Vector2(
                        trackWidth * fraction,
                        12f),
                    accent);
            }
        }

        private RectTransform CreatePanel(
            string objectName,
            Transform parent,
            Vector2 position,
            Vector2 size,
            Color color)
        {
            GameObject go =
                new GameObject(
                    objectName,
                    typeof(RectTransform),
                    typeof(Image));

            go.transform.SetParent(parent, false);

            RectTransform rect =
                go.GetComponent<RectTransform>();

            rect.anchorMin = new Vector2(0.5f, 0.5f);
            rect.anchorMax = new Vector2(0.5f, 0.5f);
            rect.pivot = new Vector2(0.5f, 0.5f);

            rect.sizeDelta = size;
            rect.anchoredPosition = position;

            Image image = go.GetComponent<Image>();
            image.color = color;
            image.raycastTarget = false;

            return rect;
        }

        private void CreateText(
            Transform parent,
            string value,
            Vector2 position,
            Vector2 size,
            float fontSize,
            Color color,
            bool isTitle,
            bool leftAligned = false)
        {
            GameObject go =
                new GameObject(
                    "Label",
                    typeof(RectTransform),
                    typeof(TextMeshProUGUI));

            go.transform.SetParent(parent, false);

            RectTransform rect =
                go.GetComponent<RectTransform>();

            rect.anchorMin = new Vector2(0.5f, 0.5f);
            rect.anchorMax = new Vector2(0.5f, 0.5f);
            rect.pivot = new Vector2(0.5f, 0.5f);

            rect.sizeDelta = size;
            rect.anchoredPosition = position;

            TextMeshProUGUI text =
                go.GetComponent<TextMeshProUGUI>();

            TMP_FontAsset selectedFont =
                isTitle ? titleFont : bodyFont;

            if (selectedFont != null)
                text.font = selectedFont;

            text.text = value;
            text.fontSize = fontSize;
            text.fontSizeMax = fontSize;
            text.fontSizeMin =
                Mathf.Max(14f, fontSize * 0.72f);

            text.enableAutoSizing = true;
            text.enableWordWrapping = false;
            text.overflowMode =
                TextOverflowModes.Ellipsis;

            text.color = color;

            text.alignment = leftAligned
                ? TextAlignmentOptions.MidlineLeft
                : TextAlignmentOptions.Center;

            text.margin =
                new Vector4(2f, 3f, 2f, 3f);

            text.raycastTarget = false;
        }

        private void OnDestroy()
        {
            if (tabletGlassRenderer != null)
            {
                tabletGlassRenderer.enabled =
                    originalGlassRendererEnabled;
            }
        }
    }
}
