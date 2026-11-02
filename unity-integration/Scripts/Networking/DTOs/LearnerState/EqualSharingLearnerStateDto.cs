using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs.LearnerState
{
    public sealed class EqualSharingLearnerStateDto
    {
        [JsonProperty("share_sizes")]
        public int[] ShareSizes { get; set; } = System.Array.Empty<int>();

        [JsonProperty("undistributed_count")]
        public int UndistributedCount { get; set; }

        [JsonProperty("answer")]
        public int? Answer { get; set; }
    }
}