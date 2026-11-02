using System;
using System.Collections;
using System.Collections.Generic;
using MathConstructVR.Networking.DTOs;
using UnityEngine;

namespace MathConstructVR.Core
{
    public enum ManipulativeSourceSlot
    {
        None = 0,
        SourceA = 1,
        SourceB = 2
    }

    public sealed class ManipulativeSupplyController : MonoBehaviour
    {
        [Header("Printer")]
        [SerializeField]
        private Animator printerAnimator;

        [SerializeField]
        private string printTriggerName = "Print";

        [SerializeField]
        private string idleStateName = "Idle";

        [Header("Tray Source Points")]
        [SerializeField]
        private Transform sourceA;

        [SerializeField]
        private Transform sourceB;

        [Header("Tray Return Area")]
        [SerializeField]
        private BoxCollider returnArea;

        [Range(1, 8)]
        [SerializeField]
        private int returnSlotCount = 3;

        [Range(0.4f, 0.95f)]
        [SerializeField]
        private float returnSlotSpanFraction = 0.72f;

        [Header("Safety")]
        [Min(1f)]
        [SerializeField]
        private float animationTimeoutSeconds = 10f;

        private readonly Queue<ManipulativeSourceSlot> printQueue = new();

        private readonly Dictionary<ManipulativeObject, int> returnedSlots =
            new();

        private WorkspaceController workspaceController;
        private VisualAssetCatalog visualAssetCatalog;
        private Transform generatedObjectsParent;

        private SourceState sourceAState;
        private SourceState sourceBState;
        private Coroutine queueRoutine;
        private bool initialized;

        private sealed class SourceState
        {
            public Transform Anchor;
            public GameObject Prefab;
            public VisualRole Role;
            public ManipulativeObject CurrentObject;
            public bool Enabled;
            public bool ReplacementPending;
        }

        public void Initialize(
            WorkspaceController controller,
            VisualAssetCatalog catalog,
            Transform generatedParent)
        {
            if (initialized)
                return;

            workspaceController =
                controller != null
                    ? controller
                    : throw new ArgumentNullException(
                        nameof(controller));

            visualAssetCatalog =
                catalog != null
                    ? catalog
                    : throw new ArgumentNullException(
                        nameof(catalog));

            generatedObjectsParent =
                generatedParent != null
                    ? generatedParent
                    : throw new ArgumentNullException(
                        nameof(generatedParent));

            if (printerAnimator == null)
            {
                throw new InvalidOperationException(
                    "ManipulativeSupplyController requires the Printer Animator.");
            }

            if (sourceA == null ||
                sourceB == null)
            {
                throw new InvalidOperationException(
                    "ManipulativeSupplyController requires SourceA and SourceB transforms.");
            }

            if (returnArea == null)
            {
                Transform returnAreaTransform =
                    transform.Find("ReturnArea");

                if (returnAreaTransform != null)
                {
                    returnArea =
                        returnAreaTransform.GetComponent<BoxCollider>();
                }
            }

            if (returnArea == null)
            {
                Debug.LogWarning(
                    "[MathConstructVR] SupplyRoot has no ReturnArea BoxCollider. " +
                    "Objects will snap back to their mathematical region instead of being returnable to the tray.",
                    this);
            }

            sourceAState =
                new SourceState
                {
                    Anchor = sourceA
                };

            sourceBState =
                new SourceState
                {
                    Anchor = sourceB
                };

            initialized = true;
        }

        public void ConfigureForJoin(
            QuestionDto question)
        {
            if (!initialized)
            {
                throw new InvalidOperationException(
                    "ManipulativeSupplyController must be initialized before use.");
            }

            if (question == null)
            {
                throw new ArgumentNullException(
                    nameof(question));
            }

            ResetSupply();

            string initialSemanticKey =
                GetSemanticObjectKey(
                    question,
                    VisualRole.Initial);

            string changeSemanticKey =
                GetSemanticObjectKey(
                    question,
                    VisualRole.Change);

            bool needsSecondSource =
                !string.Equals(
                    initialSemanticKey,
                    changeSemanticKey,
                    StringComparison.OrdinalIgnoreCase);

            GameObject initialPrefab =
                visualAssetCatalog.Resolve(
                    question,
                    VisualRole.Initial);

            GameObject changePrefab =
                visualAssetCatalog.Resolve(
                    question,
                    VisualRole.Change);

            ConfigureSource(
                sourceAState,
                initialPrefab,
                VisualRole.Initial,
                enabled: true);

            ConfigureSource(
                sourceBState,
                changePrefab,
                VisualRole.Change,
                enabled: needsSecondSource);

            SpawnReplacement(
                ManipulativeSourceSlot.SourceA,
                sourceAState);

            if (needsSecondSource)
            {
                SpawnReplacement(
                    ManipulativeSourceSlot.SourceB,
                    sourceBState);
            }
        }

