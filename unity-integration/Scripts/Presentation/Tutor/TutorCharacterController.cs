using System.Collections;
using UnityEngine;

namespace MathConstructVR.Presentation.Tutor
{
    public sealed class TutorCharacterController : MonoBehaviour
    {
        [Header("Animation")]
        [SerializeField]
        private Animator animator;

        [Header("Startup Greeting")]
        [Min(0f)]
        [SerializeField]
        private float greetingDelaySeconds = 1f;

        private static readonly int GreetingTrigger =
            Animator.StringToHash("Greeting");

        private Coroutine greetingRoutine;


        private void Start()
        {
            if (animator == null)
            {
                Debug.LogError(
                    "[MathConstructVR] TutorCharacterController has no Animator assigned.",
                    this);

                return;
            }

            greetingRoutine = StartCoroutine(PlayStartupGreeting());
        }


        private IEnumerator PlayStartupGreeting()
        {
            yield return new WaitForSecondsRealtime(
                greetingDelaySeconds);

            animator.SetTrigger(GreetingTrigger);

            greetingRoutine = null;
        }


        private void OnDisable()
        {
            if (greetingRoutine != null)
            {
                StopCoroutine(greetingRoutine);
                greetingRoutine = null;
            }
        }
    }
}