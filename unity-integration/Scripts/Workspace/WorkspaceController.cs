using System;
using System.Collections.Generic;
using MathConstructVR.Config;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using UnityEngine;
using UnityEngine.Serialization;

namespace MathConstructVR.Core
{
    public sealed class WorkspaceController : MonoBehaviour
    {
        [Header("Application")]
        [SerializeField]
        private SessionController sessionController;

        [SerializeField]
        private MathConstructTextCatalog textCatalog;

        [Header("Workspace")]
        [SerializeField]
        private Transform generatedWorkspace;

        [Tooltip("Permanent Box Collider defining the usable tabletop workspace.")]
        [SerializeField]
        private BoxCollider deskSurfaceCollider;

        [Header("Authored Prefabs")]
        [SerializeField]
        private WorkspaceRegion workspaceRegionPrefab;

        [SerializeField]
        private VisualAssetCatalog visualAssetCatalog;

        [Header("Manipulative Supply")]
        [SerializeField]
        private ManipulativeSupplyController manipulativeSupplyController;

        [Header("Shared Layout")]
        [Range(0.4f, 0.95f)]
        [SerializeField]
        private float depthUsage = 0.72f;

        [Min(0f)]
        [SerializeField]
        private float sideMargin = 0.08f;

        [Min(0.01f)]
        [SerializeField]
        private float regionGap = 0.08f;

        [Min(0.02f)]
        [SerializeField]
        private float preferredSlotSpacing = 0.11f;

        [Range(0.22f, 0.45f)]
        [SerializeField]
        private float bankDepthFraction = 0.30f;

        [Tooltip("If the bank row appears on the wrong side of the desk, toggle this without changing code.")]
        [SerializeField]
        private bool bankOnPositiveDeskZ = true;

        [Header("Equal Groups")]
        [Min(0)]
        [SerializeField]
        private int equalGroupsExtraGroupBuffer = 2;

        [FormerlySerializedAs("equalGroupsBankWidthFraction")]
        [Range(0.24f, 0.55f)]
        [SerializeField]
        private float equalGroupsMinimumBankWidthFraction = 0.34f;

        [Header("JOIN Change-Unknown Discovery Bank")]
        [Min(0)]
        [SerializeField]
        private int unknownJoinExtraObjects = 2;

        [Min(1)]
        [SerializeField]
        private int minimumUnknownJoinBankSize = 4;

        [Min(1)]
        [SerializeField]
        private int maximumUnknownJoinBankSize = 12;

        private readonly List<WorkspaceRegion> activeRegions = new();

        private WorkspaceInteraction activeInteraction;
        private QuestionDto currentQuestion;
        private DeskSurfaceGeometry deskGeometry;

        private bool initialized;

        public event Action<string> MeaningfulStateChanged;

        public event Action<InteractionType> InteractionChanged;

        public event Action<bool, bool, bool>
            GroupControlsAvailabilityChanged;

        public InteractionType CurrentInteractionType =>
            activeInteraction?.InteractionType ?? InteractionType.Unknown;

        public IReadOnlyList<WorkspaceRegion> ActiveRegions =>
            activeRegions;

        public bool CanAddGroup =>
            activeInteraction?.CanAddGroup ?? false;

        public bool CanCopyGroup =>
            activeInteraction?.CanCopyGroup ?? false;

        public bool CanRemoveEmptyGroup =>
            activeInteraction?.CanRemoveEmptyGroup ?? false;

        internal DeskSurfaceGeometry DeskGeometry => deskGeometry;
        internal MathConstructTextCatalog TextCatalog => textCatalog;
        internal float DepthUsage => depthUsage;
        internal float SideMargin => sideMargin;
        internal float RegionGap => regionGap;
        internal float BankDepthFraction => bankDepthFraction;
        internal float BankDepthSign => bankOnPositiveDeskZ ? 1f : -1f;
        internal int EqualGroupsExtraGroupBuffer => equalGroupsExtraGroupBuffer;
        internal float EqualGroupsMinimumBankWidthFraction => equalGroupsMinimumBankWidthFraction;
        internal float PreferredSlotSpacing => preferredSlotSpacing;

        internal GameObject ResolveVisualPrefab(
            QuestionDto question,
            VisualRole role)
        {
            return visualAssetCatalog.Resolve(
                question,
                role);
        }

        public void Initialize()
        {
            if (initialized)
                return;

            ValidateConfiguration();

            deskGeometry =
                CalculateDeskGeometry();

            manipulativeSupplyController?.Initialize(
                this,
                visualAssetCatalog,
                generatedWorkspace);

            sessionController.CurrentQuestionChanged +=
                HandleQuestionChanged;

            initialized = true;

            if (sessionController.IsInitialized &&
                sessionController.CurrentQuestion != null)
            {
                BuildWorkspace(
                    sessionController.CurrentQuestion);
            }
        }

