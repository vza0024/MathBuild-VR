using MathConstructVR.Config;
using MathConstructVR.Core;
using MathConstructVR.Domain;
using UnityEngine;

namespace MathConstructVR.Presentation.Tutor
{
    public sealed class SupportWhiteBoardController :
        MonoBehaviour
    {
        [Header("Application")]

        [SerializeField]
        private SessionController session;

        [SerializeField]
        private ExperienceController experience;

        [SerializeField]
        private TutorInteractionController tutorInteraction;

        [SerializeField]
        private TutorSpeechController tutorSpeech;

        [SerializeField]
        private MathConstructTextCatalog textCatalog;


        private void Awake()
        {
            ValidateReferences();
        }


        public void WhoOrWhat()
        {
            Debug.Log(
                "[MathConstructVR] BUTTON FIRED → Who or what?");


            SpeakStoryClue(
                StoryClueKind.WhoOrWhat);
        }


        public void WhatHappens()
        {
            Debug.Log(
                "[MathConstructVR] BUTTON FIRED → What happens?");


            SpeakStoryClue(
                StoryClueKind.WhatHappens);
        }


        public void WhatAreWeFinding()
        {
            Debug.Log(
                "[MathConstructVR] BUTTON FIRED → What are we finding?");


            SpeakStoryClue(
                StoryClueKind.WhatAreWeFinding);
        }


        public void StoryAsking()
        {
            Debug.Log(
                "[MathConstructVR] BUTTON FIRED → " +
                "What is the story asking me?");


            RequestManualSupport(
                SupportType.SIMPLIFY_STORY);
        }


        public void CheckWork()
        {
            Debug.Log(
                "[MathConstructVR] BUTTON FIRED → " +
                "Can you check what I did?");


            RequestManualSupport(
                SupportType.CHECK_WORK);
        }


        public void Hint()
        {
            Debug.Log(
                "[MathConstructVR] BUTTON FIRED → Can I get a hint?");


            RequestManualSupport(
                SupportType.HINT);
        }


        private void RequestManualSupport(
            SupportType supportType)
        {
            if (!CanUseTutor())
                return;


            if (!textCatalog.TryGetSupportRequest(
                    supportType,
                    out string visibleChoice,
                    out string studentMessage))
            {
                Debug.LogError(
                    $"[MathConstructVR] No text-catalog entry exists " +
                    $"for support type '{supportType}'.",
                    this);

                return;
            }


            tutorInteraction.RequestManualSupport(
                supportType,
                visibleChoice,
                studentMessage);
        }


        private void SpeakStoryClue(
            StoryClueKind clueKind)
        {
            if (!CanUseTutor())
                return;


            tutorInteraction
                .CancelAutomaticGuidanceForLocalHelp();


            string text =
                TutorMessageFactory.StoryClue(
                    session.CurrentQuestion,
                    clueKind,
                    textCatalog);


            if (string.IsNullOrWhiteSpace(
                    text))
            {
                Debug.LogWarning(
                    "[MathConstructVR] Story clue returned no text.",
                    this);

                return;
            }


            tutorSpeech.Speak(
                text);
        }


        private bool CanUseTutor()
        {
            if (!ValidateReferences())
                return false;


            if (experience.CurrentState !=
                ExperienceState.Attempt)
            {
                Debug.Log(
                    "[MathConstructVR] Whiteboard request ignored: " +
                    "learner is not in Attempt mode.");

                return false;
            }


            if (session.CurrentQuestion == null)
            {
                Debug.LogWarning(
                    "[MathConstructVR] Whiteboard request ignored: " +
                    "there is no current question.",
                    this);

                return false;
            }


            if (tutorInteraction.IsManualRequestBusy)
            {
                Debug.Log(
                    "[MathConstructVR] Whiteboard request ignored: " +
                    "a manual tutor request is already running.");

                return false;
            }


            return true;
        }


        private bool ValidateReferences()
        {
            bool valid =
                true;


            if (session == null)
            {
                Debug.LogError(
                    "[MathConstructVR] SupportWhiteBoardController: " +
                    "Session is not assigned.",
                    this);

                valid =
                    false;
            }


            if (experience == null)
            {
                Debug.LogError(
                    "[MathConstructVR] SupportWhiteBoardController: " +
                    "Experience is not assigned.",
                    this);

                valid =
                    false;
            }


            if (tutorInteraction == null)
            {
                Debug.LogError(
                    "[MathConstructVR] SupportWhiteBoardController: " +
                    "TutorInteraction is not assigned.",
                    this);

                valid =
                    false;
            }


            if (tutorSpeech == null)
            {
                Debug.LogError(
                    "[MathConstructVR] SupportWhiteBoardController: " +
                    "TutorSpeech is not assigned.",
                    this);

                valid =
                    false;
            }


            if (textCatalog == null)
            {
                Debug.LogError(
                    "[MathConstructVR] SupportWhiteBoardController: " +
                    "Text Catalog is not assigned.",
                    this);

                valid =
                    false;
            }


            return valid;
        }
    }
}