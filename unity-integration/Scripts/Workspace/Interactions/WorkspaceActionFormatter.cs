namespace MathConstructVR.Core
{
    internal static class WorkspaceActionFormatter
    {
        public static string JoinCombined(
            string objectLabel)
        {
            return
                $"Moved one {objectLabel} from one visible group to the other.";
        }

        public static string JoinChangeMovedIn(
            string objectLabel)
        {
            return
                $"Moved one {objectLabel} from the available objects into the starting collection.";
        }

        public static string JoinChangeMovedOut(
            string objectLabel)
        {
            return
                $"Returned one {objectLabel} from the collection to the available objects.";
        }

        public static string RemoveMovedOut(
            string objectLabel)
        {
            return
                $"Moved one {objectLabel} from the starting collection into the removed area.";
        }

        public static string RemoveReturned(
            string objectLabel)
        {
            return
                $"Returned one {objectLabel} from the removed area to the starting collection.";
        }

        public static string GroupCreated(
            string groupLabel,
            int groupCount)
        {
            return
                $"Created a new {groupLabel} group. The work now has {groupCount} groups.";
        }

        public static string GroupCopied(
            string objects,
            int copiedSize,
            int groupCount)
        {
            return
                $"Copied a group with {copiedSize} {objects}. The work now has {groupCount} groups.";
        }

        public static string EmptyGroupRemoved(
            int groupCount)
        {
            return
                $"Removed an empty group. The work now has {groupCount} groups.";
        }

        public static string GroupObjectMoved(
            string objectLabel,
            string destination)
        {
            return
                $"Moved one {objectLabel} to {destination}.";
        }

        public static string SharingObjectMoved(
            string objectLabel,
            string destination)
        {
            return
                $"Moved one {objectLabel} to {destination}.";
        }

        public static string RatioObjectMoved(
            string objectLabel,
            string destination)
        {
            return
                $"Moved one {objectLabel} to {destination}.";
        }
    }
}