        public void ConfigureForEqualGroups(
            QuestionDto question)
        {
            if (!initialized)
            {
                throw new InvalidOperationException(
                    "ManipulativeSupplyController must be initialized before use.");
            }

            if (question == null)
            {
                throw new ArgumentNullException(
                    nameof(question));
            }

            ResetSupply();

            GameObject objectPrefab =
                visualAssetCatalog.Resolve(
                    question,
                    VisualRole.Object);

            ConfigureSource(
                sourceAState,
                objectPrefab,
                VisualRole.Object,
                enabled: true);

            ConfigureSource(
                sourceBState,
                prefab: null,
                VisualRole.Object,
                enabled: false);

            SpawnReplacement(
                ManipulativeSourceSlot.SourceA,
                sourceAState);
        }


        public void ResetSupply()
        {
            printQueue.Clear();
            returnedSlots.Clear();

            if (queueRoutine != null)
            {
                StopCoroutine(
                    queueRoutine);

                queueRoutine = null;
            }

            ResetSourceState(
                sourceAState);

            ResetSourceState(
                sourceBState);

            if (!AnimatorIsUsable())
                return;

            printerAnimator.ResetTrigger(
                printTriggerName);

            if (string.IsNullOrWhiteSpace(
                    idleStateName))
            {
                return;
            }

            printerAnimator.Play(
                idleStateName,
                0,
                0f);

            printerAnimator.Update(
                0f);
        }

        public bool IsInsideActiveReturnArea(
            Vector3 worldPosition)
        {
            bool supplyActive =
                (sourceAState != null && sourceAState.Enabled) ||
                (sourceBState != null && sourceBState.Enabled);

            if (!initialized ||
                !supplyActive ||
                returnArea == null ||
                !returnArea.gameObject.activeInHierarchy)
            {
                return false;
            }

            // Treat ReturnArea as a 2D tray footprint. We intentionally do
            // not require the object's pivot to be inside the collider's Y
            // thickness, because XR grab pivots can sit above the tray.
            Vector3 localPoint =
                returnArea.transform.InverseTransformPoint(
                    worldPosition);

            Vector3 center =
                returnArea.center;

            Vector3 halfSize =
                returnArea.size * 0.5f;

            return
                localPoint.x >= center.x - halfSize.x &&
                localPoint.x <= center.x + halfSize.x &&
                localPoint.z >= center.z - halfSize.z &&
                localPoint.z <= center.z + halfSize.z;
        }


        public bool TryReserveReturnSlot(
            ManipulativeObject manipulative,
            out int slotIndex,
            out Vector3 traySurfacePosition,
            out Quaternion trayRotation,
            out Vector3 trayUp)
        {
            slotIndex = -1;
            traySurfacePosition = Vector3.zero;
            trayRotation = Quaternion.identity;
            trayUp = Vector3.up;

            if (manipulative == null ||
                returnArea == null ||
                returnSlotCount <= 0)
            {
                return false;
            }

            if (returnedSlots.TryGetValue(
                    manipulative,
                    out int existingSlot))
            {
                slotIndex = existingSlot;
                GetReturnSlotPose(
                    slotIndex,
                    out traySurfacePosition,
                    out trayRotation,
                    out trayUp);

                return true;
            }

            bool[] occupied =
                new bool[returnSlotCount];

            List<ManipulativeObject> stale =
                null;

            foreach (KeyValuePair<ManipulativeObject, int> entry
                     in returnedSlots)
            {
                if (entry.Key == null)
                {
                    stale ??=
                        new List<ManipulativeObject>();

                    stale.Add(
                        entry.Key);

                    continue;
                }

                if (entry.Value >= 0 &&
                    entry.Value < occupied.Length)
                {
                    occupied[entry.Value] = true;
                }
            }

            if (stale != null)
            {
                foreach (ManipulativeObject staleObject in stale)
                {
                    returnedSlots.Remove(
                        staleObject);
                }
            }

            for (int index = 0;
                 index < occupied.Length;
                 index++)
            {
                if (occupied[index])
                    continue;

                returnedSlots[manipulative] =
                    index;

                slotIndex =
                    index;

                GetReturnSlotPose(
                    slotIndex,
                    out traySurfacePosition,
                    out trayRotation,
                    out trayUp);

                return true;
            }

            return false;
        }


