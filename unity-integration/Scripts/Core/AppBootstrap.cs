using System;
using MathConstructVR.Networking;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class AppBootstrap : MonoBehaviour
    {
        [SerializeField]
        private BackendClient backendClient;

        [SerializeField]
        private SessionController sessionController;

        [SerializeField]
        private ExperienceController experienceController;

        [SerializeField]
        private WorkspaceController workspaceController;


        private async void Start()
        {
            try
            {
                var health = await backendClient.GetHealthAsync();

                Debug.Log(
                    $"[MathConstructVR] Backend connected.\n" +
                    $"Version: {health.AppVersion}\n" +
                    $"Backend questions: {health.QuestionCount}");

                var questions = await backendClient.GetQuestionsAsync();

                if (questions.Length != health.QuestionCount)
                {
                    Debug.LogWarning(
                        $"[MathConstructVR] Health endpoint reported " +
                        $"{health.QuestionCount} questions, but /api/questions " +
                        $"returned {questions.Length}.");
                }

                workspaceController.Initialize();

                sessionController.Initialize(questions);

                // The first workspace was just built by SessionController's
                // initial CurrentQuestionChanged event. Initialize the experience
                // state before subscribing to reset notifications so Exploration
                // does not immediately build the same workspace a second time.
                experienceController.Initialize();

                experienceController.StateChanged +=
                    HandleExperienceStateChanged;

                Debug.Log(
                    $"[MathConstructVR] Session initialized.\n" +
                    $"Session: {sessionController.SessionId}\n" +
                    $"Loaded: {sessionController.AllQuestions.Count} questions\n" +
                    $"Filter: {sessionController.SelectedFilter}\n" +
                    $"Current: {sessionController.CurrentQuestion.Id}\n" +
                    $"Problem: {sessionController.CurrentQuestionNumber} " +
                    $"of {sessionController.CurrentPoolCount}");
            }
            catch (Exception exception)
            {
                Debug.LogError(
                    $"[MathConstructVR] Application startup failed.\n{exception}");
            }
        }


        private void HandleExperienceStateChanged(
            ExperienceState state)
        {
            if (state != ExperienceState.Exploration)
                return;

            // Reset while AttemptContent is hidden so the next attempt
            // always begins from the question's authored baseline.
            workspaceController.ResetCurrentWorkspace();
        }


        private void OnDestroy()
        {
            if (experienceController != null)
            {
                experienceController.StateChanged -=
                    HandleExperienceStateChanged;
            }
        }
    }
}