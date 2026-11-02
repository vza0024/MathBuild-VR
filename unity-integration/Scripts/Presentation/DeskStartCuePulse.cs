using UnityEngine;

namespace MathConstructVR.Presentation
{
    [RequireComponent(typeof(LineRenderer))]
    public sealed class DeskStartCuePulse : MonoBehaviour
    {
        [Header("Dotted Line")]
        [SerializeField, Range(0f, 1f)]
        private float minimumAlpha = 0.18f;

        [SerializeField, Range(0f, 1f)]
        private float maximumAlpha = 0.55f;

        [SerializeField]
        private float cyclesPerSecond = 0.5f;


        private LineRenderer lineRenderer;
        private MaterialPropertyBlock propertyBlock;

        private static readonly int BaseColorId =
            Shader.PropertyToID("_BaseColor");

        private Color baseColor = Color.white;


        private void Awake()
        {
            lineRenderer =
                GetComponent<LineRenderer>();

            propertyBlock =
                new MaterialPropertyBlock();

            if (lineRenderer.sharedMaterial != null &&
                lineRenderer.sharedMaterial.HasProperty(BaseColorId))
            {
                baseColor =
                    lineRenderer.sharedMaterial.GetColor(BaseColorId);
            }
            else
            {
                baseColor =
                    lineRenderer.startColor;
            }
        }


        private void Update()
        {
            float wave =
                (Mathf.Sin(
                    Time.unscaledTime *
                    cyclesPerSecond *
                    Mathf.PI *
                    2f) + 1f) *
                0.5f;

            float alpha =
                Mathf.Lerp(
                    minimumAlpha,
                    maximumAlpha,
                    wave);

            Color color =
                baseColor;

            color.a =
                alpha;

            lineRenderer.GetPropertyBlock(
                propertyBlock);

            propertyBlock.SetColor(
                BaseColorId,
                color);

            lineRenderer.SetPropertyBlock(
                propertyBlock);
        }
    }
}