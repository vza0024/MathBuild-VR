using System;
using MathConstructVR.Domain;
using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class TutorRequestDto
    {
        [JsonProperty("question_id")]
        public string QuestionId { get; set; }

        [JsonProperty("learner_state")]
        public object LearnerState { get; set; }

        [JsonProperty("support_type")]
        public SupportType SupportType { get; set; }

        [JsonProperty("latest_action")]
        public string LatestAction { get; set; } = "";

        [JsonProperty("student_message")]
        public string StudentMessage { get; set; } = "";

        [JsonProperty("conversation_history")]
        public ConversationMessageDto[] ConversationHistory { get; set; } =
            Array.Empty<ConversationMessageDto>();

        [JsonProperty("view")]
        public ViewDataDto View { get; set; }
    }
}