using System.Collections;
using UnityEngine;
using UnityEngine.XR.Interaction.Toolkit;
using UnityEngine.XR.Interaction.Toolkit.Interactables;

namespace MathConstructVR.Core
{
    [RequireComponent(typeof(Rigidbody))]
    [RequireComponent(typeof(XRGrabInteractable))]
    public sealed class ManipulativeObject : MonoBehaviour
    {
        [SerializeField]
        private float snapDuration = 0.15f;

        [SerializeField]
        [Min(0f)]
        private float surfaceClearance = 0.006f;

        private Rigidbody body;

        private XRGrabInteractable grabInteractable;

        private WorkspaceController workspaceController;

        private Coroutine snapRoutine;

        private ManipulativeSupplyController supplyController;
        private ManipulativeSourceSlot sourceSlot = ManipulativeSourceSlot.None;

        private bool hasLoosePlacement;
        private Vector3 loosePlacementPosition;
        private Quaternion loosePlacementRotation;

        private int trayReturnSlotIndex = -1;


        public WorkspaceRegion CurrentRegion
        {
            get;
            private set;
        }

        public int CurrentSlotIndex
        {
            get;
            private set;
        } = -1;

        public bool IsLocked
        {
            get;
            private set;
        }

        public bool IsPrinterSourceObject =>
            sourceSlot != ManipulativeSourceSlot.None;

        public VisualRole SemanticVisualRole
        {
            get;
            private set;
        } = VisualRole.Object;


        public bool IsBeingGrabbed =>
            grabInteractable != null &&
            grabInteractable.isSelected;


        private void Awake()
        {
            EnsureReferences();
        }


        private void EnsureReferences()
        {
            if (body == null)
            {
                body =
                    GetComponent<Rigidbody>();
            }

            if (grabInteractable == null)
            {
                grabInteractable =
                    GetComponent<XRGrabInteractable>();
            }
        }


        private void OnEnable()
        {
            EnsureReferences();

            if (grabInteractable == null)
                return;

            grabInteractable.selectEntered.AddListener(
                HandleGrabStarted);

            grabInteractable.selectExited.AddListener(
                HandleGrabEnded);
        }


        private void OnDisable()
        {
            if (grabInteractable == null)
                return;

            grabInteractable.selectEntered.RemoveListener(
                HandleGrabStarted);

            grabInteractable.selectExited.RemoveListener(
                HandleGrabEnded);
        }


        public void Initialize(
            WorkspaceController controller,
            WorkspaceRegion region,
            int slotIndex,
            bool locked)
        {
            EnsureReferences();

            workspaceController =
                controller;

            supplyController = null;
            sourceSlot = ManipulativeSourceSlot.None;
            trayReturnSlotIndex = -1;
            SemanticVisualRole = VisualRole.Object;

            CurrentRegion =
                region;

            CurrentSlotIndex =
                slotIndex;

            hasLoosePlacement = false;

            IsLocked =
                locked;

            StopSnap();
            LockPhysics();

            transform.SetPositionAndRotation(
                GetRegionSnapPosition(
                    region,
                    slotIndex),
                region.GetSlotWorldRotation());

            if (grabInteractable != null)
            {
                grabInteractable.enabled =
                    !IsLocked;
            }
        }


        public void InitializeSupplySource(
            WorkspaceController controller,
            ManipulativeSupplyController supply,
            ManipulativeSourceSlot slot,
            VisualRole visualRole,
            Vector3 worldPosition,
            Quaternion worldRotation)
        {
            EnsureReferences();

            workspaceController = controller;
            supplyController = supply;
            sourceSlot = slot;
            trayReturnSlotIndex = -1;
            SemanticVisualRole = visualRole;

            CurrentRegion = null;
            CurrentSlotIndex = -1;
            hasLoosePlacement = false;
            IsLocked = false;

            StopSnap();
            LockPhysics();

            transform.SetPositionAndRotation(
                worldPosition,
                worldRotation);

            if (grabInteractable != null)
            {
                grabInteractable.enabled = true;
            }
        }


