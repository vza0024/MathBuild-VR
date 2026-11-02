using MathConstructVR.Config;
using TMPro;
using UnityEngine;

namespace MathConstructVR.Presentation.UI
{
    [RequireComponent(typeof(TMP_Text))]
    public sealed class CatalogTextBinder : MonoBehaviour
    {
        public enum TextEntry
        {
            TapToStart
        }


        [SerializeField]
        private MathConstructTextCatalog textCatalog;

        [SerializeField]
        private TextEntry textEntry =
            TextEntry.TapToStart;


        private TMP_Text targetText;


        private void Awake()
        {
            targetText =
                GetComponent<TMP_Text>();

            ApplyText();
        }


        private void ApplyText()
        {
            if (targetText == null)
            {
                targetText =
                    GetComponent<TMP_Text>();
            }

            if (textCatalog == null)
            {
                Debug.LogError(
                    "[MathConstructVR] CatalogTextBinder has no " +
                    "MathConstructTextCatalog assigned.",
                    this);

                return;
            }

            switch (textEntry)
            {
                case TextEntry.TapToStart:

                    targetText.text =
                        textCatalog.TapToStart;

                    break;
            }
        }


        [ContextMenu("Refresh Text")]
        private void RefreshText()
        {
            ApplyText();
        }
    }
}