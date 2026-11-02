using TMPro;
using UnityEngine;

namespace MathConstructVR.UI
{
    [ExecuteAlways]
    public class CurvedTMPText : MonoBehaviour
    {
        [Header("Curve")]
        [Tooltip("Positive values sag downward in the middle. Negative values curve upward.")]
        [Range(-1f, 1f)]
        [SerializeField] private float curveAmount = 0.15f;

        [Tooltip("Rotates each character slightly so it follows the curve.")]
        [SerializeField] private bool rotateAlongCurve = true;

        private TMP_Text textComponent;

        private void OnEnable()
        {
            textComponent = GetComponent<TMP_Text>();

            if (textComponent == null)
            {
                Debug.LogError(
                    $"[{nameof(CurvedTMPText)}] No TMP_Text component found on {name}.",
                    this);
                enabled = false;
                return;
            }

            textComponent.OnPreRenderText += CurveText;
            textComponent.SetVerticesDirty();
        }

        private void OnDisable()
        {
            if (textComponent != null)
                textComponent.OnPreRenderText -= CurveText;
        }

        private void OnValidate()
        {
            if (textComponent == null)
                textComponent = GetComponent<TMP_Text>();

            if (textComponent != null)
                textComponent.SetVerticesDirty();
        }

        private void CurveText(TMP_TextInfo textInfo)
        {
            if (textInfo.characterCount == 0)
                return;

            float minX = float.MaxValue;
            float maxX = float.MinValue;

            // Find the horizontal extent of the visible text.
            for (int i = 0; i < textInfo.characterCount; i++)
            {
                TMP_CharacterInfo character = textInfo.characterInfo[i];

                if (!character.isVisible)
                    continue;

                minX = Mathf.Min(minX, character.bottomLeft.x);
                maxX = Mathf.Max(maxX, character.topRight.x);
            }

            float width = maxX - minX;

            if (width <= 0.0001f)
                return;

            float midpoint = (minX + maxX) * 0.5f;

            // Make curve amount scale naturally with the chosen font size.
            float sag = curveAmount * textComponent.fontSize;

            for (int i = 0; i < textInfo.characterCount; i++)
            {
                TMP_CharacterInfo character = textInfo.characterInfo[i];

                if (!character.isVisible)
                    continue;

                int materialIndex = character.materialReferenceIndex;
                int vertexIndex = character.vertexIndex;

                Vector3[] vertices = textInfo.meshInfo[materialIndex].vertices;

                // Center of this character.
                Vector3 characterCenter =
                    (vertices[vertexIndex + 0] + vertices[vertexIndex + 2]) * 0.5f;

                // Horizontal position from -1 at left edge to +1 at right edge.
                float normalizedX =
                    ((characterCenter.x - midpoint) / (width * 0.5f));

                normalizedX = Mathf.Clamp(normalizedX, -1f, 1f);

                // Parabolic curve:
                // edges = 0 displacement
                // middle = maximum sag
                float yOffset =
                    -sag * (1f - normalizedX * normalizedX);

                float angle = 0f;

                if (rotateAlongCurve)
                {
                    // Derivative of the parabola so characters follow its slope.
                    float slope =
                        (4f * sag * normalizedX) / width;

                    angle = Mathf.Atan(slope) * Mathf.Rad2Deg;
                }

                Quaternion rotation = Quaternion.Euler(0f, 0f, angle);

                for (int j = 0; j < 4; j++)
                {
                    int index = vertexIndex + j;

                    Vector3 vertex = vertices[index];

                    vertex -= characterCenter;
                    vertex = rotation * vertex;
                    vertex += characterCenter;
                    vertex.y += yOffset;

                    vertices[index] = vertex;
                }
            }
        }
    }
}