        public void CommitPlacement(
            WorkspaceRegion region,
            int slotIndex)
        {
            if (IsLocked)
                return;

            if (trayReturnSlotIndex >= 0)
            {
                supplyController?.ReleaseReturnedSlot(
                    this);

                trayReturnSlotIndex = -1;
                supplyController = null;
            }

            CurrentRegion =
                region;

            CurrentSlotIndex =
                slotIndex;

            hasLoosePlacement = false;

            BeginSnap(
                GetRegionSnapPosition(
                    region,
                    slotIndex),
                region.GetSlotWorldRotation());
        }


        internal void UpdatePlacementReference(
            WorkspaceRegion region,
            int slotIndex)
        {
            CurrentRegion = region;
            CurrentSlotIndex = slotIndex;
            hasLoosePlacement = false;
        }


        public void CommitLoosePlacement(
            Vector3 worldPosition,
            Quaternion worldRotation)
        {
            if (IsLocked)
                return;

            CurrentRegion = null;
            CurrentSlotIndex = -1;

            hasLoosePlacement = true;
            loosePlacementPosition = worldPosition;
            loosePlacementRotation = worldRotation;

            BeginSnap(
                loosePlacementPosition,
                loosePlacementRotation);
        }


        public void CommitTrayPlacement(
            ManipulativeSupplyController supply,
            int slotIndex,
            Vector3 traySurfacePosition,
            Quaternion trayRotation,
            Vector3 trayUp)
        {
            if (IsLocked)
                return;

            supplyController = supply;
            sourceSlot = ManipulativeSourceSlot.None;
            trayReturnSlotIndex = slotIndex;

            CurrentRegion = null;
            CurrentSlotIndex = -1;

            hasLoosePlacement = true;

            float lift =
                GetVisualBottomOffset() +
                surfaceClearance;

            loosePlacementPosition =
                traySurfacePosition +
                (trayUp.normalized * lift);

            loosePlacementRotation =
                trayRotation;

            BeginSnap(
                loosePlacementPosition,
                loosePlacementRotation);
        }


        public void ReturnToCurrentPlacement()
        {
            if (CurrentRegion != null &&
                CurrentSlotIndex >= 0)
            {
                BeginSnap(
                    GetRegionSnapPosition(
                        CurrentRegion,
                        CurrentSlotIndex),
                    CurrentRegion.GetSlotWorldRotation());

                return;
            }

            if (hasLoosePlacement)
            {
                BeginSnap(
                    loosePlacementPosition,
                    loosePlacementRotation);
            }
        }


        private Vector3 GetRegionSnapPosition(
            WorkspaceRegion region,
            int slotIndex)
        {
            Vector3 surfacePosition =
                region.GetSlotWorldPosition(
                    slotIndex);

            float lift =
                GetVisualBottomOffset() +
                surfaceClearance;

            return
                surfacePosition +
                (region.transform.up * lift);
        }


        private float GetVisualBottomOffset()
        {
            Renderer[] renderers =
                GetComponentsInChildren<Renderer>(
                    includeInactive: true);

            if (renderers == null ||
                renderers.Length == 0)
            {
                return 0f;
            }

            float minimumLocalY =
                float.PositiveInfinity;

            foreach (Renderer renderer in renderers)
            {
                if (renderer == null)
                    continue;

                Bounds bounds =
                    renderer.localBounds;

                Vector3 center =
                    bounds.center;

                Vector3 extents =
                    bounds.extents;

                for (int x = -1; x <= 1; x += 2)
                {
                    for (int y = -1; y <= 1; y += 2)
                    {
                        for (int z = -1; z <= 1; z += 2)
                        {
                            Vector3 rendererLocalCorner =
                                center +
                                Vector3.Scale(
                                    extents,
                                    new Vector3(
                                        x,
                                        y,
                                        z));

                            Vector3 worldCorner =
                                renderer.transform.TransformPoint(
                                    rendererLocalCorner);

                            Vector3 rootLocalCorner =
                                transform.InverseTransformPoint(
                                    worldCorner);

                            minimumLocalY =
                                Mathf.Min(
                                    minimumLocalY,
                                    rootLocalCorner.y);
                        }
                    }
                }
            }

            if (float.IsPositiveInfinity(
                    minimumLocalY))
            {
                return 0f;
            }

            return
                Mathf.Max(
                    0f,
                    -minimumLocalY);
        }


