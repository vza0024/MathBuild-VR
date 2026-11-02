using MathConstructVR.Domain;
using UnityEngine;

namespace MathConstructVR.Config
{
    [CreateAssetMenu(
        fileName = "MathConstructTextCatalog",
        menuName = "MathConstructVR/Text Catalog")]
    public sealed class MathConstructTextCatalog : ScriptableObject
    {
        [Header("Session")]
        [TextArea(3, 6)]
        [SerializeField]
        private string tutorIntro =
            "Hi! I'm your math tutor. " +
            "Take a look at the story on the board. " +
            "When you're ready, tap the desk and let's solve it together.";

        [Header("Exploration")]
        [SerializeField]
        private string tapToStart =
            "Tap the desk to start";

        [Header("Workspace - Fixed Labels")]
        [SerializeField]
        private string joinGroupA =
            "Group A";

        [SerializeField]
        private string joinGroupB =
            "Group B";


        [SerializeField]
        private string startingCollection =
            "Starting collection";

        [SerializeField]
        private string removed =
            "Removed";

        [SerializeField]
        private string objectsToTry =
            "Objects to try";

        [Header("Workspace - Formats")]
        [SerializeField]
        private string amountTitleFormat =
            "{0} {1}";

        [SerializeField]
        private string toPlaceFormat =
            "{0} to place";

        [SerializeField]
        private string toShareFormat =
            "{0} to share";

        [SerializeField]
        private string groupTitleFormat =
            "{0} {1}";

        [SerializeField]
        private string recipientTitleFormat =
            "{0} {1}";

        [SerializeField]
        private string ratioBankFormat =
            "{0} to use";

        [SerializeField]
        private string ratioFirstFormat =
            "First: {0}";

        [SerializeField]
        private string ratioSecondFormat =
            "Second: {0}";

        [Header("Local Tutor - Opening")]
        [TextArea(2, 5)]
        [SerializeField]
        private string joinOpening =
            "Let's build the story. {story} " +
            "Use the {objects} on the table to show what the story says.";

        [TextArea(2, 5)]
        [SerializeField]
        private string removeOpening =
            "Let's build the story. {story} " +
            "Use the {objects} on the table to show what changes and what stays.";

        [TextArea(2, 5)]
        [SerializeField]
        private string equalGroupsOpening =
            "Let's build the story. {story} " +
            "Use the {objects} to make the equal groups in the story.";

        [TextArea(2, 5)]
        [SerializeField]
        private string equalSharingOpening =
            "Let's build the story. {story} " +
            "Use the {objects} to show how they are shared equally.";

        [TextArea(2, 5)]
        [SerializeField]
        private string ratioOpening =
            "Let's build the story. {story} " +
            "Use the objects on the table to show the two amounts being compared.";

        [TextArea(2, 5)]
        [SerializeField]
        private string fallbackOpening =
            "Let's build the story. {story} " +
            "Use the objects on the table to show what the story says.";

        [Header("Local Tutor - Story Clues")]
        [TextArea(2, 4)]
        [SerializeField]
        private string whoOrWhat =
            "The important things in this story are the {objects} and their amounts.";

        [TextArea(2, 4)]
        [SerializeField]
        private string joinWhatHappens =
            "There are two amounts in the story. " +
            "Show both amounts together with the {objects}.";

        [TextArea(2, 4)]
        [SerializeField]
        private string removeWhatHappens =
            "Start with the amount in the story, " +
            "then show what is taken away and what remains.";

        [TextArea(2, 4)]
        [SerializeField]
        private string equalGroupsWhatHappens =
            "Build the groups from the story so every group has the same amount.";

        [TextArea(2, 4)]
        [SerializeField]
        private string equalSharingWhatHappens =
            "Share the {objects} so each recipient gets the same amount.";

        [TextArea(2, 4)]
        [SerializeField]
        private string ratioWhatHappens =
            "Build the two amounts from the story and keep them in their own collections.";

        [TextArea(2, 4)]
        [SerializeField]
        private string fallbackWhatHappens =
            "Use the objects on the table to show what happens in the story.";

        [TextArea(2, 4)]
        [SerializeField]
        private string whatAreWeFinding =
            "We need to find {question}.";

        [Header("Manual Tutor Requests")]
        [SerializeField]
        private string storyAskingChoice =
            "What is the story asking me?";

