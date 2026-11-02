using System;
using System.Collections.Generic;
using System.Linq;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using MathConstructVR.Networking.DTOs.LearnerState;
using UnityEngine;

namespace MathConstructVR.Core
{
    internal sealed class EqualGroupsWorkspaceInteraction : WorkspaceInteraction
    {
        private readonly List<WorkspaceRegion> groups = new();

        private int totalCount;
        private int expectedGroupCount;

        public EqualGroupsWorkspaceInteraction(
            WorkspaceController host,
            QuestionDto question)
            : base(host, question)
        {
        }

        public override InteractionType InteractionType =>
            InteractionType.EqualGroups;

        public override bool CanAddGroup =>
            groups.Count < MaximumGroupCount;

        public override bool CanCopyGroup =>
            groups.Count < MaximumGroupCount &&
            FindCopySource() != null;

        public override bool CanRemoveEmptyGroup =>
            groups.Count > 0;

        private int MaximumGroupCount =>
            expectedGroupCount + Host.EqualGroupsExtraGroupBuffer;

        public override void Build()
        {
            if (Question.Parameters == null ||
                !Question.Parameters.GroupCount.HasValue ||
                !Question.Parameters.GroupSize.HasValue)
            {
                throw new InvalidOperationException(
                    $"EQUAL_GROUPS question '{Question.Id}' is missing group_count/group_size parameters.");
            }

            expectedGroupCount =
                Question.Parameters.GroupCount.Value;

            totalCount =
                expectedGroupCount *
                Question.Parameters.GroupSize.Value;

            // IMPORTANT:
            // Equal Groups no longer pre-spawns the answer-sized object bank.
            // The workspace starts with no mathematical groups and no objects.
            // The learner creates groups and gets manipulatives from the
            // printer tray supply.
        }

        public override bool CanPlace(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            return
                manipulative != null &&
                manipulative.SemanticVisualRole == VisualRole.Object &&
                targetRegion != null &&
                groups.Contains(targetRegion);
        }

        public override void OnPlacementChanged(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            ReflowForCurrentState();
        }

        public override bool TryGetLearnerState(
            out object learnerState)
        {
            learnerState =
                new EqualGroupsLearnerStateDto
                {
                    GroupSizes = groups
                        .Select(group => group.OccupantCount)
                        .ToArray(),

                    // There is no pre-spawned "undistributed" bank anymore.
                    // Zero means zero objects physically waiting in a bank;
                    // it must NOT be interpreted as "no more objects exist."
                    UndistributedCount = 0,

                    Answer = null
                };

            return true;
        }

        public override bool HasMeaningfulAttempt()
        {
            return groups.Any(
                group => group.OccupantCount > 0);
        }

        public override string GetStateSignature()
        {
            return SerializeSignature(
                new
                {
                    supply = "printer",
                    group_sizes = groups
                        .Select(group => group.OccupantCount)
                        .ToArray(),
                    total_physically_placed =
                        groups.Sum(group => group.OccupantCount)
                });
        }

        public override string BuildMoveAction(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            int index =
                groups.IndexOf(newRegion);

            return WorkspaceActionFormatter.GroupObjectMoved(
                ObjectLabel(),
                index >= 0
                    ? $"group {index + 1}"
                    : "a group");
        }

        public override string BuildTutorContext()
        {
            int[] sizes =
                groups
                    .Select(group => group.OccupantCount)
                    .ToArray();

            string groupDescription =
                sizes.Length == 0
                    ? "no groups have been created"
                    : string.Join(
                        ", ",
                        sizes.Select(
                            (size, index) =>
                                $"group {index + 1} has {size} {ObjectPlural()}"));

            int physicallyPlaced =
                sizes.Sum();

            return
                $"Physical workspace state: Equal Groups uses a printer-tray supply. " +
                $"No answer-sized object bank is pre-spawned and no undistributed pile is visible. " +
                $"The learner has physically placed {physicallyPlaced} {ObjectPlural()} total; " +
                $"{groupDescription}. " +
                $"Only these group counts are physically visible. New {ObjectPlural()} are obtained from the printer tray.";
        }

        public override bool TryAddGroup(
            out string action)
        {
            action = "";

            if (!CanAddGroup)
                return false;

            CreateGroup(
                initialCapacity: 1);

            ReflowForCurrentState();

            action =
                WorkspaceActionFormatter.GroupCreated(
                    GroupLabel(),
                    groups.Count);

            return true;
        }