        private void OnDestroy()
        {
            if (sessionController != null)
            {
                sessionController.CurrentQuestionChanged -=
                    HandleQuestionChanged;
            }
        }

        private void ValidateConfiguration()
        {
            if (sessionController == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires SessionController.");
            }

            if (textCatalog == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires MathConstructTextCatalog.");
            }

            if (generatedWorkspace == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires GeneratedWorkspace.");
            }

            if (deskSurfaceCollider == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires WorkspaceBounds Box Collider.");
            }

            if (workspaceRegionPrefab == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires the authored WorkspaceRegion prefab.");
            }

            if (visualAssetCatalog == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires VisualAssetCatalog.");
            }

            if (manipulativeSupplyController == null)
            {
                throw new InvalidOperationException(
                    "WorkspaceController requires ManipulativeSupplyController.");
            }
        }

        private void HandleQuestionChanged(
            QuestionDto question)
        {
            BuildWorkspace(question);
        }

        private void BuildWorkspace(
            QuestionDto question)
        {
            manipulativeSupplyController?.ResetSupply();
            ClearGeneratedWorkspace();

            currentQuestion = question;
            activeInteraction = null;

            if (question == null)
            {
                PublishInteractionState();
                return;
            }

            deskGeometry =
                CalculateDeskGeometry();

            switch (question.InteractionType)
            {
                case InteractionType.Join:
                    activeInteraction =
                        new JoinWorkspaceInteraction(
                            this,
                            question);
                    break;

                case InteractionType.Remove:
                    activeInteraction =
                        new RemoveWorkspaceInteraction(
                            this,
                            question);
                    break;

                case InteractionType.EqualGroups:
                    activeInteraction =
                        new EqualGroupsWorkspaceInteraction(
                            this,
                            question);
                    break;

                case InteractionType.EqualSharing:
                    activeInteraction =
                        new EqualSharingWorkspaceInteraction(
                            this,
                            question);
                    break;

                case InteractionType.PartToPartRatio:
                    activeInteraction =
                        new RatioWorkspaceInteraction(
                            this,
                            question);
                    break;

                default:
                    Debug.LogError(
                        $"[MathConstructVR] Unsupported interaction '{question.Interaction}' for question '{question.Id}'.",
                        this);
                    PublishInteractionState();
                    return;
            }

            try
            {
                activeInteraction.Build();

                if (question.InteractionType == InteractionType.Join)
                {
                    manipulativeSupplyController.ConfigureForJoin(question);
                }
                else if (question.InteractionType == InteractionType.EqualGroups)
                {
                    manipulativeSupplyController.ConfigureForEqualGroups(question);
                }
            }
            catch (Exception exception)
            {
                Debug.LogError(
                    $"[MathConstructVR] Could not build workspace for question '{question.Id}'.\n{exception}",
                    this);

                manipulativeSupplyController?.ResetSupply();
                ClearGeneratedWorkspace();
                activeInteraction = null;
            }

            PublishInteractionState();
        }

        internal WorkspaceRegion CreateRegion(
            string regionName,
            RegionPlacement placement,
            int capacity,
            string title,
            WorkspaceRegionStyle style)
        {
            WorkspaceRegion region =
                Instantiate(
                    workspaceRegionPrefab,
                    generatedWorkspace);

            region.name = regionName;

            region.Configure(
                placement.Position,
                placement.Rotation,
                placement.Size,
                Mathf.Max(1, capacity),
                preferredSlotSpacing,
                title,
                style);

            activeRegions.Add(region);

            return region;
        }

        internal List<ManipulativeObject> SpawnObjects(
            QuestionDto question,
            VisualRole role,
            int count,
            WorkspaceRegion region,
            string namePrefix)
        {
            List<ManipulativeObject> spawned = new();

            if (count <= 0)
                return spawned;

            if (count > region.Capacity)
            {
                throw new InvalidOperationException(
                    $"Workspace region '{region.name}' has capacity {region.Capacity} but needs {count} objects.");
            }

            if (count > region.PhysicalSlotCapacity)
            {
                throw new InvalidOperationException(
                    $"Workspace region '{region.name}' is physically too small for {count} objects at preferred spacing. " +
                    $"Its current geometric capacity is {region.PhysicalSlotCapacity}. " +
                    $"The interaction layout must allocate more physical area instead of compressing objects.");
            }

            GameObject prefab =
                visualAssetCatalog.Resolve(
                    question,
                    role);

            for (int index = 0; index < count; index++)
            {
                GameObject instance =
                    Instantiate(
                        prefab,
                        generatedWorkspace);

                instance.name =
                    $"{namePrefix}_{index + 1:00}";

                ManipulativeObject manipulative =
                    instance.GetComponent<ManipulativeObject>();

                if (manipulative == null)
                {
                    manipulative =
                        instance.AddComponent<ManipulativeObject>();
                }

                region.Assign(
                    manipulative,
                    index);

                manipulative.Initialize(
                    this,
                    region,
                    index,
                    locked: false);

                spawned.Add(manipulative);
            }

            // Initial banks/collections are spawned sequentially. Reflow once
            // after the full set exists so REMOVE, RATIO, legacy JOIN, etc.
            // all use the same non-overlapping occupancy-aware slot layout.
            region.RefreshSlotLayout();

            return spawned;
        }

