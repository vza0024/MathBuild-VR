using System;
using System.Collections.Generic;
using System.Linq;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using MathConstructVR.Networking.DTOs.LearnerState;
using UnityEngine;

namespace MathConstructVR.Core
{
    internal sealed class EqualSharingWorkspaceInteraction : WorkspaceInteraction
    {
        private readonly List<ManipulativeObject> objects = new();
        private readonly List<WorkspaceRegion> recipients = new();

        private WorkspaceRegion bankRegion;

        private int totalCount;
        private int recipientCount;

        private float SharingDepthSign =>
            -Host.BankDepthSign;

        public EqualSharingWorkspaceInteraction(
            WorkspaceController host,
            QuestionDto question)
            : base(host, question)
        {
        }

        public override InteractionType InteractionType =>
            InteractionType.EqualSharing;

        public override void Build()
        {
            if (Question.Parameters == null ||
                !Question.Parameters.Total.HasValue ||
                !Question.Parameters.RecipientCount.HasValue)
            {
                throw new InvalidOperationException(
                    $"EQUAL_SHARING question '{Question.Id}' is missing total/recipient_count parameters.");
            }

            totalCount =
                Question.Parameters.Total.Value;

            recipientCount =
                Question.Parameters.RecipientCount.Value;

            if (totalCount <= 0 ||
                recipientCount <= 0)
            {
                throw new InvalidOperationException(
                    $"EQUAL_SHARING question '{Question.Id}' requires positive total/recipient_count values.");
            }

            CalculateCurrentLayout(
                bankOccupancy: totalCount,
                recipientOccupancies:
                    Enumerable
                        .Repeat(0, recipientCount)
                        .ToArray(),
                out RegionPlacement bankPlacement,
                out List<RegionPlacement> recipientPlacements);

            bankRegion =
                Host.CreateRegion(
                    "SharingObjectBank",
                    bankPlacement,
                    totalCount,
                    Host.TextCatalog.FormatToShare(
                        ObjectPlural()),
                    WorkspaceRegionStyle.Neutral);

            SetOutwardTitleEdge(
                bankRegion,
                isBank: true);

            for (int index = 0;
                 index < recipientCount;
                 index++)
            {
                WorkspaceRegion recipient =
                    Host.CreateRegion(
                        $"Recipient_{index + 1}",
                        recipientPlacements[index],
                        totalCount,
                        RecipientTitle(index),
                        WorkspaceRegionStyle.Neutral);

                SetOutwardTitleEdge(
                    recipient,
                    isBank: false);

                recipients.Add(
                    recipient);
            }

            objects.AddRange(
                Host.SpawnObjects(
                    Question,
                    VisualRole.Object,
                    totalCount,
                    bankRegion,
                    "Item"));
        }

        public override bool CanPlace(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            return
                manipulative != null &&
                objects.Contains(manipulative) &&
                targetRegion != null &&
                (targetRegion == bankRegion ||
                 recipients.Contains(targetRegion));
        }

        public override void OnPlacementChanged(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            ReflowForCurrentOccupancy();
        }

        private void ReflowForCurrentOccupancy()
        {
            if (bankRegion == null)
                return;

            int[] recipientOccupancies =
                recipients
                    .Select(
                        recipient =>
                            recipient?.OccupantCount ?? 0)
                    .ToArray();

            CalculateCurrentLayout(
                bankRegion.OccupantCount,
                recipientOccupancies,
                out RegionPlacement bankPlacement,
                out List<RegionPlacement> recipientPlacements);

            bankRegion.Reflow(
                bankPlacement.Position,
                bankPlacement.Rotation,
                bankPlacement.Size,
                Host.TextCatalog.FormatToShare(
                    ObjectPlural()),
                WorkspaceRegionStyle.Neutral);

            SetOutwardTitleEdge(
                bankRegion,
                isBank: true);

            for (int index = 0;
                 index < recipients.Count;
                 index++)
            {
                WorkspaceRegion recipient =
                    recipients[index];

                RegionPlacement placement =
                    recipientPlacements[index];

                recipient.Reflow(
                    placement.Position,
                    placement.Rotation,
                    placement.Size,
                    RecipientTitle(index),
                    WorkspaceRegionStyle.Neutral);

                SetOutwardTitleEdge(
                    recipient,
                    isBank: false);
            }
        }

