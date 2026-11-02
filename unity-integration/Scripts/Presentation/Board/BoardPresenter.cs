using MathConstructVR.Core;
using MathConstructVR.Networking.DTOs;
using TMPro;
using UnityEngine;

namespace MathConstructVR.Presentation.Board
{
    public sealed class BoardPresenter : MonoBehaviour
    {
        [Header("Session")]

        [SerializeField]
        private SessionController sessionController;


        [Header("Board Text")]

        [SerializeField]
        private TMP_Text progressText;

        [SerializeField]
        private TMP_Text bodyText;

        [SerializeField]
        private TMP_Text questionText;


        private void OnEnable()
        {
            if (sessionController != null)
            {
                sessionController.CurrentQuestionChanged += HandleQuestionChanged;
            }
        }


        private void Start()
        {
            Refresh();
        }


        private void OnDisable()
        {
            if (sessionController != null)
            {
                sessionController.CurrentQuestionChanged -= HandleQuestionChanged;
            }
        }


        private void HandleQuestionChanged(QuestionDto question)
        {
            Refresh();
        }


        private void Refresh()
        {
            if (sessionController == null ||
                !sessionController.IsInitialized ||
                sessionController.CurrentQuestion == null)
            {
                ClearBoard();
                return;
            }

            QuestionDto question = sessionController.CurrentQuestion;

            progressText.text =
                $"PROBLEM {sessionController.CurrentQuestionNumber} " +
                $"OF {sessionController.CurrentPoolCount}";

            bodyText.text = question.Body ?? string.Empty;

            questionText.text = question.Question ?? string.Empty;
        }


        private void ClearBoard()
        {
            if (progressText != null)
                progressText.text = string.Empty;

            if (bodyText != null)
                bodyText.text = string.Empty;

            if (questionText != null)
                questionText.text = string.Empty;
        }
    }
}