        [TextArea(2, 4)]
        [SerializeField]
        private string storyAskingMessage =
            "I need help understanding what the story is asking me to find.";

        [SerializeField]
        private string checkWorkChoice =
            "Can you check what I did?";

        [TextArea(2, 4)]
        [SerializeField]
        private string checkWorkMessage =
            "Please look at what I have done and help me check whether it matches the story.";

        [SerializeField]
        private string hintChoice =
            "Can I get a hint?";

        [TextArea(2, 4)]
        [SerializeField]
        private string hintMessage =
            "Please give me one small hint based on my work without giving me the answer.";

        public string TutorIntro => tutorIntro;
        public string TapToStart => tapToStart;

        public string JoinGroupA => joinGroupA;
        public string JoinGroupB => joinGroupB;
        public string StartingCollection => startingCollection;
        public string Removed => removed;
        public string ObjectsToTry => objectsToTry;

        public string FormatAmountTitle(
            int amount,
            string objects)
        {
            return string.Format(
                amountTitleFormat,
                amount,
                Capitalize(objects));
        }

        public string FormatToPlace(
            string objects)
        {
            return string.Format(
                toPlaceFormat,
                Capitalize(objects));
        }

        public string FormatToShare(
            string objects)
        {
            return string.Format(
                toShareFormat,
                Capitalize(objects));
        }

        public string FormatGroupTitle(
            string groupLabel,
            int groupNumber)
        {
            return string.Format(
                groupTitleFormat,
                Capitalize(groupLabel),
                groupNumber);
        }

        public string FormatRecipientTitle(
            string recipientLabel,
            int recipientNumber)
        {
            return string.Format(
                recipientTitleFormat,
                Capitalize(recipientLabel),
                recipientNumber);
        }

        public string FormatRatioBank(
            string partLabel)
        {
            return string.Format(
                ratioBankFormat,
                Capitalize(partLabel));
        }

        public string FormatRatioFirst(
            string partLabel)
        {
            return string.Format(
                ratioFirstFormat,
                partLabel);
        }

        public string FormatRatioSecond(
            string partLabel)
        {
            return string.Format(
                ratioSecondFormat,
                partLabel);
        }

        public string GetOpeningTemplate(
            InteractionType interactionType)
        {
            switch (interactionType)
            {
                case InteractionType.Join:
                    return joinOpening;

                case InteractionType.Remove:
                    return removeOpening;

                case InteractionType.EqualGroups:
                    return equalGroupsOpening;

                case InteractionType.EqualSharing:
                    return equalSharingOpening;

                case InteractionType.PartToPartRatio:
                    return ratioOpening;

                default:
                    return fallbackOpening;
            }
        }

        public string GetWhoOrWhatTemplate()
        {
            return whoOrWhat;
        }

        public string GetWhatHappensTemplate(
            InteractionType interactionType)
        {
            switch (interactionType)
            {
                case InteractionType.Join:
                    return joinWhatHappens;

                case InteractionType.Remove:
                    return removeWhatHappens;

                case InteractionType.EqualGroups:
                    return equalGroupsWhatHappens;

                case InteractionType.EqualSharing:
                    return equalSharingWhatHappens;

                case InteractionType.PartToPartRatio:
                    return ratioWhatHappens;

                default:
                    return fallbackWhatHappens;
            }
        }

        public string GetFindingTemplate()
        {
            return whatAreWeFinding;
        }

        public bool TryGetSupportRequest(
            SupportType supportType,
            out string visibleChoice,
            out string studentMessage)
        {
            switch (supportType)
            {
                case SupportType.SIMPLIFY_STORY:
                    visibleChoice = storyAskingChoice;
                    studentMessage = storyAskingMessage;
                    return true;

                case SupportType.CHECK_WORK:
                    visibleChoice = checkWorkChoice;
                    studentMessage = checkWorkMessage;
                    return true;

                case SupportType.HINT:
                    visibleChoice = hintChoice;
                    studentMessage = hintMessage;
                    return true;

                default:
                    visibleChoice = "";
                    studentMessage = "";
                    return false;
            }
        }

        private static string Capitalize(
            string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "Objects";

            value = value.Trim();

            if (value.Length == 1)
                return value.ToUpperInvariant();

            return
                char.ToUpperInvariant(value[0]) +
                value.Substring(1);
        }
    }
}