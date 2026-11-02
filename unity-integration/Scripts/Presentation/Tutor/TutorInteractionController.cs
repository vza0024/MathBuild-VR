using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MathConstructVR.Core;
using MathConstructVR.Domain;
using MathConstructVR.Networking;
using MathConstructVR.Networking.DTOs;
using MathConstructVR.Presentation.UI;
using UnityEngine;

namespace MathConstructVR.Presentation.Tutor
{
    public sealed class TutorInteractionController :
        MonoBehaviour
    {
        private const int MaxHistoryCount = 30;

        private const int HistorySentToBackend = 20;


        [Header("Application")]
        [SerializeField]
        private BackendClient backendClient;

        [SerializeField]
        private SessionController session;

        [SerializeField]
        private ExperienceController experience;

        [SerializeField]
        private WorkspaceController workspace;

        [SerializeField]
        private WorkspacePovDebug workspacePovDebug;

        [SerializeField]
        private TutorSpeechController tutorSpeech;

        [Header("Tablet Send Hint")]
        [SerializeField]
        private HelpTabletController helpTablet;

        [Header("Automatic Tutoring")]
        [Min(0.1f)]
        [SerializeField]
        private float autoCheckDelaySeconds = 3.6f;


        private readonly List<ConversationMessageDto>
            conversationHistory =
                new();

        private readonly HashSet<string>
            inFlightAutoSignatures =
                new();


        private Coroutine autoCheckRoutine;

        private bool tutoringComplete;

        private bool manualRequestBusy;

        private string completedStateSignature =
            "";

        private string lastAutoCompletedStateSignature =
            "";

        private int automaticHistoryIndex = -1;

        private int questionGeneration;

        private int automaticGeneration;

        private int manualSequence;


        public bool TutoringComplete =>
            tutoringComplete;

        public bool IsManualRequestBusy =>
            manualRequestBusy;

        public bool CanRequestManualHelp =>
            isActiveAndEnabled &&
            experience != null &&
            experience.CurrentState ==
            ExperienceState.Attempt &&
            !manualRequestBusy &&
            !tutoringComplete;


        public event Action<bool>
            HelpAvailabilityChanged;


        private void Awake()
        {
            if (backendClient == null ||
                session == null ||
                experience == null ||
                workspace == null ||
                workspacePovDebug == null ||
                tutorSpeech == null)
            {
                Debug.LogError(
                    "[MathConstructVR] " +
                    "TutorInteractionController is not fully configured.",
                    this);

                enabled = false;
            }
        }


        private void OnEnable()
        {
            if (!enabled)
                return;

            session.CurrentQuestionChanged +=
                HandleQuestionChanged;

            experience.StateChanged +=
                HandleExperienceStateChanged;

            workspace.MeaningfulStateChanged +=
                HandleMeaningfulStateChanged;

            if (session.CurrentQuestion != null)
            {
                ResetForQuestion();
            }

            PublishHelpAvailability();
        }


        private void OnDisable()
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

            if (workspace != null)
            {
                workspace.MeaningfulStateChanged -=
                    HandleMeaningfulStateChanged;
            }

            automaticGeneration++;
            questionGeneration++;

            CancelAutoCheck();
        }


        private void HandleQuestionChanged(
            QuestionDto question)
        {
            ResetForQuestion();
        }


        private void HandleExperienceStateChanged(
            ExperienceState state)
        {
            if (state ==
                ExperienceState.Attempt)
            {
                // Entering Attempt starts a fresh tutoring pass for the
                // current physical construction. This prevents completed
                // signatures and conversation history from a previous
                // attempt suppressing guidance after Exit -> Start again.
                ResetForQuestion();
                return;
            }

            automaticGeneration++;

            CancelAutoCheck();

            PublishHelpAvailability();
        }


        private void ResetForQuestion()
        {
            questionGeneration++;
            automaticGeneration++;
            manualSequence++;

            CancelAutoCheck();

            conversationHistory.Clear();
            inFlightAutoSignatures.Clear();

            tutoringComplete = false;
            manualRequestBusy = false;

            completedStateSignature =
                "";

            lastAutoCompletedStateSignature =
                "";

            automaticHistoryIndex = -1;

            PublishHelpAvailability();
        }


