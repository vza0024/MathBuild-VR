using Newtonsoft.Json;
using Newtonsoft.Json.Converters;

namespace MathConstructVR.Domain
{
    [JsonConverter(typeof(StringEnumConverter))]
    public enum SupportType
    {
        AUTO_CHECK,
        SIMPLIFY_STORY,
        INTERFACE_HELP,
        CHECK_WORK,
        SMALLER_EXAMPLE,
        UNSURE,
        HINT,
        OPEN_ENDED
    }
}