        internal void ReleaseReturnedSlot(
            ManipulativeObject manipulative)
        {
            if (manipulative == null)
                return;

            returnedSlots.Remove(
                manipulative);
        }


        private void GetReturnSlotPose(
            int slotIndex,
            out Vector3 traySurfacePosition,
            out Quaternion trayRotation,
            out Vector3 trayUp)
        {
            Vector3 center =
                returnArea.center;

            Vector3 size =
                returnArea.size;

            float normalized =
                returnSlotCount <= 1
                    ? 0f
                    : ((float)slotIndex /
                       (returnSlotCount - 1)) - 0.5f;

            Vector3 localPosition =
                center;

            if (size.x >= size.z)
            {
                localPosition.x +=
                    normalized *
                    size.x *
                    returnSlotSpanFraction;
            }
            else
            {
                localPosition.z +=
                    normalized *
                    size.z *
                    returnSlotSpanFraction;
            }

            // Top surface of the ReturnArea collider.
            localPosition.y =
                center.y +
                (size.y * 0.5f);

            traySurfacePosition =
                returnArea.transform.TransformPoint(
                    localPosition);

            trayRotation =
                returnArea.transform.rotation;

            trayUp =
                returnArea.transform.up;
        }


        internal void HandleSourceGrabbed(
            ManipulativeObject manipulative,
            ManipulativeSourceSlot slot)
        {
            if (!initialized ||
                manipulative == null)
            {
                return;
            }

            SourceState state =
                GetSourceState(
                    slot);

            if (state == null ||
                !state.Enabled ||
                state.ReplacementPending ||
                state.CurrentObject != manipulative)
            {
                return;
            }

            state.CurrentObject = null;
            state.ReplacementPending = true;

            printQueue.Enqueue(
                slot);

            if (queueRoutine == null)
            {
                queueRoutine =
                    StartCoroutine(
                        ProcessPrintQueue());
            }
        }

        private IEnumerator ProcessPrintQueue()
        {
            while (printQueue.Count > 0)
            {
                ManipulativeSourceSlot slot =
                    printQueue.Dequeue();

                SourceState state =
                    GetSourceState(
                        slot);

                if (state == null ||
                    !state.Enabled)
                {
                    continue;
                }

                yield return
                    PlayOnePrintCycle();

                if (state.Enabled &&
                    state.ReplacementPending &&
                    state.CurrentObject == null)
                {
                    SpawnReplacement(
                        slot,
                        state);
                }
            }

            queueRoutine = null;
        }

        private IEnumerator PlayOnePrintCycle()
        {
            if (!AnimatorIsUsable())
            {
                // The workspace may be changing state while the queue is
                // being cancelled. Never call Animator APIs on an inactive
                // printer object.
                yield break;
            }

            int idleHash =
                printerAnimator
                    .GetCurrentAnimatorStateInfo(0)
                    .fullPathHash;

            printerAnimator.ResetTrigger(
                printTriggerName);

            printerAnimator.SetTrigger(
                printTriggerName);

            bool leftIdle = false;
            float elapsed = 0f;

            while (elapsed <
                   animationTimeoutSeconds)
            {
                if (!AnimatorIsUsable())
                    yield break;

                bool inTransition =
                    printerAnimator.IsInTransition(
                        0);

                AnimatorStateInfo stateInfo =
                    printerAnimator
                        .GetCurrentAnimatorStateInfo(
                            0);

                if (inTransition ||
                    stateInfo.fullPathHash != idleHash)
                {
                    leftIdle = true;
                }

                if (leftIdle &&
                    !inTransition &&
                    stateInfo.fullPathHash == idleHash)
                {
                    yield break;
                }

                elapsed +=
                    Time.deltaTime;

                yield return null;
            }

            Debug.LogWarning(
                "[MathConstructVR] Printer animation timed out; " +
                "continuing the supply queue so interaction cannot deadlock.",
                this);
        }

