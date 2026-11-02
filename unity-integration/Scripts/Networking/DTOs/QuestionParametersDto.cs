using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class QuestionParametersDto
    {
        [JsonProperty("initial")]
        public int? Initial { get; set; }

        [JsonProperty("change")]
        public int? Change { get; set; }

        [JsonProperty("result")]
        public int? Result { get; set; }

        [JsonProperty("group_count")]
        public int? GroupCount { get; set; }

        [JsonProperty("group_size")]
        public int? GroupSize { get; set; }

        [JsonProperty("total")]
        public int? Total { get; set; }

        [JsonProperty("recipient_count")]
        public int? RecipientCount { get; set; }

        [JsonProperty("share_size")]
        public int? ShareSize { get; set; }

        [JsonProperty("part_a")]
        public int? PartA { get; set; }

        [JsonProperty("part_b")]
        public int? PartB { get; set; }
    }
}