        private void HandleMeaningfulStateChanged(
            string latestAction)
        {
            automaticGeneration++;

            CancelAutoCheck();

            if (experience.CurrentState !=
                ExperienceState.Attempt)
            {
                return;
            }

            if (!workspace.HasMeaningfulAttempt())
            {
                return;
            }

            if (!TryGetCurrentStateSignature(
                    out string stateSignature))
            {
                return;
            }

            if (tutoringComplete &&
                stateSignature !=
                completedStateSignature)
            {
                tutoringComplete = false;

                completedStateSignature =
                    "";

                PublishHelpAvailability();
            }

            if (tutoringComplete)
                return;

            // A manual request already concerns the learner's
            // current work. If they alter that work while the
            // request is being generated, the manual request
            // will regenerate once for the new arrangement.
            if (manualRequestBusy)
                return;

            if (stateSignature ==
                lastAutoCompletedStateSignature)
            {
                return;
            }

            if (inFlightAutoSignatures.Contains(
                    stateSignature))
            {
                return;
            }

            int generation =
                automaticGeneration;

            autoCheckRoutine =
                StartCoroutine(
                    AutoCheckAfterDelay(
                        latestAction,
                        stateSignature,
                        generation));
        }


        private IEnumerator AutoCheckAfterDelay(
            string latestAction,
            string stateSignature,
            int generation)
        {
            yield return
                new WaitForSecondsRealtime(
                    autoCheckDelaySeconds);

            // Voice is a single channel in VR. If the opening
            // explanation or another tutor response is still
            // playing after 3.6 seconds, wait rather than
            // cutting it off.
            while (tutorSpeech.IsSpeaking)
            {
                if (generation !=
                    automaticGeneration)
                {
                    autoCheckRoutine =
                        null;

                    yield break;
                }

                yield return null;
            }

            autoCheckRoutine = null;

            if (generation !=
                automaticGeneration)
            {
                yield break;
            }

            _ =
                RequestAutomaticTutorAsync(
                    latestAction,
                    stateSignature,
                    generation);
        }


        private async Task RequestAutomaticTutorAsync(
            string latestAction,
            string stateSignature,
            int generation)
        {
            if (!TryGetCurrentState(
                    out object learnerState,
                    out string currentSignature))
            {
                return;
            }

            if (currentSignature !=
                stateSignature)
            {
                return;
            }

            if (!inFlightAutoSignatures.Add(
                    stateSignature))
            {
                return;
            }

            QuestionDto question =
                session.CurrentQuestion;

            if (question == null)
            {
                inFlightAutoSignatures.Remove(
                    stateSignature);

                return;
            }

            string questionId =
                question.Id;

            int questionGenerationAtStart =
                questionGeneration;

            int manualSequenceAtStart =
                manualSequence;

            try
            {
                TutorRequestDto request =
                    new TutorRequestDto
                    {
                        QuestionId =
                            questionId,

                        LearnerState =
                            learnerState,

                        SupportType =
                            SupportType.AUTO_CHECK,

                        LatestAction =
                            BuildRequestLatestAction(
                                latestAction),

                        StudentMessage =
                            "",

                        ConversationHistory =
                            GetRecentHistory(),

                        View =
                            workspacePovDebug
                                .CaptureViewSnapshot()
                    };

                TutorResponseDto response =
                    await backendClient
                        .PostTutorAsync(
                            request);

                if (!isActiveAndEnabled)
                    return;

                if (questionGeneration !=
                    questionGenerationAtStart)
                {
                    return;
                }

                if (automaticGeneration !=
                    generation)
                {
                    return;
                }

                if (manualSequence !=
                    manualSequenceAtStart)
                {
                    return;
                }

                if (session.CurrentQuestion?.Id !=
                    questionId)
                {
                    return;
                }

                if (!TryGetCurrentStateSignature(
                        out string latestSignature))
                {
                    return;
                }

                // The backend response describes exactly the
                // arrangement sent in the request. Never speak
                // it after the learner has changed that state.
                if (latestSignature !=
                    stateSignature)
                {
                    return;
                }

                AcceptTutorResponse(
                    response,
                    manual: false,
                    stateSignature);
            }
            catch (Exception exception)
            {
                Debug.LogWarning(
                    $"[MathConstructVR] Automatic tutor request failed.\n" +
                    $"{exception.Message}",
                    this);
            }
            finally
            {
                inFlightAutoSignatures.Remove(
                    stateSignature);
            }
        }


