using System;

namespace MathConstructVR.Domain
{
    public enum InteractionType
    {
        Unknown = 0,
        Join = 1,
        Remove = 2,
        EqualGroups = 3,
        EqualSharing = 4,
        PartToPartRatio = 5
    }

    public enum UnknownPositionType
    {
        Unknown = 0,
        Result = 1,
        Change = 2,
        Total = 3,
        ShareSize = 4,
        Representation = 5
    }

    public static class InteractionTypeParser
    {
        public static InteractionType Parse(
            string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return InteractionType.Unknown;

            if (string.Equals(value, "JOIN", StringComparison.OrdinalIgnoreCase))
                return InteractionType.Join;

            if (string.Equals(value, "REMOVE", StringComparison.OrdinalIgnoreCase))
                return InteractionType.Remove;

            if (string.Equals(value, "EQUAL_GROUPS", StringComparison.OrdinalIgnoreCase))
                return InteractionType.EqualGroups;

            if (string.Equals(value, "EQUAL_SHARING", StringComparison.OrdinalIgnoreCase))
                return InteractionType.EqualSharing;

            if (string.Equals(value, "PART_TO_PART_RATIO", StringComparison.OrdinalIgnoreCase))
                return InteractionType.PartToPartRatio;

            return InteractionType.Unknown;
        }
    }

    public static class UnknownPositionTypeParser
    {
        public static UnknownPositionType Parse(
            string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return UnknownPositionType.Unknown;

            if (string.Equals(value, "RESULT", StringComparison.OrdinalIgnoreCase))
                return UnknownPositionType.Result;

            if (string.Equals(value, "CHANGE", StringComparison.OrdinalIgnoreCase))
                return UnknownPositionType.Change;

            if (string.Equals(value, "TOTAL", StringComparison.OrdinalIgnoreCase))
                return UnknownPositionType.Total;

            if (string.Equals(value, "SHARE_SIZE", StringComparison.OrdinalIgnoreCase))
                return UnknownPositionType.ShareSize;

            if (string.Equals(value, "REPRESENTATION", StringComparison.OrdinalIgnoreCase))
                return UnknownPositionType.Representation;

            return UnknownPositionType.Unknown;
        }
    }
}