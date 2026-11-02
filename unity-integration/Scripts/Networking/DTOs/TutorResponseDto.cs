using MathConstructVR.Domain;
using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class TutorResponseDto
    {
        [JsonProperty("tutor_response")]
        public string TutorResponse { get; set; }

        [JsonProperty("conversation_status")]
        public string ConversationStatus { get; set; }

        [JsonProperty("student_correct")]
        public bool StudentCorrect { get; set; }

        [JsonProperty("support_type")]
        public SupportType SupportType { get; set; }
    }
}