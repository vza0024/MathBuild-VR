using System;
using System.Collections.Generic;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using MathConstructVR.Networking.DTOs.LearnerState;

namespace MathConstructVR.Core
{
    internal sealed class RatioWorkspaceInteraction : WorkspaceInteraction
    {
        private readonly List<ManipulativeObject> partAObjects = new();
        private readonly List<ManipulativeObject> partBObjects = new();

        private WorkspaceRegion bankA;
        private WorkspaceRegion bankB;
        private WorkspaceRegion targetA;
        private WorkspaceRegion targetB;

        private int partACount;
        private int partBCount;

        public RatioWorkspaceInteraction(
            WorkspaceController host,
            QuestionDto question)
            : base(host, question)
        {
        }

        public override InteractionType InteractionType =>
            InteractionType.PartToPartRatio;

        public override void Build()
        {
            if (Question.Parameters == null ||
                !Question.Parameters.PartA.HasValue ||
                !Question.Parameters.PartB.HasValue)
            {
                throw new InvalidOperationException(
                    $"PART_TO_PART_RATIO question '{Question.Id}' is missing part_a/part_b parameters.");
            }

            partACount = Question.Parameters.PartA.Value;
            partBCount = Question.Parameters.PartB.Value;

            WorkspaceLayoutEngine.RatioFourRegions(
                Host.DeskGeometry,
                Host.DepthUsage,
                Host.SideMargin,
                Host.RegionGap,
                Host.RegionGap,
                Host.BankDepthSign,
                out RegionPlacement bankAPlacement,
                out RegionPlacement bankBPlacement,
                out RegionPlacement targetAPlacement,
                out RegionPlacement targetBPlacement);

            // The desk's local left/right orientation is reversed from
            // the learner's seated view. Put the first ratio part on the
            // learner's left and the second ratio part on the learner's right.
            bankA = Host.CreateRegion(
                "RatioBankA",
                bankBPlacement,
                partACount,
                Host.TextCatalog.FormatRatioBank(PartALabel()),
                WorkspaceRegionStyle.Neutral);

            bankB = Host.CreateRegion(
                "RatioBankB",
                bankAPlacement,
                partBCount,
                Host.TextCatalog.FormatRatioBank(PartBLabel()),
                WorkspaceRegionStyle.Neutral);

            targetA = Host.CreateRegion(
                "RatioTargetA",
                targetBPlacement,
                partACount,
                Host.TextCatalog.FormatRatioFirst(PartALabel()),
                WorkspaceRegionStyle.Neutral);

            targetB = Host.CreateRegion(
                "RatioTargetB",
                targetAPlacement,
                partBCount,
                Host.TextCatalog.FormatRatioSecond(PartBLabel()),
                WorkspaceRegionStyle.Neutral);

            partAObjects.AddRange(
                Host.SpawnObjects(
                    Question,
                    VisualRole.PartA,
                    partACount,
                    bankA,
                    "PartA"));

            partBObjects.AddRange(
                Host.SpawnObjects(
                    Question,
                    VisualRole.PartB,
                    partBCount,
                    bankB,
                    "PartB"));
        }

        public override bool CanPlace(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            if (partAObjects.Contains(manipulative))
            {
                return
                    targetRegion == bankA ||
                    targetRegion == targetA;
            }

            if (partBObjects.Contains(manipulative))
            {
                return
                    targetRegion == bankB ||
                    targetRegion == targetB;
            }

            return false;
        }

        public override bool TryGetLearnerState(
            out object learnerState)
        {
            learnerState =
                new RatioLearnerStateDto
                {
                    PartACount = CountInRegion(partAObjects, targetA),
                    PartBCount = CountInRegion(partBObjects, targetB),
                    UnassignedA = CountInRegion(partAObjects, bankA),
                    UnassignedB = CountInRegion(partBObjects, bankB),
                    Answer = null
                };

            return true;
        }

        public override bool HasMeaningfulAttempt()
        {
            return
                CountInRegion(partAObjects, targetA) > 0 ||
                CountInRegion(partBObjects, targetB) > 0;
        }

        public override string GetStateSignature()
        {
            return SerializeSignature(
                new
                {
                    part_a = CountInRegion(partAObjects, targetA),
                    part_b = CountInRegion(partBObjects, targetB),
                    unassigned_a = CountInRegion(partAObjects, bankA),
                    unassigned_b = CountInRegion(partBObjects, bankB)
                });
        }

        public override string BuildMoveAction(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            if (newRegion == targetA)
            {
                return WorkspaceActionFormatter.RatioObjectMoved(
                    PartALabel(),
                    "the first labelled collection");
            }

            if (newRegion == targetB)
            {
                return WorkspaceActionFormatter.RatioObjectMoved(
                    PartBLabel(),
                    "the second labelled collection");
            }

            return WorkspaceActionFormatter.RatioObjectMoved(
                partAObjects.Contains(manipulative)
                    ? PartALabel()
                    : PartBLabel(),
                "its matching bank");
        }

        private string PartALabel()
        {
            string label = Question.Visual?.PartALabel;

            return string.IsNullOrWhiteSpace(label)
                ? "first part"
                : label;
        }

        private string PartBLabel()
        {
            string label = Question.Visual?.PartBLabel;

            return string.IsNullOrWhiteSpace(label)
                ? "second part"
                : label;
        }
    }
}