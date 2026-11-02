using System;
using System.Collections.Generic;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using MathConstructVR.Networking.DTOs.LearnerState;
using UnityEngine;

namespace MathConstructVR.Core
{
    internal sealed class JoinWorkspaceInteraction : WorkspaceInteraction
    {
        private enum ResultWorkspaceLayout
        {
            None = 0,
            SingleDestination = 1,
            TwoDestinations = 2
        }

        private readonly List<ManipulativeObject> initialObjects = new();
        private readonly List<ManipulativeObject> changeObjects = new();

        private WorkspaceRegion initialRegion;
        private WorkspaceRegion changeRegion;
        private WorkspaceRegion combinedRegion;

        private int initialCount;
        private int statedChangeCount;
        private int resultCount;

        private ResultWorkspaceLayout resultLayout =
            ResultWorkspaceLayout.None;

        private bool IsResultUnknown =>
            Question.UnknownPositionType == UnknownPositionType.Result;

        private bool IsChangeUnknown =>
            Question.UnknownPositionType == UnknownPositionType.Change;

        public JoinWorkspaceInteraction(
            WorkspaceController host,
            QuestionDto question)
            : base(host, question)
        {
        }

        public override InteractionType InteractionType =>
            InteractionType.Join;

        public override void Build()
        {
            if (Question.Parameters == null ||
                !Question.Parameters.Initial.HasValue)
            {
                throw new InvalidOperationException(
                    $"JOIN question '{Question.Id}' is missing its initial parameter.");
            }

            initialCount = Question.Parameters.Initial.Value;

            if (IsResultUnknown)
            {
                if (!Question.Parameters.Change.HasValue)
                {
                    throw new InvalidOperationException(
                        $"JOIN result-unknown question '{Question.Id}' is missing its stated change parameter.");
                }

                statedChangeCount = Question.Parameters.Change.Value;
                resultCount = initialCount + statedChangeCount;

                BuildEmptyResultUnknownWorkspace();
                return;
            }

            if (IsChangeUnknown)
            {
                if (!Question.Parameters.Result.HasValue)
                {
                    throw new InvalidOperationException(
                        $"JOIN change-unknown question '{Question.Id}' is missing its stated result parameter.");
                }

                resultCount = Question.Parameters.Result.Value;
                statedChangeCount = resultCount - initialCount;

                if (statedChangeCount < 0)
                {
                    throw new InvalidOperationException(
                        $"JOIN change-unknown question '{Question.Id}' has a result smaller than its initial amount.");
                }

                BuildLegacyChangeUnknownWorkspace();
                return;
            }

            throw new InvalidOperationException(
                $"JOIN question '{Question.Id}' uses unsupported unknown position '{Question.UnknownPosition}'.");
        }

        private void BuildEmptyResultUnknownWorkspace()
        {
            ValidateAndResolveResultLayout();

            int regionCapacity =
                Mathf.Max(
                    12,
                    resultCount + 6);

            if (resultLayout ==
                ResultWorkspaceLayout.SingleDestination)
            {
                RegionPlacement placement =
                    WorkspaceLayoutEngine.SingleRegion(
                        Host.DeskGeometry,
                        Host.DepthUsage,
                        Host.SideMargin);

                combinedRegion =
                    Host.CreateRegion(
                        "JoinCombinedCollection",
                        placement,
                        regionCapacity,
                        Question.Visual.GroupLabel.Trim(),
                        WorkspaceRegionStyle.Neutral);

                return;
            }

            WorkspaceLayoutEngine.TwoColumns(
                Host.DeskGeometry,
                Host.DepthUsage,
                Host.SideMargin,
                Host.RegionGap,
                out RegionPlacement left,
                out RegionPlacement right);

            // In this scene, the desk local X axis is reversed from the
            // learner's visual left/right, so Part A uses the placement
            // returned as "right" to appear on the learner's LEFT.
            initialRegion =
                Host.CreateRegion(
                    "JoinPartA",
                    right,
                    regionCapacity,
                    Question.Visual.PartALabel.Trim(),
                    WorkspaceRegionStyle.Neutral);

            changeRegion =
                Host.CreateRegion(
                    "JoinPartB",
                    left,
                    regionCapacity,
                    Question.Visual.PartBLabel.Trim(),
                    WorkspaceRegionStyle.Neutral);
        }