        internal bool TransferManipulative(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            if (manipulative == null ||
                targetRegion == null)
            {
                return false;
            }

            if (!targetRegion.TryFindFirstAvailableSlot(
                    manipulative,
                    out int targetSlot))
            {
                return false;
            }

            WorkspaceRegion previousRegion =
                manipulative.CurrentRegion;

            previousRegion?.Release(manipulative);

            targetRegion.Assign(
                manipulative,
                targetSlot);

            manipulative.CommitPlacement(
                targetRegion,
                targetSlot);

            return true;
        }

        internal void RemoveRegion(
            WorkspaceRegion region)
        {
            if (region == null)
                return;

            activeRegions.Remove(region);
            Destroy(region.gameObject);
        }

        internal int GetUnknownJoinCandidateCount(
            int requiredChange)
        {
            int desired =
                requiredChange +
                unknownJoinExtraObjects;

            int upperBound =
                Mathf.Max(
                    minimumUnknownJoinBankSize,
                    maximumUnknownJoinBankSize);

            return Mathf.Clamp(
                desired,
                minimumUnknownJoinBankSize,
                upperBound);
        }

        public void HandleManipulativeReleased(
            ManipulativeObject manipulative,
            Vector3 releaseWorldPosition)
        {
            if (manipulative == null ||
                activeInteraction == null)
            {
                return;
            }

            if (manipulativeSupplyController != null &&
                manipulativeSupplyController.IsInsideActiveReturnArea(
                    releaseWorldPosition))
            {
                if (!manipulativeSupplyController.TryReserveReturnSlot(
                        manipulative,
                        out int returnSlotIndex,
                        out Vector3 traySurfacePosition,
                        out Quaternion trayRotation,
                        out Vector3 trayUp))
                {
                    // Return tray is full. Preserve the learner's previous
                    // mathematical placement instead of stacking objects.
                    manipulative.ReturnToCurrentPlacement();
                    return;
                }

                WorkspaceRegion trayPreviousRegion =
                    manipulative.CurrentRegion;

                trayPreviousRegion?.Release(
                    manipulative);

                manipulative.CommitTrayPlacement(
                    manipulativeSupplyController,
                    returnSlotIndex,
                    traySurfacePosition,
                    trayRotation,
                    trayUp);

                if (trayPreviousRegion != null)
                {
                    activeInteraction.OnPlacementChanged(
                        manipulative,
                        trayPreviousRegion,
                        null);
                }

                string objectLabel =
                    currentQuestion?.Visual?.ObjectLabel;

                if (string.IsNullOrWhiteSpace(
                        objectLabel))
                {
                    objectLabel = "object";
                }

                MeaningfulStateChanged?.Invoke(
                    $"Returned one {objectLabel} to the printer tray.");

                PublishGroupControlsAvailability();
                return;
            }

            WorkspaceRegion bestRegion = null;
            int bestSlot = -1;
            float bestDistance = float.PositiveInfinity;

            foreach (WorkspaceRegion region in activeRegions)
            {
                if (region == null ||
                    !activeInteraction.CanPlace(
                        manipulative,
                        region))
                {
                    continue;
                }

                if (!region.ContainsWorldPoint(
                        releaseWorldPosition))
                {
                    continue;
                }

                if (!region.TryFindNearestAvailableSlot(
                        releaseWorldPosition,
                        manipulative,
                        out int candidateSlot))
                {
                    continue;
                }

                Vector3 candidatePosition =
                    region.GetSlotWorldPosition(
                        candidateSlot);

                float distance =
                    (candidatePosition - releaseWorldPosition)
                    .sqrMagnitude;

                if (distance >= bestDistance)
                    continue;

                bestDistance = distance;
                bestRegion = region;
                bestSlot = candidateSlot;
            }

            if (bestRegion == null)
            {
                manipulative.ReturnToCurrentPlacement();
                return;
            }

            WorkspaceRegion previousRegion =
                manipulative.CurrentRegion;

            int previousSlot =
                manipulative.CurrentSlotIndex;

            bool placementChanged =
                previousRegion != bestRegion ||
                previousSlot != bestSlot;

            if (!placementChanged)
            {
                manipulative.ReturnToCurrentPlacement();
                return;
            }

            bool semanticStateChanged =
                previousRegion != bestRegion;

            previousRegion?.Release(manipulative);

            bestRegion.Assign(
                manipulative,
                bestSlot);

            manipulative.CommitPlacement(
                bestRegion,
                bestSlot);

            // Global invariant: every interaction type reflows after a
            // placement so occupied objects use distinct, non-compressed
            // physical slots. This applies to JOIN, REMOVE, EQUAL_GROUPS,
            // EQUAL_SHARING, and PART_TO_PART_RATIO.
            previousRegion?.RefreshSlotLayout();

            if (bestRegion != previousRegion)
            {
                bestRegion.RefreshSlotLayout();
            }

            if (!semanticStateChanged)
                return;

            activeInteraction.OnPlacementChanged(
                manipulative,
                previousRegion,
                bestRegion);

            string latestAction =
                activeInteraction.BuildMoveAction(
                    manipulative,
                    previousRegion,
                    bestRegion);

            MeaningfulStateChanged?.Invoke(
                latestAction);

            PublishGroupControlsAvailability();
        }

