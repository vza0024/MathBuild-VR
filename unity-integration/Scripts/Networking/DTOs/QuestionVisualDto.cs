using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class QuestionVisualDto
    {
        [JsonProperty("object_label")]
        public string ObjectLabel { get; set; }

        [JsonProperty("object_plural")]
        public string ObjectPlural { get; set; }

        [JsonProperty("object_code")]
        public string ObjectCode { get; set; }

        [JsonProperty("fallback_emoji")]
        public string FallbackEmoji { get; set; }

        [JsonProperty("initial_object_label")]
        public string InitialObjectLabel { get; set; }

        [JsonProperty("initial_object_code")]
        public string InitialObjectCode { get; set; }

        [JsonProperty("initial_fallback_emoji")]
        public string InitialFallbackEmoji { get; set; }

        [JsonProperty("change_object_label")]
        public string ChangeObjectLabel { get; set; }

        [JsonProperty("change_object_code")]
        public string ChangeObjectCode { get; set; }

        [JsonProperty("change_fallback_emoji")]
        public string ChangeFallbackEmoji { get; set; }

        [JsonProperty("group_label")]
        public string GroupLabel { get; set; }

        [JsonProperty("group_emoji")]
        public string GroupEmoji { get; set; }

        [JsonProperty("recipient_label")]
        public string RecipientLabel { get; set; }

        [JsonProperty("recipient_labels")]
        public string[] RecipientLabels { get; set; }

        [JsonProperty("recipient_emoji")]
        public string RecipientEmoji { get; set; }

        [JsonProperty("part_a_label")]
        public string PartALabel { get; set; }

        [JsonProperty("part_b_label")]
        public string PartBLabel { get; set; }

        [JsonProperty("part_a_emoji")]
        public string PartAEmoji { get; set; }

        [JsonProperty("part_b_emoji")]
        public string PartBEmoji { get; set; }
    }
}