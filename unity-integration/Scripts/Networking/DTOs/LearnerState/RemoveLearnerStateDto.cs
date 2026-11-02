using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs.LearnerState
{
    public sealed class RemoveLearnerStateDto
    {
        [JsonProperty("removed_count")]
        public int RemovedCount { get; set; }

        [JsonProperty("remaining_count")]
        public int RemainingCount { get; set; }

        [JsonProperty("answer")]
        public int? Answer { get; set; }
    }
}