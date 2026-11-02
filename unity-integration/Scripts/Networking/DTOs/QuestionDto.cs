using System;
using MathConstructVR.Domain;
using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    [Serializable]
    public sealed class QuestionDto
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("asdiv_id")]
        public string AsdivId { get; set; }

        [JsonProperty("grade")]
        public int Grade { get; set; }

        [JsonProperty("body")]
        public string Body { get; set; }

        [JsonProperty("question")]
        public string Question { get; set; }

        [JsonProperty("topic")]
        public string Topic { get; set; }

        [JsonProperty("subtype")]
        public string Subtype { get; set; }

        [JsonProperty("unknown_position")]
        public string UnknownPosition { get; set; }

        [JsonProperty("parameters")]
        public QuestionParametersDto Parameters { get; set; }

        [JsonProperty("visual")]
        public QuestionVisualDto Visual { get; set; }

        [JsonProperty("interaction")]
        public string Interaction { get; set; }

        [JsonProperty("visible_roles")]
        public string[] VisibleRoles { get; set; } =
            Array.Empty<string>();

        [JsonProperty("hidden_role")]
        public string HiddenRole { get; set; }

        [JsonIgnore]
        public InteractionType InteractionType =>
            InteractionTypeParser.Parse(Interaction);

        [JsonIgnore]
        public UnknownPositionType UnknownPositionType =>
            UnknownPositionTypeParser.Parse(UnknownPosition);
    }
}