        private void ValidateAndResolveResultLayout()
        {
            QuestionVisualDto visual =
                Question.Visual;

            if (visual == null)
            {
                throw new InvalidOperationException(
                    $"JOIN question '{Question.Id}' has no visual metadata. " +
                    "Result-unknown JOIN requires either group_label, or both part_a_label and part_b_label.");
            }

            bool hasGroup =
                HasText(
                    visual.GroupLabel);

            bool hasPartA =
                HasText(
                    visual.PartALabel);

            bool hasPartB =
                HasText(
                    visual.PartBLabel);

            if (hasGroup &&
                !hasPartA &&
                !hasPartB)
            {
                resultLayout =
                    ResultWorkspaceLayout.SingleDestination;

                return;
            }

            if (!hasGroup &&
                hasPartA &&
                hasPartB)
            {
                resultLayout =
                    ResultWorkspaceLayout.TwoDestinations;

                return;
            }

            if (!hasGroup &&
                !hasPartA &&
                !hasPartB)
            {
                throw new InvalidOperationException(
                    $"JOIN question '{Question.Id}' is missing destination metadata. " +
                    "Use group_label for one destination, or part_a_label + part_b_label for two destinations. " +
                    "Unity will not infer JOIN structure from story text.");
            }

            throw new InvalidOperationException(
                $"JOIN question '{Question.Id}' has ambiguous destination metadata. " +
                $"group_label='{visual.GroupLabel ?? ""}', " +
                $"part_a_label='{visual.PartALabel ?? ""}', " +
                $"part_b_label='{visual.PartBLabel ?? ""}'. " +
                "Use exactly one JOIN layout: group_label OR the part_a/part_b pair.");
        }

        private void BuildLegacyChangeUnknownWorkspace()
        {
            WorkspaceLayoutEngine.TwoColumns(
                Host.DeskGeometry,
                Host.DepthUsage,
                Host.SideMargin,
                Host.RegionGap,
                out RegionPlacement left,
                out RegionPlacement right);

            int candidateCount =
                Host.GetUnknownJoinCandidateCount(
                    statedChangeCount);

            int totalCapacity =
                Mathf.Max(
                    1,
                    initialCount + candidateCount);

            changeRegion =
                Host.CreateRegion(
                    "JoinAvailableObjects",
                    left,
                    totalCapacity,
                    Host.TextCatalog.ObjectsToTry,
                    WorkspaceRegionStyle.Neutral);

            initialRegion =
                Host.CreateRegion(
                    "JoinStartingCollection",
                    right,
                    totalCapacity,
                    Host.TextCatalog.StartingCollection,
                    WorkspaceRegionStyle.Neutral);

            initialObjects.AddRange(
                Host.SpawnObjects(
                    Question,
                    VisualRole.Initial,
                    initialCount,
                    initialRegion,
                    "Initial"));

            changeObjects.AddRange(
                Host.SpawnObjects(
                    Question,
                    VisualRole.Change,
                    candidateCount,
                    changeRegion,
                    "Candidate"));
        }

        public override bool CanPlace(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            if (targetRegion == null)
                return false;

            if (IsResultUnknown)
            {
                return resultLayout switch
                {
                    ResultWorkspaceLayout.SingleDestination =>
                        targetRegion == combinedRegion,

                    ResultWorkspaceLayout.TwoDestinations =>
                        targetRegion == initialRegion ||
                        targetRegion == changeRegion,

                    _ => false
                };
            }

            if (initialObjects.Contains(
                    manipulative))
            {
                return
                    targetRegion == initialRegion;
            }

            if (changeObjects.Contains(
                    manipulative))
            {
                return
                    targetRegion == changeRegion ||
                    targetRegion == initialRegion;
            }

            return false;
        }

        public override void OnPlacementChanged(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            // Result-unknown JOIN state is derived from live region contents.
        }