        // Wire SendHint's Button.OnClick to this method.
        // This path sends the SAME POV + learner state frozen by B/Refresh.
        public void RequestTabletHint()
        {
            if (!CanRequestManualHelp)
                return;

            if (helpTablet == null ||
                !helpTablet.TryGetFrozenCapture(
                    out string questionId,
                    out object learnerState,
                    out string workspaceSignature,
                    out ViewDataDto frozenView))
            {
                Debug.LogWarning(
                    "[HelpTablet] No frozen capture. Open tablet with B first.",
                    this);
                return;
            }

            if (!helpTablet.IsCaptureStillValid() ||
                session.CurrentQuestion?.Id != questionId ||
                workspace.GetStateSignature() != workspaceSignature)
            {
                Debug.LogWarning(
                    "[HelpTablet] Workspace changed. Press Refresh before Send Hint.",
                    this);
                return;
            }

            automaticGeneration++;
            manualSequence++;
            CancelAutoCheck();
            tutorSpeech.StopSpeech();

            AddStudentHistory("Can I get a hint?");
            manualRequestBusy = true;
            PublishHelpAvailability();

            _ = RunTabletHintAsync(
                questionId,
                learnerState,
                questionId + "|" + workspaceSignature,
                frozenView,
                manualSequence,
                questionGeneration);
        }

        private async Task RunTabletHintAsync(
            string questionId,
            object frozenLearnerState,
            string frozenSignature,
            ViewDataDto frozenView,
            int sequence,
            int generation)
        {
            try
            {
                TutorRequestDto request = new TutorRequestDto
                {
                    QuestionId = questionId,
                    LearnerState = frozenLearnerState,
                    SupportType = SupportType.HINT,
                    LatestAction = BuildRequestLatestAction(
                        "The student selected the support request: Can I get a hint?"),
                    StudentMessage =
                        "Please give me one small hint based on my work without giving me the answer.",
                    ConversationHistory = GetRecentHistory(),
                    View = frozenView
                };

                // BackendClient updates snapshot_age_ms, not the captured POV.
                TutorResponseDto response = await backendClient.PostTutorAsync(request);

                if (!isActiveAndEnabled ||
                    generation != questionGeneration ||
                    sequence != manualSequence ||
                    experience.CurrentState != ExperienceState.Attempt ||
                    session.CurrentQuestion?.Id != questionId)
                    return;

                if (!TryGetCurrentStateSignature(out string latestSignature) ||
                    latestSignature != frozenSignature)
                {
                    Debug.LogWarning(
                        "[HelpTablet] State changed during request. " +
                        "Discarding stale response; press Refresh and Send Hint again.",
                        this);
                    return;
                }

                // Existing path adds conversation history and speaks through the tutor.
                AcceptTutorResponse(response, manual: true, frozenSignature);
            }
            catch (Exception exception)
            {
                Debug.LogWarning(
                    "[HelpTablet] Send Hint failed: " + exception.Message,
                    this);
            }
            finally
            {
                if (generation == questionGeneration &&
                    sequence == manualSequence)
                {
                    manualRequestBusy = false;
                    PublishHelpAvailability();
                }
            }
        }


