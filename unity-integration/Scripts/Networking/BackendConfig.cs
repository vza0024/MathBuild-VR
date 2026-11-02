using UnityEngine;

namespace MathConstructVR.Networking
{
    [CreateAssetMenu(
        fileName = "BackendConfig",
        menuName = "MathConstructVR/Backend Config")]
    public sealed class BackendConfig : ScriptableObject
    {
        [Header("Backend URLs")]

        [SerializeField]
        private string editorBaseUrl = "http://127.0.0.1:8000";

        [SerializeField]
        private string questBaseUrl = "https://abhisheks-macbook-pro.tailf247c6.ts.net";

        [Header("Request Settings")]

        [SerializeField, Min(1)]
        private int requestTimeoutSeconds = 90;


        public string BaseUrl
        {
            get
            {
                #if UNITY_EDITOR
                    return NormalizeUrl(editorBaseUrl);
                #elif UNITY_ANDROID
                    return NormalizeUrl(questBaseUrl);
                #else
                    return NormalizeUrl(editorBaseUrl);
                #endif
            }
        }

        public int RequestTimeoutSeconds => requestTimeoutSeconds;


        private static string NormalizeUrl(string url)
        {
            if (string.IsNullOrWhiteSpace(url))
                return string.Empty;

            return url.Trim().TrimEnd('/');
        }
    }
}