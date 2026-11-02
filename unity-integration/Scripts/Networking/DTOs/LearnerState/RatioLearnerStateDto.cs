using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs.LearnerState
{
    public sealed class RatioLearnerStateDto
    {
        [JsonProperty("part_a_count")]
        public int PartACount { get; set; }

        [JsonProperty("part_b_count")]
        public int PartBCount { get; set; }

        [JsonProperty("unassigned_a")]
        public int UnassignedA { get; set; }

        [JsonProperty("unassigned_b")]
        public int UnassignedB { get; set; }

        [JsonProperty("answer")]
        public int? Answer { get; set; }
    }
}