using TMPro;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class WorkspaceRegionView : MonoBehaviour
    {
        [Header("Authored Children")]
        [SerializeField]
        private LineRenderer border;

        [SerializeField]
        private TMP_Text titleText;

        [SerializeField]
        private Transform removalBackground;

        [SerializeField]
        private MeshRenderer removalBackgroundRenderer;

        [Header("Materials")]
        [SerializeField]
        private Material neutralBorderMaterial;

        [SerializeField]
        private Material removalBorderMaterial;

        [SerializeField]
        private Material removalBackgroundMaterial;

        [Header("Geometry")]
        [Min(0f)]
        [SerializeField]
        private float borderHeight = 0.006f;

        [Min(0f)]
        [SerializeField]
        private float backgroundHeight = 0.0015f;

        [Min(0.0001f)]
        [SerializeField]
        private float backgroundThickness = 0.002f;

        [Min(0f)]
        [SerializeField]
        private float titleHeight = 0.004f;

        [Min(0f)]
        [SerializeField]
        private float titleOutsideOffset = 0.09f;

        [SerializeField]
        private bool titleOnPositiveZEdge = false;

        [Range(0.3f, 1f)]
        [SerializeField]
        private float titleWidthFraction = 0.9f;

        private Vector2 configuredSize;
        private bool hasConfiguredSize;

        private float authoredTitleFontSizeMin;
        private float authoredTitleFontSizeMax;
        private bool hasCachedTitleFontRange;

        private const float TitleFontScale = 0.7f;

        public TMP_Text TitleText => titleText;


        private void CacheAuthoredTitleFontRange()
        {
            if (hasCachedTitleFontRange ||
                titleText == null)
            {
                return;
            }

            authoredTitleFontSizeMin =
                titleText.fontSizeMin;

            authoredTitleFontSizeMax =
                titleText.fontSizeMax;

            hasCachedTitleFontRange = true;
        }


        public void SetTitleOnPositiveZEdge(
            bool value)
        {
            if (titleOnPositiveZEdge == value)
                return;

            titleOnPositiveZEdge = value;

            // The edge can be chosen after the region has already been
            // configured. Apply the new edge immediately instead of requiring
            // an unrelated Reflow() call just to move the title.
            if (hasConfiguredSize &&
                titleText != null)
            {
                ConfigureTitle(
                    configuredSize,
                    titleText.text);
            }
        }


        public void Configure(
            Vector2 size,
            string title,
            WorkspaceRegionStyle style)
        {
            configuredSize = size;
            hasConfiguredSize = true;

            ConfigureBorder(size, style);
            ConfigureBackground(size, style);
            ConfigureTitle(size, title);
        }


        private void ConfigureBorder(
            Vector2 size,
            WorkspaceRegionStyle style)
        {
            if (border == null)
            {
                Debug.LogError(
                    "[MathConstructVR] WorkspaceRegionView has no Border LineRenderer assigned.",
                    this);

                return;
            }

            float halfWidth = size.x * 0.5f;
            float halfDepth = size.y * 0.5f;

            border.useWorldSpace = false;
            border.loop = true;
            border.positionCount = 4;

            border.SetPosition(
                0,
                new Vector3(
                    -halfWidth,
                    borderHeight,
                    halfDepth));

            border.SetPosition(
                1,
                new Vector3(
                    halfWidth,
                    borderHeight,
                    halfDepth));

            border.SetPosition(
                2,
                new Vector3(
                    halfWidth,
                    borderHeight,
                    -halfDepth));

            border.SetPosition(
                3,
                new Vector3(
                    -halfWidth,
                    borderHeight,
                    -halfDepth));

            Material material =
                style == WorkspaceRegionStyle.Removal
                    ? removalBorderMaterial
                    : neutralBorderMaterial;

            if (material != null)
            {
                border.sharedMaterial =
                    material;
            }
        }


        private void ConfigureBackground(
            Vector2 size,
            WorkspaceRegionStyle style)
        {
            if (removalBackground == null)
                return;

            bool visible =
                style == WorkspaceRegionStyle.Removal;

            removalBackground.gameObject.SetActive(
                visible);

            if (!visible)
                return;

            removalBackground.localPosition =
                new Vector3(
                    0f,
                    backgroundHeight,
                    0f);

            removalBackground.localScale =
                new Vector3(
                    size.x,
                    backgroundThickness,
                    size.y);

            if (removalBackgroundRenderer != null &&
                removalBackgroundMaterial != null)
            {
                removalBackgroundRenderer.sharedMaterial =
                    removalBackgroundMaterial;
            }
        }


        private void ConfigureTitle(
            Vector2 size,
            string title)
        {
            if (titleText == null)
            {
                Debug.LogError(
                    "[MathConstructVR] WorkspaceRegionView has no authored TMP title assigned.",
                    this);

                return;
            }

            titleText.text =
                title ?? "";

            Transform titleTransform =
                titleText.transform;

            float titleZ =
                (size.y * 0.5f) +
                titleOutsideOffset;

            if (!titleOnPositiveZEdge)
            {
                titleZ = -titleZ;
            }

            titleTransform.localPosition =
                new Vector3(
                    0f,
                    titleHeight,
                    titleZ);

            RectTransform rectTransform =
                titleText.rectTransform;

            if (rectTransform == null)
                return;

            /*
             * Region size is measured in workspace-local metres.
             *
             * 3D TMP objects are normally authored with a small transform
             * scale (for example 0.01). RectTransform.sizeDelta, however,
             * is expressed in the TMP object's own local units.
             *
             * Convert the desired physical width into TMP-local units
             * instead of assigning metres directly to sizeDelta.
             */
            float localScaleX =
                Mathf.Abs(
                    titleTransform.localScale.x);

            if (localScaleX < 0.0001f)
            {
                localScaleX =
                    1f;
            }

            float desiredWorldWidth =
                size.x *
                titleWidthFraction;

            float desiredLocalWidth =
                desiredWorldWidth /
                localScaleX;

            Vector2 currentSize =
                rectTransform.sizeDelta;

            currentSize.x =
                Mathf.Max(
                    1f,
                    desiredLocalWidth);

            rectTransform.sizeDelta =
                currentSize;

            CacheAuthoredTitleFontRange();

            // Keep each title on one line. Auto-sizing is allowed to shrink
            // longer names to fit, but words are never split across lines.
            titleText.textWrappingMode =
                TextWrappingModes.NoWrap;

            titleText.overflowMode =
                TextOverflowModes.Truncate;

            // Preserve TMP auto-sizing, but use half of the authored font-size
            // range so short labels do not grow unnecessarily large.
            if (hasCachedTitleFontRange)
            {
                titleText.fontSizeMin =
                    authoredTitleFontSizeMin *
                    TitleFontScale;

                titleText.fontSizeMax =
                    authoredTitleFontSizeMax *
                    TitleFontScale;
            }

            titleText.enableAutoSizing =
                true;
        }
    }
}