        public void RequestManualSupport(
            SupportType supportType,
            string visibleChoice,
            string studentMessage)
        {
            if (!CanRequestManualHelp)
                return;

            if (!TryGetCurrentState(
                    out _,
                    out _))
            {
                Debug.LogWarning(
                    "[MathConstructVR] Current workspace does not " +
                    "yet expose a learner state for tutoring.",
                    this);

                return;
            }

            automaticGeneration++;
            manualSequence++;

            CancelAutoCheck();

            // Requested help supersedes any tutor statement
            // currently being spoken.
            tutorSpeech.StopSpeech();

            AddStudentHistory(
                visibleChoice);

            manualRequestBusy = true;

            PublishHelpAvailability();

            int sequence =
                manualSequence;

            int currentQuestionGeneration =
                questionGeneration;

            _ =
                RunManualSupportAsync(
                    supportType,
                    visibleChoice,
                    studentMessage,
                    sequence,
                    currentQuestionGeneration);
        }


        private async Task RunManualSupportAsync(
            SupportType supportType,
            string visibleChoice,
            string studentMessage,
            int sequence,
            int generation)
        {
            try
            {
                // Exactly like the web implementation, one
                // manual request may regenerate once if the
                // learner changes the arrangement while the
                // backend is thinking.
                for (int attempt = 0;
                     attempt < 2;
                     attempt++)
                {
                    QuestionDto question =
                        session.CurrentQuestion;

                    if (question == null)
                        return;

                    string questionId =
                        question.Id;

                    if (!TryGetCurrentState(
                            out object learnerState,
                            out string stateSignature))
                    {
                        return;
                    }

                    TutorRequestDto request =
                        new TutorRequestDto
                        {
                            QuestionId =
                                questionId,

                            LearnerState =
                                learnerState,

                            SupportType =
                                supportType,

                            LatestAction =
                                BuildRequestLatestAction(
                                    $"The student selected the support request: " +
                                    $"{visibleChoice}."),

                            StudentMessage =
                                studentMessage,

                            ConversationHistory =
                                GetRecentHistory(),

                            View =
                                workspacePovDebug
                                    .CaptureViewSnapshot()
                        };

                    TutorResponseDto response =
                        await backendClient
                            .PostTutorAsync(
                                request);

                    if (!isActiveAndEnabled)
                        return;

                    if (questionGeneration !=
                        generation)
                    {
                        return;
                    }

                    if (manualSequence !=
                        sequence)
                    {
                        return;
                    }

                    if (session.CurrentQuestion?.Id !=
                        questionId)
                    {
                        return;
                    }

                    if (!TryGetCurrentStateSignature(
                            out string latestSignature))
                    {
                        return;
                    }

                    if (latestSignature !=
                        stateSignature)
                    {
                        if (attempt == 0)
                        {
                            continue;
                        }

                        return;
                    }

                    AcceptTutorResponse(
                        response,
                        manual: true,
                        stateSignature);

                    return;
                }
            }
            catch (Exception exception)
            {
                Debug.LogWarning(
                    $"[MathConstructVR] Manual tutor request failed.\n" +
                    $"{exception.Message}",
                    this);
            }
            finally
            {
                if (questionGeneration ==
                        generation &&
                    manualSequence ==
                        sequence)
                {
                    manualRequestBusy = false;

                    PublishHelpAvailability();
                }
            }
        }


        private void AcceptTutorResponse(
            TutorResponseDto response,
            bool manual,
            string stateSignature)
        {
            if (response == null)
                return;

            string text =
                workspace.AdaptTutorResponse(
                    response.TutorResponse?.Trim());

            if (!string.IsNullOrWhiteSpace(
                    text))
            {
                if (manual)
                {
                    AppendTutorHistory(
                        text);
                }
                else
                {
                    UpdateAutomaticHistory(
                        text);

                    lastAutoCompletedStateSignature =
                        stateSignature;
                }

                tutorSpeech.Speak(
                    text);
            }

            bool correct =
                response.StudentCorrect ||
                string.Equals(
                    response.ConversationStatus,
                    "correct",
                    StringComparison.OrdinalIgnoreCase);

            if (correct)
            {
                MarkTutoringComplete(
                    stateSignature);
            }
        }


