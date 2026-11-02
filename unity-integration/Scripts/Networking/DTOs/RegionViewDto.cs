using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class RegionViewDto
    {
        [JsonProperty("region_id")]
        public string RegionId { get; set; }

        [JsonProperty("visible_fraction")]
        public float? VisibleFraction { get; set; }

        [JsonProperty("label_visible")]
        public bool? LabelVisible { get; set; }

        [JsonProperty("label_seen_this_attempt")]
        public bool? LabelSeenThisAttempt { get; set; }
    }
}