using System;
using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class ViewDataDto
    {
        [JsonProperty("timestamp_ms")]
        public long? TimestampMs { get; set; }

        [JsonProperty("gaze_target")]
        public string GazeTarget { get; set; }

        [JsonProperty("head_position")]
        public float[] HeadPosition { get; set; }

        [JsonProperty("head_forward")]
        public float[] HeadForward { get; set; }

        [JsonProperty("fov_deg")]
        public float[] FovDeg { get; set; }

        [JsonProperty("regions")]
        public RegionViewDto[] Regions { get; set; } =
            Array.Empty<RegionViewDto>();

        [JsonProperty("last_touched_region_id")]
        public string LastTouchedRegionId { get; set; }

        [JsonProperty("attempt_id")]
        public string AttemptId { get; set; }

        [JsonProperty("snapshot_source")]
        public string SnapshotSource { get; set; }

        [JsonProperty("snapshot_age_ms")]
        public long? SnapshotAgeMs { get; set; }
    }
}