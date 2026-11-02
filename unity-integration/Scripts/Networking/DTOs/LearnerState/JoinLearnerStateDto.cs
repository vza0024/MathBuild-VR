using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs.LearnerState
{
    public sealed class JoinLearnerStateDto
    {
        // Legacy fields retained so the current backend contract does not break.
        [JsonProperty("added_count")]
        public int AddedCount { get; set; }

        [JsonProperty("current_count")]
        public int CurrentCount { get; set; }

        [JsonProperty("answer")]
        public int? Answer { get; set; }

        // New physical-construction state.
        [JsonProperty("workspace_mode")]
        public string WorkspaceMode { get; set; }

        [JsonProperty("destination_label")]
        public string DestinationLabel { get; set; }

        [JsonProperty("part_a_label")]
        public string PartALabel { get; set; }

        [JsonProperty("part_b_label")]
        public string PartBLabel { get; set; }

        [JsonProperty("part_a_count")]
        public int? PartACount { get; set; }

        [JsonProperty("part_b_count")]
        public int? PartBCount { get; set; }

        [JsonProperty("total_count")]
        public int TotalCount { get; set; }

        [JsonProperty("story_quantities_pre_spawned")]
        public bool StoryQuantitiesPreSpawned { get; set; } = false;

        [JsonProperty("state_note")]
        public string StateNote { get; set; } =
            "These counts describe only objects physically placed by the learner. " +
            "Story quantities are not pre-spawned or automatically visible.";
    }
}