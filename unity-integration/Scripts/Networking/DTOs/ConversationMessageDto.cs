using Newtonsoft.Json;

namespace MathConstructVR.Networking.DTOs
{
    public sealed class ConversationMessageDto
    {
        [JsonProperty("role")]
        public string Role { get; set; }

        [JsonProperty("content")]
        public string Content { get; set; }
    }
}