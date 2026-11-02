using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace MathConstructVR.UI
{
    [RequireComponent(typeof(Button))]
    public sealed class ButtonCooldown : MonoBehaviour
    {
        [Header("Cooldown")]
        [Min(0f)]
        [SerializeField]
        private float cooldownSeconds = 0.5f;

        [Header("Action")]
        [SerializeField]
        private UnityEvent onAcceptedClick;

        private float nextAllowedTime;
        private bool externallyLocked;


        public bool IsLocked =>
            externallyLocked ||
            Time.unscaledTime < nextAllowedTime;


        public void TryInvoke()
        {
            if (IsLocked)
                return;

            nextAllowedTime =
                Time.unscaledTime +
                cooldownSeconds;

            onAcceptedClick?.Invoke();
        }


        public void SetLocked(bool locked)
        {
            externallyLocked = locked;
        }
    }
}