using System;
using System.Collections.Generic;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using MathConstructVR.Networking.DTOs.LearnerState;

namespace MathConstructVR.Core
{
    internal sealed class RemoveWorkspaceInteraction : WorkspaceInteraction
    {
        private readonly List<ManipulativeObject> objects = new();

        private WorkspaceRegion startingRegion;
        private WorkspaceRegion removedRegion;

        private int initialCount;

        public RemoveWorkspaceInteraction(
            WorkspaceController host,
            QuestionDto question)
            : base(host, question)
        {
        }

        public override InteractionType InteractionType =>
            InteractionType.Remove;

        public override void Build()
        {
            if (Question.Parameters == null ||
                !Question.Parameters.Initial.HasValue)
            {
                throw new InvalidOperationException(
                    $"REMOVE question '{Question.Id}' is missing its initial parameter.");
            }

            initialCount = Question.Parameters.Initial.Value;

            WorkspaceLayoutEngine.TwoColumns(
                Host.DeskGeometry,
                Host.DepthUsage,
                Host.SideMargin,
                Host.RegionGap,
                out RegionPlacement left,
                out RegionPlacement right);

            // The desk's local left/right orientation is reversed from the
            // learner's seated view, so use the opposite placements here.
            // This keeps Starting collection on the learner's left and
            // Removed on the learner's right.
            startingRegion = Host.CreateRegion(
                "StartingCollection",
                right,
                initialCount,
                Host.TextCatalog.StartingCollection,
                WorkspaceRegionStyle.Neutral);

            removedRegion = Host.CreateRegion(
                "Removed",
                left,
                initialCount,
                Host.TextCatalog.Removed,
                WorkspaceRegionStyle.Removal);

            objects.AddRange(
                Host.SpawnObjects(
                    Question,
                    VisualRole.Object,
                    initialCount,
                    startingRegion,
                    "Item"));
        }

        public override bool CanPlace(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            return
                objects.Contains(manipulative) &&
                (targetRegion == startingRegion ||
                 targetRegion == removedRegion);
        }

        public override bool TryGetLearnerState(
            out object learnerState)
        {
            int removed = CountInRegion(objects, removedRegion);
            int remaining = CountInRegion(objects, startingRegion);

            learnerState =
                new RemoveLearnerStateDto
                {
                    RemovedCount = removed,
                    RemainingCount = remaining,
                    Answer = null
                };

            return true;
        }

        public override bool HasMeaningfulAttempt()
        {
            return CountInRegion(objects, removedRegion) > 0;
        }

        public override string GetStateSignature()
        {
            return SerializeSignature(
                new
                {
                    removed = CountInRegion(objects, removedRegion),
                    remaining = CountInRegion(objects, startingRegion)
                });
        }

        public override string BuildMoveAction(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            if (newRegion == removedRegion)
            {
                return WorkspaceActionFormatter.RemoveMovedOut(ObjectLabel());
            }

            return WorkspaceActionFormatter.RemoveReturned(ObjectLabel());
        }
    }
}