using System;
using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    [Serializable]
    public sealed class HealthResponseDto
    {
        [JsonProperty("status")]
        public string Status { get; set; }

        [JsonProperty("app_version")]
        public string AppVersion { get; set; }

        [JsonProperty("question_count")]
        public int QuestionCount { get; set; }

        [JsonProperty("support_options")]
        public string[] SupportOptions { get; set; } = Array.Empty<string>();

        [JsonProperty("llm_provider")]
        public string LlmProvider { get; set; }

        [JsonProperty("llm_model")]
        public string LlmModel { get; set; }

        [JsonProperty("llm_configured")]
        public bool LlmConfigured { get; set; }

        [JsonProperty("llm_loaded")]
        public bool LlmLoaded { get; set; }

        [JsonProperty("hf_token_configured")]
        public bool HfTokenConfigured { get; set; }

        [JsonProperty("gpu_available")]
        public bool GpuAvailable { get; set; }

        [JsonProperty("gpu_name")]
        public string GpuName { get; set; }

        [JsonProperty("load_in_4bit")]
        public bool LoadIn4Bit { get; set; }

        [JsonProperty("model_error")]
        public string ModelError { get; set; }

        [JsonProperty("model_load_attempted")]
        public bool ModelLoadAttempted { get; set; }
    }
}