        public override bool TryCopyGroup(
            out string action)
        {
            action = "";

            if (!CanCopyGroup)
                return false;

            WorkspaceRegion source =
                FindCopySource();

            if (source == null)
                return false;

            int sourceSize =
                source.OccupantCount;

            int copiedGroupCapacity =
                DynamicCapacityForOccupancy(
                    sourceSize);

            WorkspaceRegion newGroup =
                CreateGroup(
                    copiedGroupCapacity);

            /*
             * Copy Group remains an explicit convenience operation.
             * It no longer consumes objects from an answer-sized bank.
             * Instead, it creates a true copy of the learner's populated
             * source group. Normal manual construction still uses the
             * printer-tray source one object at a time.
             */
            Host.SpawnObjects(
                Question,
                VisualRole.Object,
                sourceSize,
                newGroup,
                "CopiedItem");

            ReflowForCurrentState();

            action =
                WorkspaceActionFormatter.GroupCopied(
                    ObjectPlural(),
                    sourceSize,
                    groups.Count);

            return true;
        }

        public override bool TryRemoveEmptyGroup(
            out string action)
        {
            action = "";

            if (groups.Count == 0)
                return false;

            // Remove the most recently created group. This works even when
            // Copy Group populated it. Its objects are deleted with the group
            // instead of being forced onto the small return tray.
            WorkspaceRegion groupToRemove =
                groups[groups.Count - 1];

            int removedGroupNumber =
                groups.Count;

            if (!groupToRemove.TryDestroyAllOccupants(
                    out int removedObjectCount))
            {
                return false;
            }

            groups.RemoveAt(
                groups.Count - 1);

            Host.RemoveRegion(
                groupToRemove);

            ReflowForCurrentState();

            action =
                removedObjectCount > 0
                    ? $"Removed group {removedGroupNumber} and its {removedObjectCount} {ObjectPlural()}."
                    : $"Removed empty group {removedGroupNumber}.";

            return true;
        }

        private WorkspaceRegion CreateGroup(
            int initialCapacity)
        {
            int newCount =
                groups.Count + 1;

            CalculateLayout(
                newCount,
                out List<RegionPlacement> placements);

            RegionPlacement placement =
                placements[newCount - 1];

            WorkspaceRegion region =
                Host.CreateRegion(
                    $"Group_{newCount}",
                    placement,
                    Mathf.Clamp(
                        initialCapacity,
                        1,
                        Mathf.Max(1, totalCount)),
                    Host.TextCatalog.FormatGroupTitle(
                        GroupLabel(),
                        newCount),
                    WorkspaceRegionStyle.Neutral);

            groups.Add(
                region);

            return region;
        }

        private void ReflowForCurrentState()
        {
            ResizeDynamicRegionCapacities();

            CalculateLayout(
                groups.Count,
                out List<RegionPlacement> placements);

            for (int index = 0;
                 index < groups.Count;
                 index++)
            {
                RegionPlacement placement =
                    placements[index];

                groups[index].Reflow(
                    placement.Position,
                    placement.Rotation,
                    placement.Size,
                    Host.TextCatalog.FormatGroupTitle(
                        GroupLabel(),
                        index + 1),
                    WorkspaceRegionStyle.Neutral);
            }
        }

        private void ResizeDynamicRegionCapacities()
        {
            foreach (WorkspaceRegion group in groups)
            {
                if (group == null)
                    continue;

                group.ResizeCapacity(
                    DynamicCapacityForOccupancy(
                        group.OccupantCount));
            }
        }

        private int DynamicCapacityForOccupancy(
            int occupantCount)
        {
            if (occupantCount >= totalCount)
            {
                return Mathf.Max(
                    1,
                    totalCount);
            }

            return Mathf.Clamp(
                occupantCount + 1,
                1,
                Mathf.Max(1, totalCount));
        }

        private void CalculateLayout(
            int groupCount,
            out List<RegionPlacement> placements)
        {
            WorkspaceLayoutEngine.EqualGroupsGridOnly(
                Host.DeskGeometry,
                Host.DepthUsage,
                Host.SideMargin,
                Host.RegionGap,
                groupCount,
                out placements);
        }

        private WorkspaceRegion FindCopySource()
        {
            return groups.FirstOrDefault(
                group => group.OccupantCount > 0);
        }

        private string GroupLabel()
        {
            string label =
                Question.Visual?.GroupLabel;

            return string.IsNullOrWhiteSpace(
                label)
                    ? "group"
                    : label;
        }
    }
}