        private void CalculateCurrentLayout(
            int bankOccupancy,
            int[] recipientOccupancies,
            out RegionPlacement bankPlacement,
            out List<RegionPlacement> recipientPlacements)
        {
            // Reserve one NEXT drop slot from the learner's CURRENT state.
            // Never use the correct share size / answer.
            int bankDemand =
                Mathf.Clamp(
                    bankOccupancy +
                    (bankOccupancy < totalCount ? 1 : 0),
                    1,
                    totalCount);

            int[] recipientDemands =
                new int[recipientCount];

            for (int index = 0;
                 index < recipientCount;
                 index++)
            {
                int occupancy =
                    recipientOccupancies != null &&
                    index < recipientOccupancies.Length
                        ? recipientOccupancies[index]
                        : 0;

                recipientDemands[index] =
                    Mathf.Clamp(
                        occupancy + 1,
                        1,
                        totalCount);
            }

            WorkspaceLayoutEngine.EqualSharingAdaptiveBands(
                Host.DeskGeometry,
                Host.SideMargin,
                Host.RegionGap,
                Host.PreferredSlotSpacing,
                SharingDepthSign,
                bankDemand,
                recipientDemands,
                out bankPlacement,
                out recipientPlacements);
        }

        private void SetOutwardTitleEdge(
            WorkspaceRegion region,
            bool isBank)
        {
            if (region == null)
                return;

            bool bankIsOnPositiveZ =
                SharingDepthSign >= 0f;

            bool positiveEdge =
                isBank
                    ? bankIsOnPositiveZ
                    : !bankIsOnPositiveZ;

            region.SetTitleOnPositiveZEdge(
                positiveEdge);
        }

        public override bool TryGetLearnerState(
            out object learnerState)
        {
            learnerState =
                new EqualSharingLearnerStateDto
                {
                    ShareSizes =
                        recipients
                            .Select(
                                recipient =>
                                    recipient.OccupantCount)
                            .ToArray(),

                    UndistributedCount =
                        bankRegion.OccupantCount,

                    Answer = null
                };

            return true;
        }

        public override bool HasMeaningfulAttempt()
        {
            return
                recipients.Any(
                    recipient =>
                        recipient.OccupantCount > 0);
        }

        public override string GetStateSignature()
        {
            return SerializeSignature(
                new
                {
                    share_sizes =
                        recipients
                            .Select(
                                recipient =>
                                    recipient.OccupantCount)
                            .ToArray(),

                    undistributed =
                        bankRegion.OccupantCount
                });
        }

        public override string BuildMoveAction(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            if (newRegion == bankRegion)
            {
                return WorkspaceActionFormatter.SharingObjectMoved(
                    ObjectLabel(),
                    "the objects-to-share area");
            }

            int index =
                recipients.IndexOf(
                    newRegion);

            return WorkspaceActionFormatter.SharingObjectMoved(
                ObjectLabel(),
                index >= 0
                    ? RecipientTitle(index)
                    : "a recipient");
        }

        private string RecipientTitle(
            int index)
        {
            string[] exactLabels =
                Question.Visual?.RecipientLabels;

            if (exactLabels != null &&
                index >= 0 &&
                index < exactLabels.Length &&
                !string.IsNullOrWhiteSpace(
                    exactLabels[index]))
            {
                return
                    exactLabels[index].Trim();
            }

            return
                Host.TextCatalog.FormatRecipientTitle(
                    RecipientLabel(),
                    index + 1);
        }

        private string RecipientLabel()
        {
            string label =
                Question.Visual?.RecipientLabel;

            return
                string.IsNullOrWhiteSpace(
                    label)
                    ? "recipient"
                    : label;
        }
    }
}