        private void ConfigureSource(
            SourceState state,
            GameObject prefab,
            VisualRole role,
            bool enabled)
        {
            state.Prefab = prefab;
            state.Role = role;
            state.Enabled = enabled;
            state.ReplacementPending = false;
            state.CurrentObject = null;
        }

        private void SpawnReplacement(
            ManipulativeSourceSlot slot,
            SourceState state)
        {
            if (!state.Enabled ||
                state.Anchor == null ||
                state.Prefab == null)
            {
                return;
            }

            GameObject instance =
                Instantiate(
                    state.Prefab,
                    state.Anchor.position,
                    state.Anchor.rotation,
                    generatedObjectsParent);

            instance.name =
                $"Supply_{slot}_{state.Role}";

            ManipulativeObject manipulative =
                instance.GetComponent<ManipulativeObject>();

            if (manipulative == null)
            {
                manipulative =
                    instance.AddComponent<ManipulativeObject>();
            }

            manipulative.InitializeSupplySource(
                workspaceController,
                this,
                slot,
                state.Role,
                state.Anchor.position,
                state.Anchor.rotation);

            state.CurrentObject =
                manipulative;

            state.ReplacementPending =
                false;
        }

        private SourceState GetSourceState(
            ManipulativeSourceSlot slot)
        {
            return slot switch
            {
                ManipulativeSourceSlot.SourceA =>
                    sourceAState,

                ManipulativeSourceSlot.SourceB =>
                    sourceBState,

                _ => null
            };
        }

        private bool AnimatorIsUsable()
        {
            return
                printerAnimator != null &&
                printerAnimator.isActiveAndEnabled &&
                printerAnimator.gameObject.activeInHierarchy;
        }

        private static void ResetSourceState(
            SourceState state)
        {
            if (state == null)
                return;

            state.Enabled = false;
            state.ReplacementPending = false;
            state.CurrentObject = null;
            state.Prefab = null;
        }

        private static string GetSemanticObjectKey(
            QuestionDto question,
            VisualRole role)
        {
            QuestionVisualDto visual =
                question.Visual;

            if (visual == null)
            {
                throw new InvalidOperationException(
                    $"JOIN question '{question.Id}' has no visual metadata. " +
                    "Printer source identity requires semantic object metadata.");
            }

            // Semantic labels are the source of truth. Visual codes may point
            // to the same temporary DefaultToken and must not determine whether
            // the learner needs one source or two.
            string roleLabel =
                role == VisualRole.Initial
                    ? visual.InitialObjectLabel
                    : visual.ChangeObjectLabel;

            string label =
                FirstNonEmpty(
                    roleLabel,
                    visual.ObjectLabel);

            if (HasText(label))
            {
                return
                    $"label:{label.Trim().ToLowerInvariant()}";
            }

            string roleCode =
                role == VisualRole.Initial
                    ? visual.InitialObjectCode
                    : visual.ChangeObjectCode;

            string code =
                FirstNonEmpty(
                    roleCode,
                    visual.ObjectCode);

            if (HasText(code))
            {
                return
                    $"code:{code.Trim()}";
            }

            string roleEmoji =
                role == VisualRole.Initial
                    ? visual.InitialFallbackEmoji
                    : visual.ChangeFallbackEmoji;

            string emoji =
                FirstNonEmpty(
                    roleEmoji,
                    visual.FallbackEmoji);

            if (HasText(emoji))
            {
                return
                    $"emoji:{emoji.Trim()}";
            }

            throw new InvalidOperationException(
                $"JOIN question '{question.Id}' is missing semantic object identity for role '{role}'. " +
                "Provide an object label, object code, or fallback emoji.");
        }

        private static bool HasText(
            string value)
        {
            return
                !string.IsNullOrWhiteSpace(
                    value);
        }

        private static string FirstNonEmpty(
            params string[] values)
        {
            if (values == null)
                return null;

            foreach (string value in values)
            {
                if (HasText(
                        value))
                {
                    return
                        value;
                }
            }

            return null;
        }
    }
}