        public override bool TryGetLearnerState(
            out object learnerState)
        {
            if (IsResultUnknown)
            {
                int totalCount =
                    CurrentPhysicalTotal();

                bool distinctSources =
                    HasDistinctSemanticSources();

                int? partACount = null;
                int? partBCount = null;

                string partALabel = null;
                string partBLabel = null;
                string destinationLabel = null;
                string workspaceMode;

                if (resultLayout ==
                    ResultWorkspaceLayout.SingleDestination)
                {
                    workspaceMode =
                        distinctSources
                            ? "single_destination_two_sources"
                            : "single_destination_one_source";

                    destinationLabel =
                        Question.Visual.GroupLabel?.Trim();

                    if (distinctSources)
                    {
                        partALabel =
                            InitialSemanticLabel();

                        partBLabel =
                            ChangeSemanticLabel();

                        partACount =
                            combinedRegion?.CountOccupantsByRole(
                                VisualRole.Initial) ?? 0;

                        partBCount =
                            combinedRegion?.CountOccupantsByRole(
                                VisualRole.Change) ?? 0;
                    }
                }
                else
                {
                    workspaceMode =
                        "two_destinations";

                    partALabel =
                        Question.Visual.PartALabel?.Trim();

                    partBLabel =
                        Question.Visual.PartBLabel?.Trim();

                    partACount =
                        initialRegion?.OccupantCount ?? 0;

                    partBCount =
                        changeRegion?.OccupantCount ?? 0;
                }

                learnerState =
                    new JoinLearnerStateDto
                    {
                        // Keep legacy keys alive, but make current_count the
                        // actual physical construction rather than a presumed
                        // initial collection.
                        AddedCount =
                            Mathf.Max(
                                0,
                                totalCount - initialCount),
                        CurrentCount = totalCount,
                        Answer = null,

                        WorkspaceMode = workspaceMode,
                        DestinationLabel = destinationLabel,
                        PartALabel = partALabel,
                        PartBLabel = partBLabel,
                        PartACount = partACount,
                        PartBCount = partBCount,
                        TotalCount = totalCount,
                        StoryQuantitiesPreSpawned = false
                    };

                return true;
            }

            int addedCount =
                CountInRegion(
                    changeObjects,
                    initialRegion);

            learnerState =
                new JoinLearnerStateDto
                {
                    AddedCount = addedCount,
                    CurrentCount = initialCount + addedCount,
                    TotalCount = initialCount + addedCount,
                    WorkspaceMode = "legacy_change_unknown",
                    StoryQuantitiesPreSpawned = true,
                    Answer = null
                };

            return true;
        }

        public override bool HasMeaningfulAttempt()
        {
            if (IsResultUnknown)
            {
                if (resultLayout ==
                    ResultWorkspaceLayout.SingleDestination)
                {
                    return
                        (combinedRegion?.OccupantCount ?? 0) > 0;
                }

                return
                    (initialRegion?.OccupantCount ?? 0) > 0 ||
                    (changeRegion?.OccupantCount ?? 0) > 0;
            }

            return
                CountInRegion(
                    changeObjects,
                    initialRegion) > 0;
        }

        public override string GetStateSignature()
        {
            if (IsResultUnknown)
            {
                bool distinctSources =
                    HasDistinctSemanticSources();

                if (resultLayout ==
                    ResultWorkspaceLayout.SingleDestination)
                {
                    return SerializeSignature(
                        new
                        {
                            mode =
                                distinctSources
                                    ? "result_single_two_sources"
                                    : "result_single_one_source",
                            destination =
                                Question.Visual.GroupLabel,
                            initial_role_count =
                                distinctSources
                                    ? combinedRegion?.CountOccupantsByRole(
                                        VisualRole.Initial) ?? 0
                                    : 0,
                            change_role_count =
                                distinctSources
                                    ? combinedRegion?.CountOccupantsByRole(
                                        VisualRole.Change) ?? 0
                                    : 0,
                            total =
                                combinedRegion?.OccupantCount ?? 0
                        });
                }

                return SerializeSignature(
                    new
                    {
                        mode = "result_split",
                        part_a_label =
                            Question.Visual.PartALabel,
                        part_a =
                            initialRegion?.OccupantCount ?? 0,
                        part_b_label =
                            Question.Visual.PartBLabel,
                        part_b =
                            changeRegion?.OccupantCount ?? 0,
                        total =
                            (initialRegion?.OccupantCount ?? 0) +
                            (changeRegion?.OccupantCount ?? 0)
                    });
            }

            return SerializeSignature(
                new
                {
                    mode = "change",
                    initial_in_initial =
                        CountInRegion(
                            initialObjects,
                            initialRegion),
                    change_in_initial =
                        CountInRegion(
                            changeObjects,
                            initialRegion),
                    change_in_change =
                        CountInRegion(
                            changeObjects,
                            changeRegion)
                });
        }

