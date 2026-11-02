using System;
using System.Collections;
using System.Threading;
using MathConstructVR.Config;
using MathConstructVR.Core;
using MathConstructVR.Networking.DTOs;
using PonyuDev.SherpaOnnx.Tts;
using UnityEngine;

namespace MathConstructVR.Presentation.Tutor
{
    public sealed class TutorSpeechController : MonoBehaviour
    {
        [Header("Application")]

        [SerializeField]
        private SessionController session;

        [SerializeField]
        private ExperienceController experience;

        [SerializeField]
        private MathConstructTextCatalog textCatalog;


        [Header("TTS")]

        [SerializeField]
        private TtsOrchestrator orchestrator;

        [SerializeField]
        private AudioSource audioSource;


        [Header("Opening")]

        [Min(0f)]
        [SerializeField]
        private float introDelaySeconds =
            0f;


        private bool ttsReady;
        private bool introStarted;

        private Coroutine introRoutine;

        private CancellationTokenSource
            speechCancellation;

        private int speechGeneration;


        public bool IsSpeaking
        {
            get;
            private set;
        }


        private void Start()
        {
            if (session == null)
            {
                Fail(
                    "TutorSpeechController has no SessionController.");

                return;
            }


            if (experience == null)
            {
                Fail(
                    "TutorSpeechController has no ExperienceController.");

                return;
            }


            if (textCatalog == null)
            {
                Fail(
                    "TutorSpeechController has no MathConstructTextCatalog.");

                return;
            }


            if (orchestrator == null)
            {
                Fail(
                    "TutorSpeechController has no TtsOrchestrator.");

                return;
            }


            if (audioSource == null)
            {
                Fail(
                    "TutorSpeechController has no AudioSource.");

                return;
            }


            session.CurrentQuestionChanged +=
                HandleQuestionChanged;


            experience.StateChanged +=
                HandleExperienceStateChanged;


            if (orchestrator.IsInitialized)
            {
                HandleTtsInitialized();
            }
            else
            {
                orchestrator.Initialized +=
                    HandleTtsInitialized;
            }


            TryStartIntro();
        }


        private void HandleTtsInitialized()
        {
            orchestrator.Initialized -=
                HandleTtsInitialized;


            ttsReady = true;


            TryStartIntro();
        }


        private void HandleQuestionChanged(
            QuestionDto question)
        {
            // Question changes during Exploration can be caused by the
            // development filter/navigation tools. The startup intro is
            // session-level guidance, not question-specific guidance, so
            // changing the selected question must not cancel it.
            if (experience.CurrentState !=
                ExperienceState.Attempt)
            {
                TryStartIntro();

                return;
            }


            // In Attempt, the opening guidance is question-specific.
            // Stop stale speech before speaking for the new question.
            StopSpeech();


            SpeakQuestionOpening(
                question);
        }


        private void HandleExperienceStateChanged(
            ExperienceState state)
        {
            if (state ==
                ExperienceState.Exploration)
            {
                // AppBootstrap initializes Exploration only after the
                // question session is ready. Calling TryStartIntro here
                // makes startup speech independent of Unity Start-order
                // timing between the session, experience, and TTS objects.
                TryStartIntro();
                return;
            }


            if (state !=
                ExperienceState.Attempt)
            {
                return;
            }


            StopSpeech();


            SpeakQuestionOpening(
                session.CurrentQuestion);
        }


        private void TryStartIntro()
        {
            if (introStarted)
                return;


            if (!ttsReady)
                return;


            if (session.CurrentQuestion == null)
                return;


            if (experience.CurrentState ==
                ExperienceState.Attempt)
            {
                return;
            }


            introStarted = true;


            if (introDelaySeconds <= 0f)
            {
                Speak(
                    textCatalog.TutorIntro);

                return;
            }


            introRoutine =
                StartCoroutine(
                    SpeakIntroAfterDelay());
        }


        private IEnumerator SpeakIntroAfterDelay()
        {
            yield return
                new WaitForSecondsRealtime(
                    introDelaySeconds);


            introRoutine = null;


            if (experience.CurrentState ==
                ExperienceState.Attempt)
            {
                yield break;
            }


            Speak(
                textCatalog.TutorIntro);
        }


        private void SpeakQuestionOpening(
            QuestionDto question)
        {
            if (question == null)
                return;


            string message =
                TutorMessageFactory
                    .InitialTutorMessage(
                        question,
                        textCatalog);


            Speak(
                message);


            Debug.Log(
                $"[MathConstructVR] Tutor opening guidance → " +
                $"{question.Id}");
        }


        public async void Speak(
            string text)
        {
            if (!ttsReady)
                return;


            if (string.IsNullOrWhiteSpace(
                    text))
            {
                return;
            }


            StopSpeech();


            int generation =
                ++speechGeneration;


            IsSpeaking =
                true;


            speechCancellation =
                new CancellationTokenSource();


            CancellationToken token =
                speechCancellation.Token;


            try
            {
                await orchestrator.Service.Speak(
                    text,
                    audioSource,
                    token,
                    onHandleStarted: null,
                    lookAhead: 3);
            }
            catch (OperationCanceledException)
            {
                // Expected when newer guidance replaces
                // speech that is no longer relevant.
            }
            catch (Exception exception)
            {
                Debug.LogError(
                    $"[MathConstructVR] Tutor speech failed:\n" +
                    $"{exception}",
                    this);
            }
            finally
            {
                if (speechGeneration ==
                    generation)
                {
                    IsSpeaking =
                        false;
                }
            }
        }


        public void StopSpeech()
        {
            speechGeneration++;

            IsSpeaking =
                false;


            if (introRoutine != null)
            {
                StopCoroutine(
                    introRoutine);


                introRoutine =
                    null;
            }


            if (speechCancellation != null)
            {
                speechCancellation.Cancel();

                speechCancellation.Dispose();

                speechCancellation =
                    null;
            }


            if (audioSource != null &&
                audioSource.isPlaying)
            {
                audioSource.Stop();
            }
        }


        private void Fail(
            string message)
        {
            Debug.LogError(
                $"[MathConstructVR] {message}",
                this);


            enabled =
                false;
        }


        private void OnDestroy()
        {
            if (session != null)
            {
                session.CurrentQuestionChanged -=
                    HandleQuestionChanged;
            }


            if (experience != null)
            {
                experience.StateChanged -=
                    HandleExperienceStateChanged;
            }


            if (orchestrator != null)
            {
                orchestrator.Initialized -=
                    HandleTtsInitialized;
            }


            StopSpeech();
        }
    }
}