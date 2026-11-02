using System;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class ExperienceController : MonoBehaviour
    {
        [Header("State Roots")]
        [SerializeField]
        private GameObject explorationContent;

        [SerializeField]
        private GameObject attemptContent;

        [Header("Transition Protection")]
        [Tooltip("Minimum time between Exploration/Attempt state transitions.")]
        [Min(0f)]
        [SerializeField]
        private float transitionCooldownSeconds = 0.75f;

        private float nextTransitionAllowedTime;

        public ExperienceState CurrentState { get; private set; }

        public event Action<ExperienceState> StateChanged;


        public void Initialize()
        {
            // Initial state should not be blocked by the transition cooldown.
            ApplyState(ExperienceState.Exploration);
            nextTransitionAllowedTime = 0f;
        }


        public void BeginAttempt()
        {
            if (CurrentState != ExperienceState.Exploration)
                return;

            if (IsTransitionLocked())
                return;

            TransitionTo(ExperienceState.Attempt);
        }


        public void ReturnToExploration()
        {
            if (CurrentState == ExperienceState.Exploration)
                return;

            if (IsTransitionLocked())
                return;

            TransitionTo(ExperienceState.Exploration);
        }


        private void TransitionTo(ExperienceState newState)
        {
            ApplyState(newState);

            nextTransitionAllowedTime =
                Time.unscaledTime + transitionCooldownSeconds;
        }


        private bool IsTransitionLocked()
        {
            return Time.unscaledTime < nextTransitionAllowedTime;
        }


        private void ApplyState(ExperienceState newState)
        {
            CurrentState = newState;

            if (explorationContent != null)
            {
                explorationContent.SetActive(
                    newState == ExperienceState.Exploration);
            }

            if (attemptContent != null)
            {
                attemptContent.SetActive(
                    newState == ExperienceState.Attempt);
            }

            StateChanged?.Invoke(newState);

            Debug.Log(
                $"[MathConstructVR] Experience state → {newState}");
        }
    }
}