        private void MarkTutoringComplete(
            string stateSignature)
        {
            tutoringComplete = true;

            completedStateSignature =
                stateSignature;

            automaticGeneration++;

            CancelAutoCheck();

            PublishHelpAvailability();

            Debug.Log(
                "[MathConstructVR] Tutor verified the current " +
                "construction as correct.");
        }


        public void CancelAutomaticGuidanceForLocalHelp()
        {
            automaticGeneration++;

            CancelAutoCheck();
        }


        private void CancelAutoCheck()
        {
            if (autoCheckRoutine == null)
                return;

            StopCoroutine(
                autoCheckRoutine);

            autoCheckRoutine = null;
        }


        private string BuildRequestLatestAction(
            string latestAction)
        {
            string context =
                workspace.GetTutorContext();

            if (string.IsNullOrWhiteSpace(context))
                return latestAction ?? "";

            if (string.IsNullOrWhiteSpace(latestAction))
                return context;

            return
                $"{latestAction} {context}";
        }


        private bool TryGetCurrentState(
            out object learnerState,
            out string signature)
        {
            signature = "";

            if (!workspace.TryGetLearnerState(
                    out learnerState))
            {
                return false;
            }

            QuestionDto question =
                session.CurrentQuestion;

            if (question == null)
                return false;

            signature =
                $"{question.Id}|{workspace.GetStateSignature()}";

            return true;
        }


        private bool TryGetCurrentStateSignature(
            out string signature)
        {
            return TryGetCurrentState(
                out _,
                out signature);
        }


        private void AddStudentHistory(
            string content)
        {
            if (string.IsNullOrWhiteSpace(
                    content))
            {
                return;
            }

            conversationHistory.Add(
                new ConversationMessageDto
                {
                    Role =
                        "student",

                    Content =
                        content
                });

            automaticHistoryIndex =
                -1;

            TrimHistory();
        }


        private void AppendTutorHistory(
            string content)
        {
            conversationHistory.Add(
                new ConversationMessageDto
                {
                    Role =
                        "tutor",

                    Content =
                        content
                });

            automaticHistoryIndex =
                -1;

            TrimHistory();
        }


        private void UpdateAutomaticHistory(
            string content)
        {
            if (automaticHistoryIndex >= 0 &&
                automaticHistoryIndex <
                conversationHistory.Count &&
                conversationHistory[
                    automaticHistoryIndex]
                    .Role ==
                "tutor")
            {
                conversationHistory[
                    automaticHistoryIndex] =
                    new ConversationMessageDto
                    {
                        Role =
                            "tutor",

                        Content =
                            content
                    };
            }
            else
            {
                conversationHistory.Add(
                    new ConversationMessageDto
                    {
                        Role =
                            "tutor",

                        Content =
                            content
                    });

                automaticHistoryIndex =
                    conversationHistory.Count - 1;
            }

            TrimHistory();
        }


        private void TrimHistory()
        {
            if (conversationHistory.Count <=
                MaxHistoryCount)
            {
                return;
            }

            int removeCount =
                conversationHistory.Count -
                MaxHistoryCount;

            conversationHistory.RemoveRange(
                0,
                removeCount);

            if (automaticHistoryIndex >= 0)
            {
                automaticHistoryIndex -=
                    removeCount;

                if (automaticHistoryIndex < 0)
                {
                    automaticHistoryIndex =
                        -1;
                }
            }
        }


        private ConversationMessageDto[]
            GetRecentHistory()
        {
            int skip =
                Mathf.Max(
                    0,
                    conversationHistory.Count -
                    HistorySentToBackend);

            return conversationHistory
                .Skip(skip)
                .Select(
                    message =>
                        new ConversationMessageDto
                        {
                            Role =
                                message.Role,

                            Content =
                                message.Content
                        })
                .ToArray();
        }


        private void PublishHelpAvailability()
        {
            HelpAvailabilityChanged?.Invoke(
                CanRequestManualHelp);
        }
    }
}