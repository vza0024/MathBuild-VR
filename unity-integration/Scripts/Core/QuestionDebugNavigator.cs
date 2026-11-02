using MathConstructVR.Domain;
using UnityEngine;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace MathConstructVR.Core
{
    public sealed class QuestionDebugNavigator : MonoBehaviour
    {
        [Header("Session")]
        [SerializeField]
        private SessionController sessionController;


        [Header("Play Mode Filter")]
        [Tooltip(
            "Change this dropdown while the game is running. " +
            "The selected question category will be applied immediately.")]
        [SerializeField]
        private QuestionFilter selectedFilter =
            QuestionFilter.ALL;


        [SerializeField]
        private bool liveApplySelectedFilter =
            true;


        [Header("Editor Keyboard Shortcuts")]
        [SerializeField]
        private bool enableKeyboardShortcuts =
            true;


        private void Update()
        {
            if (sessionController == null ||
                !sessionController.IsInitialized)
            {
                return;
            }


            // ---------------------------------------------
            // LIVE INSPECTOR DROPDOWN
            // ---------------------------------------------

            if (liveApplySelectedFilter &&
                sessionController.SelectedFilter !=
                    selectedFilter)
            {
                ApplySelectedFilter();
            }


            // ---------------------------------------------
            // KEYBOARD
            // ---------------------------------------------

#if ENABLE_INPUT_SYSTEM

            if (!enableKeyboardShortcuts)
                return;


            Keyboard keyboard =
                Keyboard.current;


            if (keyboard == null)
                return;


            if (keyboard.digit1Key.wasPressedThisFrame)
            {
                SetFilter(
                    QuestionFilter.ALL);
            }


            if (keyboard.digit2Key.wasPressedThisFrame)
            {
                SetFilter(
                    QuestionFilter.JOIN);
            }


            if (keyboard.digit3Key.wasPressedThisFrame)
            {
                SetFilter(
                    QuestionFilter.REMOVE);
            }


            if (keyboard.digit4Key.wasPressedThisFrame)
            {
                SetFilter(
                    QuestionFilter.EQUAL_GROUPS);
            }


            if (keyboard.digit5Key.wasPressedThisFrame)
            {
                SetFilter(
                    QuestionFilter.EQUAL_SHARING);
            }


            if (keyboard.digit6Key.wasPressedThisFrame)
            {
                SetFilter(
                    QuestionFilter.PART_TO_PART_RATIO);
            }


            if (keyboard.rightArrowKey.wasPressedThisFrame ||
                keyboard.nKey.wasPressedThisFrame)
            {
                NextQuestion();
            }


            if (keyboard.leftArrowKey.wasPressedThisFrame ||
                keyboard.pKey.wasPressedThisFrame)
            {
                PreviousQuestion();
            }

#endif
        }


        [ContextMenu("Apply Selected Filter")]
        public void ApplySelectedFilter()
        {
            if (!CanNavigate())
                return;


            sessionController.SetFilter(
                selectedFilter);


            LogCurrentQuestion();
        }


        public void SetFilter(
            QuestionFilter filter)
        {
            if (!CanNavigate())
                return;


            selectedFilter =
                filter;


            sessionController.SetFilter(
                selectedFilter);


            LogCurrentQuestion();
        }


        [ContextMenu("Next Question")]
        public void NextQuestion()
        {
            if (!CanNavigate())
                return;


            sessionController.NextQuestion();

            LogCurrentQuestion();
        }


        [ContextMenu("Previous Question")]
        public void PreviousQuestion()
        {
            if (!CanNavigate())
                return;


            sessionController.PreviousQuestion();

            LogCurrentQuestion();
        }


        public void ShowAll()
        {
            SetFilter(
                QuestionFilter.ALL);
        }


        public void ShowJoin()
        {
            SetFilter(
                QuestionFilter.JOIN);
        }


        public void ShowRemove()
        {
            SetFilter(
                QuestionFilter.REMOVE);
        }


        public void ShowEqualGroups()
        {
            SetFilter(
                QuestionFilter.EQUAL_GROUPS);
        }


        public void ShowEqualSharing()
        {
            SetFilter(
                QuestionFilter.EQUAL_SHARING);
        }


        public void ShowRatio()
        {
            SetFilter(
                QuestionFilter.PART_TO_PART_RATIO);
        }


        private bool CanNavigate()
        {
            if (sessionController == null)
            {
                Debug.LogWarning(
                    "[MathConstructVR] QuestionDebugNavigator " +
                    "has no SessionController assigned.",
                    this);

                return false;
            }


            if (!sessionController.IsInitialized)
            {
                Debug.LogWarning(
                    "[MathConstructVR] QuestionDebugNavigator: " +
                    "session has not initialized yet.",
                    this);

                return false;
            }


            return true;
        }


        private void LogCurrentQuestion()
        {
            if (sessionController.CurrentQuestion == null)
                return;


            Debug.Log(
                $"[MathConstructVR] Debug question navigation\n" +
                $"Filter: {sessionController.SelectedFilter}\n" +
                $"Problem: {sessionController.CurrentQuestionNumber} " +
                $"of {sessionController.CurrentPoolCount}\n" +
                $"ID: {sessionController.CurrentQuestion.Id}\n" +
                $"Interaction: {sessionController.CurrentQuestion.Interaction}\n" +
                $"Subtype: {sessionController.CurrentQuestion.Subtype}");
        }
    }
}