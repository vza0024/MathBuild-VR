using Unity.XR.CoreUtils;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class AttemptViewController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField]
        private ExperienceController experienceController;

        [SerializeField]
        private XROrigin xrOrigin;

        [SerializeField]
        private Transform attemptViewAnchor;


        [Header("Position Lock")]
        [SerializeField, Min(0f)]
        private float allowedHorizontalRadius = 0f;


        private bool positionLocked;

        private Vector3 lockedCameraWorldPosition;


        private void OnEnable()
        {
            if (experienceController != null)
            {
                experienceController.StateChanged += OnStateChanged;
            }
        }


        private void OnDisable()
        {
            if (experienceController != null)
            {
                experienceController.StateChanged -= OnStateChanged;
            }
        }


        private void LateUpdate()
        {
            if (!positionLocked)
                return;

            if (xrOrigin == null || xrOrigin.Camera == null)
                return;

            LockHorizontalPosition();
        }


        private void OnStateChanged(ExperienceState state)
        {
            switch (state)
            {
                case ExperienceState.Attempt:
                    EnterAttemptView();
                    break;

                case ExperienceState.Exploration:
                    ExitAttemptView();
                    break;
            }
        }


        private void EnterAttemptView()
        {
            if (xrOrigin == null ||
                xrOrigin.Camera == null ||
                attemptViewAnchor == null)
            {
                Debug.LogError(
                    "[MathConstructVR] Attempt view is not configured.");

                return;
            }

            Camera xrCamera = xrOrigin.Camera;


            // Move horizontally to the Attempt anchor,
            // while preserving the learner's tracked height.
            Vector3 targetPosition = attemptViewAnchor.position;

            targetPosition.y =
                xrCamera.transform.position.y;

            xrOrigin.MoveCameraToWorldLocation(
                targetPosition);


            // Rotate the XR Origin so the learner's
            // neutral forward direction faces the board.
            Vector3 currentForward =
                Vector3.ProjectOnPlane(
                    xrCamera.transform.forward,
                    Vector3.up).normalized;

            Vector3 desiredForward =
                Vector3.ProjectOnPlane(
                    attemptViewAnchor.forward,
                    Vector3.up).normalized;

            if (currentForward.sqrMagnitude > 0.001f &&
                desiredForward.sqrMagnitude > 0.001f)
            {
                float yaw =
                    Vector3.SignedAngle(
                        currentForward,
                        desiredForward,
                        Vector3.up);

                xrOrigin.RotateAroundCameraUsingOriginUp(
                    yaw);
            }


            // Record the camera position AFTER recentering.
            lockedCameraWorldPosition =
                xrCamera.transform.position;

            positionLocked = true;


            Debug.Log(
                "[MathConstructVR] Attempt position locked.");
        }


        private void ExitAttemptView()
        {
            positionLocked = false;

            Debug.Log(
                "[MathConstructVR] Attempt position unlocked.");
        }


        private void LockHorizontalPosition()
        {
            Vector3 cameraPosition =
                xrOrigin.Camera.transform.position;


            Vector2 lockedPosition =
                new Vector2(
                    lockedCameraWorldPosition.x,
                    lockedCameraWorldPosition.z);

            Vector2 currentPosition =
                new Vector2(
                    cameraPosition.x,
                    cameraPosition.z);


            Vector2 offset =
                currentPosition - lockedPosition;

            float distance =
                offset.magnitude;


            if (distance <= allowedHorizontalRadius)
                return;


            Vector2 permittedPosition;

            if (allowedHorizontalRadius <= 0f)
            {
                permittedPosition = lockedPosition;
            }
            else
            {
                permittedPosition =
                    lockedPosition +
                    offset.normalized *
                    allowedHorizontalRadius;
            }


            Vector3 correction =
                new Vector3(
                    permittedPosition.x - cameraPosition.x,
                    0f,
                    permittedPosition.y - cameraPosition.z);


            xrOrigin.transform.position += correction;
        }
    }
}