        public void ResetCurrentWorkspace()
        {
            if (currentQuestion == null)
                return;

            BuildWorkspace(currentQuestion);
        }


        public bool TryGetLearnerState(
            out object learnerState)
        {
            learnerState = null;

            return
                activeInteraction != null &&
                activeInteraction.TryGetLearnerState(
                    out learnerState);
        }

        public bool HasMeaningfulAttempt()
        {
            return
                activeInteraction != null &&
                activeInteraction.HasMeaningfulAttempt();
        }

        public string GetStateSignature()
        {
            return activeInteraction?.GetStateSignature() ?? "";
        }

        public string AdaptTutorResponse(
            string text)
        {
            return activeInteraction?.AdaptTutorText(text) ?? text;
        }

        public string GetTutorContext()
        {
            return activeInteraction?.BuildTutorContext() ?? "";
        }

        public void AddGroup()
        {
            if (activeInteraction == null)
                return;

            if (activeInteraction.TryAddGroup(
                    out string action))
            {
                MeaningfulStateChanged?.Invoke(action);
            }

            PublishGroupControlsAvailability();
        }

        public void CopyGroup()
        {
            if (activeInteraction == null)
                return;

            if (activeInteraction.TryCopyGroup(
                    out string action))
            {
                MeaningfulStateChanged?.Invoke(action);
            }

            PublishGroupControlsAvailability();
        }

        public void RemoveEmptyGroup()
        {
            if (activeInteraction == null)
                return;

            if (activeInteraction.TryRemoveEmptyGroup(
                    out string action))
            {
                MeaningfulStateChanged?.Invoke(action);
            }

            PublishGroupControlsAvailability();
        }

        private void PublishInteractionState()
        {
            InteractionChanged?.Invoke(
                CurrentInteractionType);

            PublishGroupControlsAvailability();
        }

        private void PublishGroupControlsAvailability()
        {
            GroupControlsAvailabilityChanged?.Invoke(
                activeInteraction?.CanAddGroup ?? false,
                activeInteraction?.CanCopyGroup ?? false,
                activeInteraction?.CanRemoveEmptyGroup ?? false);
        }

        private DeskSurfaceGeometry CalculateDeskGeometry()
        {
            Transform deskTransform =
                deskSurfaceCollider.transform;

            Vector3 localTopCenter =
                deskSurfaceCollider.center;

            localTopCenter.y +=
                deskSurfaceCollider.size.y *
                0.5f;

            Vector3 center =
                deskTransform.TransformPoint(
                    localTopCenter);

            Vector3 scale =
                deskTransform.lossyScale;

            float width =
                Mathf.Abs(
                    deskSurfaceCollider.size.x *
                    scale.x);

            float depth =
                Mathf.Abs(
                    deskSurfaceCollider.size.z *
                    scale.z);

            return
                new DeskSurfaceGeometry(
                    center,
                    deskTransform.rotation,
                    deskTransform.right.normalized,
                    deskTransform.forward.normalized,
                    width,
                    depth);
        }

        private void ClearGeneratedWorkspace()
        {
            activeRegions.Clear();

            for (int index =
                    generatedWorkspace.childCount - 1;
                 index >= 0;
                 index--)
            {
                Destroy(
                    generatedWorkspace
                        .GetChild(index)
                        .gameObject);
            }
        }
    }
}