        private void HandleGrabStarted(
            SelectEnterEventArgs args)
        {
            if (IsLocked)
                return;

            StopSnap();

            if (sourceSlot != ManipulativeSourceSlot.None)
            {
                ManipulativeSourceSlot grabbedSlot = sourceSlot;
                ManipulativeSupplyController sourceController = supplyController;

                sourceSlot = ManipulativeSourceSlot.None;
                supplyController = null;

                sourceController?.HandleSourceGrabbed(
                    this,
                    grabbedSlot);
            }

            body.isKinematic = false;
            body.useGravity = false;

            body.linearVelocity =
                Vector3.zero;

            body.angularVelocity =
                Vector3.zero;
        }


        private void HandleGrabEnded(
            SelectExitEventArgs args)
        {
            if (IsLocked)
                return;

            body.linearVelocity =
                Vector3.zero;

            body.angularVelocity =
                Vector3.zero;

            LockPhysics();

            if (workspaceController == null)
            {
                Debug.LogError(
                    $"[MathConstructVR] Manipulative '{name}' " +
                    $"has no WorkspaceController.");

                return;
            }

            workspaceController
                .HandleManipulativeReleased(
                    this,
                    transform.position);
        }


        private void BeginSnap(
            Vector3 targetPosition,
            Quaternion targetRotation)
        {
            StopSnap();
            LockPhysics();

            // Workspace content is intentionally rebuilt while AttemptContent
            // is hidden. Unity cannot start a coroutine on an inactive object,
            // so hidden objects must take the final placement immediately.
            if (!gameObject.activeInHierarchy ||
                !isActiveAndEnabled ||
                snapDuration <= 0f)
            {
                transform.SetPositionAndRotation(
                    targetPosition,
                    targetRotation);

                snapRoutine = null;
                return;
            }

            snapRoutine =
                StartCoroutine(
                    SnapRoutine(
                        targetPosition,
                        targetRotation));
        }


        private IEnumerator SnapRoutine(
            Vector3 targetPosition,
            Quaternion targetRotation)
        {
            Vector3 startPosition =
                transform.position;

            Quaternion startRotation =
                transform.rotation;

            float elapsed = 0f;

            while (elapsed < snapDuration)
            {
                elapsed +=
                    Time.deltaTime;

                float normalizedTime =
                    Mathf.Clamp01(
                        elapsed /
                        snapDuration);

                float easedTime =
                    Mathf.SmoothStep(
                        0f,
                        1f,
                        normalizedTime);

                transform.position =
                    Vector3.Lerp(
                        startPosition,
                        targetPosition,
                        easedTime);

                transform.rotation =
                    Quaternion.Slerp(
                        startRotation,
                        targetRotation,
                        easedTime);

                yield return null;
            }

            transform.SetPositionAndRotation(
                targetPosition,
                targetRotation);

            snapRoutine = null;
        }


        private void LockPhysics()
        {
            body.linearVelocity =
                Vector3.zero;

            body.angularVelocity =
                Vector3.zero;

            body.useGravity = false;
            body.isKinematic = true;
        }


        private void StopSnap()
        {
            if (snapRoutine == null)
                return;

            StopCoroutine(
                snapRoutine);

            snapRoutine = null;
        }
    }
}