        public override string BuildMoveAction(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
            if (!IsResultUnknown)
            {
                string legacyLabel =
                    ObjectLabel();

                if (newRegion == initialRegion)
                {
                    return
                        WorkspaceActionFormatter.JoinChangeMovedIn(
                            legacyLabel);
                }

                return
                    WorkspaceActionFormatter.JoinChangeMovedOut(
                        legacyLabel);
            }

            string objectLabel =
                SemanticObjectLabel(
                    manipulative);

            if (resultLayout ==
                ResultWorkspaceLayout.SingleDestination)
            {
                return
                    $"Moved one {objectLabel} to {Question.Visual.GroupLabel.Trim()}.";
            }

            if (newRegion == initialRegion)
            {
                return
                    $"Moved one {objectLabel} to {Question.Visual.PartALabel.Trim()}.";
            }

            if (newRegion == changeRegion)
            {
                return
                    $"Moved one {objectLabel} to {Question.Visual.PartBLabel.Trim()}.";
            }

            return
                $"Moved one {objectLabel}.";
        }

        public override string AdaptTutorText(
            string text)
        {
            return text;
        }

        public override string BuildTutorContext()
        {
            if (!IsResultUnknown)
                return "";

            const string visibilityRule =
                "Story quantities are NOT pre-spawned or automatically visible; " +
                "only the following learner-constructed counts are physically present.";

            if (resultLayout ==
                ResultWorkspaceLayout.SingleDestination)
            {
                int total =
                    combinedRegion?.OccupantCount ?? 0;

                if (HasDistinctSemanticSources())
                {
                    int initialRoleCount =
                        combinedRegion?.CountOccupantsByRole(
                            VisualRole.Initial) ?? 0;

                    int changeRoleCount =
                        combinedRegion?.CountOccupantsByRole(
                            VisualRole.Change) ?? 0;

                    return
                        $"Physical workspace state: {Question.Visual.GroupLabel}: " +
                        $"{InitialSemanticLabel()} count = {initialRoleCount}, " +
                        $"{ChangeSemanticLabel()} count = {changeRoleCount}, " +
                        $"total = {total}. {visibilityRule}";
                }

                return
                    $"Physical workspace state: {Question.Visual.GroupLabel}: " +
                    $"total {ObjectPlural()} physically placed = {total}. " +
                    $"{visibilityRule}";
            }

            int partA =
                initialRegion?.OccupantCount ?? 0;

            int partB =
                changeRegion?.OccupantCount ?? 0;

            return
                $"Physical workspace state: {Question.Visual.PartALabel} count = {partA}; " +
                $"{Question.Visual.PartBLabel} count = {partB}; " +
                $"total physically placed = {partA + partB}. {visibilityRule}";
        }

        private int CurrentPhysicalTotal()
        {
            if (resultLayout ==
                ResultWorkspaceLayout.SingleDestination)
            {
                return
                    combinedRegion?.OccupantCount ?? 0;
            }

            return
                (initialRegion?.OccupantCount ?? 0) +
                (changeRegion?.OccupantCount ?? 0);
        }

        private bool HasDistinctSemanticSources()
        {
            return
                !string.Equals(
                    InitialSemanticLabel(),
                    ChangeSemanticLabel(),
                    StringComparison.OrdinalIgnoreCase);
        }

        private string InitialSemanticLabel()
        {
            return FirstNonEmpty(
                Question.Visual?.InitialObjectLabel,
                Question.Visual?.ObjectLabel,
                "object");
        }

        private string ChangeSemanticLabel()
        {
            return FirstNonEmpty(
                Question.Visual?.ChangeObjectLabel,
                Question.Visual?.ObjectLabel,
                "object");
        }

        private string SemanticObjectLabel(
            ManipulativeObject manipulative)
        {
            QuestionVisualDto visual =
                Question.Visual;

            if (visual == null)
                return ObjectLabel();

            if (manipulative != null &&
                manipulative.SemanticVisualRole ==
                VisualRole.Change)
            {
                return FirstNonEmpty(
                    visual.ChangeObjectLabel,
                    visual.ObjectLabel,
                    "object");
            }

            if (manipulative != null &&
                manipulative.SemanticVisualRole ==
                VisualRole.Initial)
            {
                return FirstNonEmpty(
                    visual.InitialObjectLabel,
                    visual.ObjectLabel,
                    "object");
            }

            return FirstNonEmpty(
                visual.ObjectLabel,
                visual.InitialObjectLabel,
                visual.ChangeObjectLabel,
                "object");
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
            if (values != null)
            {
                foreach (string value in values)
                {
                    if (HasText(value))
                        return value.Trim();
                }
            }

            return "object";
        }
    }
}