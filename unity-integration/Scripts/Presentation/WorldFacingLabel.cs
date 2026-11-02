using TMPro;
using UnityEngine;

namespace MathConstructVR.Presentation
{
    public sealed class WorldFacingLabel : MonoBehaviour
    {
        private const float CanvasPixelWidth =
            600f;

        private const float CanvasPixelHeight =
            100f;


        private RectTransform canvasRect;

        private TextMeshProUGUI labelText;

        private Color baseColor =
            new Color(
                0.08f,
                0.08f,
                0.08f,
                1f);


        public void Configure(
            string text,
            Vector2 worldSize,
            float fontSize = 36f)
        {
            EnsureCreated();


            canvasRect.sizeDelta =
                new Vector2(
                    CanvasPixelWidth,
                    CanvasPixelHeight);


            canvasRect.localScale =
                new Vector3(
                    worldSize.x /
                    CanvasPixelWidth,

                    worldSize.y /
                    CanvasPixelHeight,

                    1f);


            labelText.fontSize =
                fontSize;

            labelText.text =
                text ?? "";

            labelText.color =
                baseColor;
        }


        public void SetText(
            string text)
        {
            EnsureCreated();

            labelText.text =
                text ?? "";
        }


        public void SetAlpha(
            float alpha)
        {
            EnsureCreated();

            Color color =
                baseColor;

            color.a =
                Mathf.Clamp01(
                    alpha);

            labelText.color =
                color;
        }


        private void EnsureCreated()
        {
            if (canvasRect != null &&
                labelText != null)
            {
                return;
            }


            GameObject canvasObject =
                new GameObject(
                    "Canvas",
                    typeof(RectTransform),
                    typeof(Canvas));


            canvasObject.transform.SetParent(
                transform,
                false);


            Canvas canvas =
                canvasObject.GetComponent<Canvas>();

            canvas.renderMode =
                RenderMode.WorldSpace;

            canvas.overrideSorting =
                true;

            canvas.sortingOrder =
                20;


            canvasRect =
                canvasObject.GetComponent<
                    RectTransform>();


            GameObject textObject =
                new GameObject(
                    "Text",
                    typeof(RectTransform),
                    typeof(CanvasRenderer),
                    typeof(TextMeshProUGUI));


            textObject.transform.SetParent(
                canvasObject.transform,
                false);


            RectTransform textRect =
                textObject.GetComponent<
                    RectTransform>();


            textRect.anchorMin =
                Vector2.zero;

            textRect.anchorMax =
                Vector2.one;

            textRect.offsetMin =
                Vector2.zero;

            textRect.offsetMax =
                Vector2.zero;


            labelText =
                textObject.GetComponent<
                    TextMeshProUGUI>();


            labelText.alignment =
                TextAlignmentOptions.Center;

            labelText.fontStyle =
                FontStyles.Bold;

            labelText.raycastTarget =
                false;

            labelText.color =
                baseColor;
        }


        private void LateUpdate()
        {
            Camera camera =
                Camera.main;


            if (camera == null)
                return;


            // Keep the little label facing the learner.
            // We are not modifying its position, only orientation.
            transform.rotation =
                camera.transform.rotation;
        }
    }
}