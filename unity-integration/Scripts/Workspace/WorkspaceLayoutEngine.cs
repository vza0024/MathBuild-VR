using System.Collections.Generic;
using UnityEngine;

namespace MathConstructVR.Core
{
    public readonly struct DeskSurfaceGeometry
    {
        public DeskSurfaceGeometry(
            Vector3 center,
            Quaternion rotation,
            Vector3 right,
            Vector3 forward,
            float width,
            float depth)
        {
            Center = center;
            Rotation = rotation;
            Right = right;
            Forward = forward;
            Width = width;
            Depth = depth;
        }

        public Vector3 Center { get; }
        public Quaternion Rotation { get; }
        public Vector3 Right { get; }
        public Vector3 Forward { get; }
        public float Width { get; }
        public float Depth { get; }

        public Vector3 Point(
            float localX,
            float localZ)
        {
            return
                Center +
                (Right * localX) +
                (Forward * localZ);
        }
    }

    public readonly struct RegionPlacement
    {
        public RegionPlacement(
            Vector3 position,
            Quaternion rotation,
            Vector2 size)
        {
            Position = position;
            Rotation = rotation;
            Size = size;
        }

        public Vector3 Position { get; }
        public Quaternion Rotation { get; }
        public Vector2 Size { get; }
    }

    public static class WorkspaceLayoutEngine
    {
        public static void TwoColumns(
            DeskSurfaceGeometry desk,
            float depthUsage,
            float sideMargin,
            float gap,
            out RegionPlacement left,
            out RegionPlacement right)
        {
            float usableWidth =
                Mathf.Max(
                    0.3f,
                    desk.Width - (sideMargin * 2f));

            float regionWidth =
                Mathf.Max(
                    0.12f,
                    (usableWidth - gap) * 0.5f);

            float regionDepth =
                Mathf.Max(
                    0.12f,
                    desk.Depth * depthUsage);

            float centerOffset =
                (regionWidth + gap) * 0.5f;

            left =
                new RegionPlacement(
                    desk.Point(-centerOffset, 0f),
                    desk.Rotation,
                    new Vector2(regionWidth, regionDepth));

            right =
                new RegionPlacement(
                    desk.Point(centerOffset, 0f),
                    desk.Rotation,
                    new Vector2(regionWidth, regionDepth));
        }

        public static RegionPlacement SingleRegion(
            DeskSurfaceGeometry desk,
            float depthUsage,
            float sideMargin)
        {
            float usableWidth =
                Mathf.Max(
                    0.3f,
                    desk.Width - (sideMargin * 2f));

            float regionDepth =
                Mathf.Max(
                    0.12f,
                    desk.Depth * depthUsage);

            return new RegionPlacement(
                desk.Point(0f, 0f),
                desk.Rotation,
                new Vector2(
                    usableWidth,
                    regionDepth));
        }

        public static void BankAndGrid(
            DeskSurfaceGeometry desk,
            float depthUsage,
            float sideMargin,
            float gap,
            float bankDepthFraction,
            float depthSign,
            int cellCount,
            out RegionPlacement bank,
            out List<RegionPlacement> cells)
        {
            float usableWidth =
                Mathf.Max(
                    0.3f,
                    desk.Width - (sideMargin * 2f));

            float usableDepth =
                Mathf.Max(
                    0.3f,
                    desk.Depth * depthUsage);

            if (cellCount <= 0)
            {
                bank =
                    new RegionPlacement(
                        desk.Point(0f, 0f),
                        desk.Rotation,
                        new Vector2(usableWidth, usableDepth));

                cells = new List<RegionPlacement>();
                return;
            }

            float clampedBankFraction =
                Mathf.Clamp(
                    bankDepthFraction,
                    0.22f,
                    0.45f);

            float bankDepth =
                Mathf.Max(
                    0.12f,
                    usableDepth * clampedBankFraction);

            float gridDepth =
                Mathf.Max(
                    0.12f,
                    usableDepth - bankDepth - gap);

            float direction = depthSign >= 0f ? 1f : -1f;

            float bankZ =
                direction * (gridDepth + gap) * 0.5f;

            float gridZ =
                -direction * (bankDepth + gap) * 0.5f;

            bank =
                new RegionPlacement(
                    desk.Point(0f, bankZ),
                    desk.Rotation,
                    new Vector2(usableWidth, bankDepth));

            cells =
                BuildGrid(
                    desk,
                    0f,
                    usableWidth,
                    gridDepth,
                    gridZ,
                    gap,
                    cellCount,
                    adaptiveShape: false);
        }

        public static void EqualSharingAdaptiveBands(
            DeskSurfaceGeometry desk,
            float sideMargin,
            float preferredGap,
            float preferredSlotSpacing,
            float depthSign,
            int bankSlotDemand,
            IReadOnlyList<int> recipientSlotDemands,
            out RegionPlacement bank,
            out List<RegionPlacement> recipients)
        {
            float usableWidth =
                desk.Width -
                (Mathf.Max(0f, sideMargin) * 2f);

            float usableDepth =
                desk.Depth;

            if (usableWidth <= 0f ||
                usableDepth <= 0f)
            {
                throw new System.InvalidOperationException(
                    $"Equal Sharing has no usable WorkspaceBounds area. " +
                    $"Desk is {desk.Width:F3}m x {desk.Depth:F3}m with {sideMargin:F3}m side margins.");
            }

            float spacing =
                Mathf.Max(
                    0.01f,
                    preferredSlotSpacing);

            float padding =
                spacing * 0.55f;

            float gap =
                Mathf.Clamp(
                    preferredGap,
                    0.025f,
                    0.06f);

            int recipientCount =
                recipientSlotDemands?.Count ?? 0;

            if (recipientCount <= 0)
            {
                bank =
                    new RegionPlacement(
                        desk.Point(0f, 0f),
                        desk.Rotation,
                        new Vector2(
                            usableWidth,
                            Mathf.Min(
                                usableDepth,
                                RequiredDepthForSlotsAtSpacing(
                                    Mathf.Max(1, bankSlotDemand),
                                    usableWidth,
                                    spacing,
                                    padding))));

                recipients =
                    new List<RegionPlacement>();

                return;
            }

            int safeBankDemand =
                Mathf.Max(
                    1,
                    bankSlotDemand);

            float bankDepth =
                RequiredDepthForSlotsAtSpacing(
                    safeBankDemand,
                    usableWidth,
                    spacing,
                    padding);

            // Preferred visual size for empty Equal Sharing recipient regions.
            // These are preferences, not hard minimums: when several recipient rows
            // share a shallow table, depth automatically contracts only as much as
            // needed to keep the current construction inside WorkspaceBounds.
            const float EQUAL_SHARING_PREFERRED_STARTING_DEPTH = 0.20f;
            const float EQUAL_SHARING_MINIMUM_ROW_DEPTH = 0.08f;
            const float EQUAL_SHARING_STARTING_BOX_WIDTH = 0.16f;
            const float rowGap = 0.035f;

            // Equal Sharing recipients stay in one horizontal row.
            // Width and depth still adapt to the real WorkspaceBounds and current occupancy.
            int columns = recipientCount;
            int rows = 1;

            float maximumRecipientDepth =
                usableDepth -
                bankDepth -
                gap;

            if (maximumRecipientDepth <= 0f)
            {
                throw new System.InvalidOperationException(
                    $"Equal Sharing bank does not leave room for recipients inside WorkspaceBounds. " +
                    $"Bank needs {bankDepth:F3}m depth, gap is {gap:F3}m, and desk depth is {usableDepth:F3}m.");
            }

            float rowGapsDepth =
                (rows - 1) * rowGap;

            float availableRowsDepth =
                maximumRecipientDepth -
                rowGapsDepth;

            if (availableRowsDepth <= 0f)
            {
                throw new System.InvalidOperationException(
                    $"Equal Sharing recipient rows do not fit inside WorkspaceBounds. " +
                    $"The row gaps alone need {rowGapsDepth:F3}m, while only {maximumRecipientDepth:F3}m remains after the bank.");
            }

            // First determine the true content-driven minimum for every row.
            // This is the depth required by the learner's current placement plus
            // one available drop slot, independent of the preferred visual size.
            float[] minimumRowDepths =
                new float[rows];

            float minimumRowsDepth = 0f;

            for (int row = 0;
                 row < rows;
                 row++)
            {
                int first =
                    row * columns;

                int countInRow =
                    Mathf.Min(
                        columns,
                        recipientCount - first);

                float rowMinimumRecipientWidth =
                    Mathf.Min(
                        EQUAL_SHARING_STARTING_BOX_WIDTH,
                        (usableWidth - (gap * (countInRow - 1))) / countInRow);

                float rowDepth =
                    FindMinimumRowDepth(
                        usableWidth,
                        gap,
                        spacing,
                        padding,
                        recipientSlotDemands,
                        first,
                        countInRow,
                        EQUAL_SHARING_MINIMUM_ROW_DEPTH,
                        rowMinimumRecipientWidth,
                        maximumRecipientDepth);

                if (rowDepth >
                    maximumRecipientDepth + 0.0001f)
                {
                    throw new System.InvalidOperationException(
                        $"Equal Sharing recipient row {row + 1} cannot fit the current learner construction " +
                        $"inside the {usableWidth:F3}m workspace width at preferred spacing.");
                }

                minimumRowDepths[row] =
                    rowDepth;

                minimumRowsDepth +=
                    rowDepth;
            }

            if (minimumRowsDepth >
                availableRowsDepth + 0.0001f)
            {
                float minimumRecipientAreaDepth =
                    minimumRowsDepth +
                    rowGapsDepth;

                throw new System.InvalidOperationException(
                    $"Equal Sharing current construction does not fit inside WorkspaceBounds at preferred spacing. " +
                    $"Current bank needs {bankDepth:F3}m, recipients need at least {minimumRecipientAreaDepth:F3}m, " +
                    $"and the bank gap needs {gap:F3}m, but desk depth is {usableDepth:F3}m. " +
                    $"This uses only the learner's current placement plus one available drop slot per region.");
            }

            // Grow each row toward the preferred starting depth only when physical
            // table depth is available. If the preferred size would overflow, all
            // rows contract proportionally toward their true content minimums.
            float preferredExtraDepth = 0f;

            for (int row = 0;
                 row < rows;
                 row++)
            {
                preferredExtraDepth +=
                    Mathf.Max(
                        0f,
                        EQUAL_SHARING_PREFERRED_STARTING_DEPTH - minimumRowDepths[row]);
            }

            float availableExtraDepth =
                Mathf.Max(
                    0f,
                    availableRowsDepth - minimumRowsDepth);

            float preferredDepthScale =
                preferredExtraDepth > 0.0001f
                    ? Mathf.Min(
                        1f,
                        availableExtraDepth / preferredExtraDepth)
                    : 0f;

            float[] rowDepths =
                new float[rows];

            float recipientAreaDepth =
                rowGapsDepth;

            for (int row = 0;
                 row < rows;
                 row++)
            {
                float preferredExtraForRow =
                    Mathf.Max(
                        0f,
                        EQUAL_SHARING_PREFERRED_STARTING_DEPTH - minimumRowDepths[row]);

                rowDepths[row] =
                    minimumRowDepths[row] +
                    (preferredExtraForRow * preferredDepthScale);

                recipientAreaDepth +=
                    rowDepths[row];
            }

            float direction =
                depthSign >= 0f
                    ? 1f
                    : -1f;

            // Use only the physical area required by the current construction.
            // Unused tabletop remains unused instead of being inflated into
            // oversized recipient regions. The whole construction stays centered.
            float bankZ =
                direction *
                (recipientAreaDepth + gap) *
                0.5f;

            float recipientAreaCenterZ =
                -direction *
                (bankDepth + gap) *
                0.5f;

            bank =
                new RegionPlacement(
                    desk.Point(
                        0f,
                        bankZ),
                    desk.Rotation,
                    new Vector2(
                        usableWidth,
                        bankDepth));

            recipients =
                new List<RegionPlacement>(
                    recipientCount);

            float rowCursor =
                recipientAreaDepth * 0.5f;

            for (int row = 0;
                 row < rows;
                 row++)
            {
                float rowDepth =
                    rowDepths[row];

                float rowLocalZ =
                    rowCursor -
                    (rowDepth * 0.5f);

                float rowCenterZ =
                    recipientAreaCenterZ +
                    (direction * rowLocalZ);

                int first =
                    row * columns;

                int countInRow =
                    Mathf.Min(
                        columns,
                        recipientCount - first);

                float[] widths =
                    new float[countInRow];

                float rowMinimumRecipientWidth =
                    Mathf.Min(
                        EQUAL_SHARING_STARTING_BOX_WIDTH,
                        (usableWidth - (gap * (countInRow - 1))) / countInRow);

                float rowUsedWidth =
                    gap *
                    (countInRow - 1);

                for (int offset = 0;
                     offset < countInRow;
                     offset++)
                {
                    int demand =
                        Mathf.Max(
                            1,
                            recipientSlotDemands[first + offset]);

                    float width =
                        Mathf.Max(
                            rowMinimumRecipientWidth,
                            RequiredWidthForSlotsAtSpacing(
                                demand,
                                rowDepth,
                                spacing,
                                padding));

                    widths[offset] =
                        width;

                    rowUsedWidth +=
                        width;
                }

                if (rowUsedWidth >
                    usableWidth + 0.0001f)
                {
                    throw new System.InvalidOperationException(
                        $"Equal Sharing recipient row {row + 1} needs {rowUsedWidth:F3}m width, " +
                        $"but WorkspaceBounds provides {usableWidth:F3}m after side margins.");
                }

                // Positive desk-local X is learner-left in this scene.
                // Center the compact row while keeping recipient 1 on that side.
                float xCursor =
                    rowUsedWidth * 0.5f;

                for (int offset = 0;
                     offset < countInRow;
                     offset++)
                {
                    float width =
                        widths[offset];

                    float centerX =
                        xCursor -
                        (width * 0.5f);

                    recipients.Add(
                        new RegionPlacement(
                            desk.Point(
                                centerX,
                                rowCenterZ),
                            desk.Rotation,
                            new Vector2(
                                width,
                                rowDepth)));

                    xCursor -=
                        width +
                        gap;
                }

                rowCursor -=
                    rowDepth +
                    rowGap;
            }
        }


        private static float FindMinimumRowDepth(
            float usableWidth,
            float horizontalGap,
            float spacing,
            float padding,
            IReadOnlyList<int> demands,
            int firstIndex,
            int count,
            float minimumDepth,
            float minimumWidth,
            float maximumDepth)
        {
            float depth =
                minimumDepth;

            const float searchStep = 0.01f;

            while (depth <=
                   maximumDepth + 0.0001f)
            {
                float widthSum = 0f;

                for (int offset = 0;
                     offset < count;
                     offset++)
                {
                    int demand =
                        Mathf.Max(
                            1,
                            demands[firstIndex + offset]);

                    widthSum +=
                        Mathf.Max(
                            minimumWidth,
                            RequiredWidthForSlotsAtSpacing(
                                demand,
                                depth,
                                spacing,
                                padding));
                }

                float required =
                    widthSum +
                    (horizontalGap *
                     (count - 1));

                if (required <=
                    usableWidth)
                {
                    return depth;
                }

                depth +=
                    searchStep;
            }

            return
                maximumDepth +
                searchStep;
        }


        private static float RequiredDepthForSlotsAtSpacing(
            int slotCount,
            float regionWidth,
            float spacing,
            float padding)
        {
            int safeCount =
                Mathf.Max(
                    1,
                    slotCount);

            float usableWidth =
                Mathf.Max(
                    0.01f,
                    regionWidth -
                    (padding * 2f));

            int columns =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableWidth / spacing) + 1);

            columns =
                Mathf.Min(
                    columns,
                    safeCount);

            int rows =
                Mathf.CeilToInt(
                    safeCount /
                    (float)columns);

            return
                Mathf.Max(
                    0.08f,
                    (padding * 2f) +
                    ((rows - 1) * spacing));
        }


        private static float RequiredWidthForSlotsAtSpacing(
            int slotCount,
            float regionDepth,
            float spacing,
            float padding)
        {
            int safeCount =
                Mathf.Max(
                    1,
                    slotCount);

            float usableDepth =
                Mathf.Max(
                    0.01f,
                    regionDepth -
                    (padding * 2f));

            int rows =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableDepth / spacing) + 1);

            rows =
                Mathf.Min(
                    rows,
                    safeCount);

            int columns =
                Mathf.CeilToInt(
                    safeCount /
                    (float)rows);

            return
                Mathf.Max(
                    0.08f,
                    (padding * 2f) +
                    ((columns - 1) * spacing));
        }


        public static void EqualGroupsBankAndGrid(
            DeskSurfaceGeometry desk,
            float depthUsage,
            float sideMargin,
            float gap,
            float minimumBankWidthFraction,
            float preferredSlotSpacing,
            int bankSlotCount,
            int groupCount,
            out RegionPlacement bank,
            out List<RegionPlacement> groups)
        {
            float usableWidth =
                Mathf.Max(
                    0.3f,
                    desk.Width - (sideMargin * 2f));

            float usableDepth =
                Mathf.Max(
                    0.3f,
                    desk.Depth * depthUsage);

            float safeSlotSpacing =
                Mathf.Max(
                    0.02f,
                    preferredSlotSpacing);

            /*
             * WorkspaceRegionView puts each title outside the dotted border.
             * Equal Groups can have multiple rows, so the layout must reserve
             * real desk space for that title instead of pretending the border
             * owns the whole cell. This prevents titles from colliding with
             * the next row or hanging off the table.
             *
             * The current authored WorkspaceRegion prefab places titles on
             * the negative local-Z edge. The helper below reserves a header
             * gutter on that side of every bank/group footprint.
             */
            const float titleGutter = 0.14f;

            if (groupCount <= 0)
            {
                bank =
                    BuildSinglePlacementWithTitleGutter(
                        desk,
                        0f,
                        usableWidth,
                        usableDepth,
                        0f,
                        titleGutter);

                groups = new List<RegionPlacement>();
                return;
            }

            float clampedPreferredBankFraction =
                Mathf.Clamp(
                    minimumBankWidthFraction,
                    0.20f,
                    0.50f);

            float minimumGroupAreaWidth =
                Mathf.Max(
                    0.18f,
                    safeSlotSpacing * 1.8f);

            float maximumBankWidth =
                Mathf.Max(
                    0.12f,
                    usableWidth - gap - minimumGroupAreaWidth);

            int safeBankSlotCount =
                Mathf.Max(
                    1,
                    bankSlotCount);

            // When very few objects remain, the bank should become a compact
            // return/drop area instead of permanently consuming ~30-40% of
            // the desk. As occupancy grows, its preferred minimum smoothly
            // approaches the configured fraction, and FindBankWidthThatFitsSlots
            // can still expand it further when the objects genuinely need room.
            float compactBankWidth =
                Mathf.Max(
                    0.13f,
                    safeSlotSpacing * 1.6f);

            float configuredBankWidth =
                Mathf.Max(
                    compactBankWidth,
                    usableWidth * clampedPreferredBankFraction);

            float occupancyPressure =
                Mathf.InverseLerp(
                    1f,
                    10f,
                    safeBankSlotCount);

            float adaptiveMinimumBankWidth =
                Mathf.Lerp(
                    compactBankWidth,
                    configuredBankWidth,
                    occupancyPressure);

            float minimumBankWidth =
                Mathf.Min(
                    maximumBankWidth,
                    adaptiveMinimumBankWidth);

            // Slots live inside the dotted border, not in the title gutter.
            float bankRegionDepth =
                Mathf.Max(
                    0.12f,
                    usableDepth - titleGutter);

            float bankWidth =
                FindBankWidthThatFitsSlots(
                    safeBankSlotCount,
                    bankRegionDepth,
                    safeSlotSpacing,
                    minimumBankWidth,
                    maximumBankWidth);

            float groupAreaWidth =
                Mathf.Max(
                    0.12f,
                    usableWidth - bankWidth - gap);

            // In this classroom desk orientation, positive local X is the
            // learner's left. The bank therefore remains on the learner's
            // left and the generated groups occupy the learner's right.
            float bankCenterX =
                (groupAreaWidth + gap) * 0.5f;

            float groupsCenterX =
                -(bankWidth + gap) * 0.5f;

            bank =
                BuildSinglePlacementWithTitleGutter(
                    desk,
                    bankCenterX,
                    bankWidth,
                    usableDepth,
                    0f,
                    titleGutter);

            // Predictable pedagogical layout:
            // 1-3 -> one row, 4 -> 2x2, 5-6 -> 3x2, etc.
            GetGridShape(
                groupCount,
                out int groupColumns,
                out int groupRows);

            groups =
                BuildGridWithTitleGutter(
                    desk,
                    groupsCenterX,
                    groupAreaWidth,
                    usableDepth,
                    0f,
                    gap,
                    groupCount,
                    groupColumns,
                    groupRows,
                    titleGutter,
                    reverseColumns: true);
        }

        public static void EqualGroupsGridOnly(
            DeskSurfaceGeometry desk,
            float depthUsage,
            float sideMargin,
            float gap,
            int groupCount,
            out List<RegionPlacement> groups)
        {
            float usableWidth =
                Mathf.Max(
                    0.3f,
                    desk.Width - (sideMargin * 2f));

            float usableDepth =
                Mathf.Max(
                    0.3f,
                    desk.Depth * depthUsage);

            const float titleGutter = 0.06f;

            if (groupCount <= 0)
            {
                groups =
                    new List<RegionPlacement>();

                return;
            }

            GetGridShape(
                groupCount,
                out int columns,
                out int rows);

            // Positive local X is the learner's left in this classroom scene.
            // reverseColumns=true therefore keeps Group 1 on learner-left.
            groups =
                BuildGridWithTitleGutter(
                    desk,
                    0f,
                    usableWidth,
                    usableDepth,
                    0f,
                    Mathf.Min(gap, 0.055f),
                    groupCount,
                    columns,
                    rows,
                    titleGutter,
                    reverseColumns: true);
        }


        public static void RatioFourRegions(
            DeskSurfaceGeometry desk,
            float depthUsage,
            float sideMargin,
            float horizontalGap,
            float verticalGap,
            float depthSign,
            out RegionPlacement bankA,
            out RegionPlacement bankB,
            out RegionPlacement targetA,
            out RegionPlacement targetB)
        {
            float usableWidth =
                Mathf.Max(
                    0.3f,
                    desk.Width - (sideMargin * 2f));

            float usableDepth =
                Mathf.Max(
                    0.3f,
                    desk.Depth * depthUsage);

            float regionWidth =
                Mathf.Max(
                    0.12f,
                    (usableWidth - horizontalGap) * 0.5f);

            float regionDepth =
                Mathf.Max(
                    0.12f,
                    (usableDepth - verticalGap) * 0.5f);

            float xOffset =
                (regionWidth + horizontalGap) * 0.5f;

            float zOffset =
                (regionDepth + verticalGap) * 0.5f;

            float direction = depthSign >= 0f ? 1f : -1f;
            float bankZ = direction * zOffset;
            float targetZ = -direction * zOffset;

            bankA =
                new RegionPlacement(
                    desk.Point(-xOffset, bankZ),
                    desk.Rotation,
                    new Vector2(regionWidth, regionDepth));

            bankB =
                new RegionPlacement(
                    desk.Point(xOffset, bankZ),
                    desk.Rotation,
                    new Vector2(regionWidth, regionDepth));

            targetA =
                new RegionPlacement(
                    desk.Point(-xOffset, targetZ),
                    desk.Rotation,
                    new Vector2(regionWidth, regionDepth));

            targetB =
                new RegionPlacement(
                    desk.Point(xOffset, targetZ),
                    desk.Rotation,
                    new Vector2(regionWidth, regionDepth));
        }

        private static float FindBankWidthThatFitsSlots(
            int slotCount,
            float regionDepth,
            float preferredSlotSpacing,
            float minimumWidth,
            float maximumWidth)
        {
            if (slotCount <= 1 ||
                maximumWidth <= minimumWidth)
            {
                return minimumWidth;
            }

            // WorkspaceRegion uses preferred spacing when there is room, then
            // compresses it to fit. We allow some compression, but not enough
            // that manipulatives are packed almost on top of one another.
            float minimumAcceptableSpacing =
                preferredSlotSpacing * 0.72f;

            const int samples = 80;

            for (int index = 0; index <= samples; index++)
            {
                float width =
                    Mathf.Lerp(
                        minimumWidth,
                        maximumWidth,
                        index / (float)samples);

                float effectiveSpacing =
                    CalculateEffectiveSlotSpacing(
                        width,
                        regionDepth,
                        slotCount,
                        preferredSlotSpacing);

                if (effectiveSpacing >= minimumAcceptableSpacing)
                {
                    return width;
                }
            }

            // The desk is physically too small to retain the desired spacing.
            // Give the bank everything we safely can while still leaving a
            // usable group area. WorkspaceRegion will compress the slots as a
            // last-resort fallback rather than overlapping other UI.
            return maximumWidth;
        }

        private static float CalculateEffectiveSlotSpacing(
            float regionWidth,
            float regionDepth,
            int capacity,
            float preferredSlotSpacing)
        {
            float padding =
                preferredSlotSpacing * 0.55f;

            float usableWidth =
                Mathf.Max(
                    0.01f,
                    regionWidth - (padding * 2f));

            float usableDepth =
                Mathf.Max(
                    0.01f,
                    regionDepth - (padding * 2f));

            int columns =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableWidth /
                        preferredSlotSpacing) + 1);

            columns =
                Mathf.Min(
                    columns,
                    capacity);

            int rows =
                Mathf.CeilToInt(
                    capacity /
                    (float)columns);

            float xSpacing =
                columns <= 1
                    ? preferredSlotSpacing
                    : Mathf.Min(
                        preferredSlotSpacing,
                        usableWidth /
                        (columns - 1));

            float zSpacing =
                rows <= 1
                    ? preferredSlotSpacing
                    : Mathf.Min(
                        preferredSlotSpacing,
                        usableDepth /
                        (rows - 1));

            if (columns <= 1)
                return zSpacing;

            if (rows <= 1)
                return xSpacing;

            return Mathf.Min(
                xSpacing,
                zSpacing);
        }

        private static List<RegionPlacement> BuildGrid(
            DeskSurfaceGeometry desk,
            float centerX,
            float width,
            float depth,
            float centerZ,
            float gap,
            int count,
            bool adaptiveShape)
        {
            List<RegionPlacement> placements =
                new List<RegionPlacement>();

            if (count <= 0)
                return placements;

            if (adaptiveShape)
            {
                GetAdaptiveGridShape(
                    width,
                    depth,
                    gap,
                    count,
                    out int adaptiveColumns,
                    out int adaptiveRows);

                return BuildGridWithShape(
                    desk,
                    centerX,
                    width,
                    depth,
                    centerZ,
                    gap,
                    count,
                    adaptiveColumns,
                    adaptiveRows);
            }

            GetGridShape(
                count,
                out int columns,
                out int rows);

            return BuildGridWithShape(
                desk,
                centerX,
                width,
                depth,
                centerZ,
                gap,
                count,
                columns,
                rows);
        }

        private static RegionPlacement BuildSinglePlacementWithTitleGutter(
            DeskSurfaceGeometry desk,
            float centerX,
            float footprintWidth,
            float footprintDepth,
            float centerZ,
            float titleGutter)
        {
            float safeGutter =
                Mathf.Clamp(
                    titleGutter,
                    0f,
                    Mathf.Max(0f, footprintDepth - 0.08f));

            float regionDepth =
                Mathf.Max(
                    0.08f,
                    footprintDepth - safeGutter);

            // Title is authored outside the negative local-Z edge. Shift the
            // dotted region toward +Z so the reserved gutter remains inside
            // the overall workspace footprint.
            float regionCenterZ =
                centerZ + (safeGutter * 0.5f);

            return
                new RegionPlacement(
                    desk.Point(centerX, regionCenterZ),
                    desk.Rotation,
                    new Vector2(
                        footprintWidth,
                        regionDepth));
        }

        private static List<RegionPlacement> BuildGridWithTitleGutter(
            DeskSurfaceGeometry desk,
            float centerX,
            float width,
            float depth,
            float centerZ,
            float gap,
            int count,
            int columns,
            int rows,
            float titleGutter,
            bool reverseColumns = false)
        {
            List<RegionPlacement> placements =
                new List<RegionPlacement>();

            float cellWidth =
                Mathf.Max(
                    0.01f,
                    (width - (gap * (columns - 1))) /
                    columns);

            // Each row gets a complete footprint. The dotted region uses the
            // footprint minus its title gutter, so row labels cannot overlap
            // the border/objects in the row next to them.
            float footprintDepth =
                Mathf.Max(
                    0.01f,
                    (depth - (gap * (rows - 1))) /
                    rows);

            float safeGutter =
                Mathf.Clamp(
                    titleGutter,
                    0f,
                    Mathf.Max(0f, footprintDepth - 0.08f));

            float regionDepth =
                Mathf.Max(
                    0.08f,
                    footprintDepth - safeGutter);

            float totalGridDepth =
                (rows * footprintDepth) +
                ((rows - 1) * gap);

            for (int index = 0; index < count; index++)
            {
                int row = index / columns;
                int column = index % columns;

                int firstIndexInRow = row * columns;
                int itemsInThisRow =
                    Mathf.Min(
                        columns,
                        count - firstIndexInRow);

                float rowWidth =
                    (itemsInThisRow * cellWidth) +
                    ((itemsInThisRow - 1) * gap);

                int placementColumn =
                    reverseColumns
                        ? (itemsInThisRow - 1 - column)
                        : column;

                float x =
                    centerX +
                    (-rowWidth * 0.5f) +
                    (cellWidth * 0.5f) +
                    (placementColumn * (cellWidth + gap));

                float footprintCenterZ =
                    centerZ +
                    (totalGridDepth * 0.5f) -
                    (footprintDepth * 0.5f) -
                    (row * (footprintDepth + gap));

                float regionCenterZ =
                    footprintCenterZ +
                    (safeGutter * 0.5f);

                placements.Add(
                    new RegionPlacement(
                        desk.Point(x, regionCenterZ),
                        desk.Rotation,
                        new Vector2(
                            cellWidth,
                            regionDepth)));
            }

            return placements;
        }

        private static List<RegionPlacement> BuildGridWithShape(
            DeskSurfaceGeometry desk,
            float centerX,
            float width,
            float depth,
            float centerZ,
            float gap,
            int count,
            int columns,
            int rows,
            bool reverseColumns = false)
        {
            List<RegionPlacement> placements =
                new List<RegionPlacement>();

            float cellWidth =
                Mathf.Max(
                    0.01f,
                    (width - (gap * (columns - 1))) /
                    columns);

            float cellDepth =
                Mathf.Max(
                    0.01f,
                    (depth - (gap * (rows - 1))) /
                    rows);

            float totalGridDepth =
                (rows * cellDepth) +
                ((rows - 1) * gap);

            for (int index = 0; index < count; index++)
            {
                int row = index / columns;
                int column = index % columns;

                int firstIndexInRow = row * columns;
                int itemsInThisRow =
                    Mathf.Min(
                        columns,
                        count - firstIndexInRow);

                float rowWidth =
                    (itemsInThisRow * cellWidth) +
                    ((itemsInThisRow - 1) * gap);

                int placementColumn =
                    reverseColumns
                        ? (itemsInThisRow - 1 - column)
                        : column;

                float x =
                    centerX +
                    (-rowWidth * 0.5f) +
                    (cellWidth * 0.5f) +
                    (placementColumn * (cellWidth + gap));

                float z =
                    centerZ +
                    (totalGridDepth * 0.5f) -
                    (cellDepth * 0.5f) -
                    (row * (cellDepth + gap));

                placements.Add(
                    new RegionPlacement(
                        desk.Point(x, z),
                        desk.Rotation,
                        new Vector2(cellWidth, cellDepth)));
            }

            return placements;
        }

        private static void GetAdaptiveGridShape(
            float width,
            float depth,
            float gap,
            int count,
            out int bestColumns,
            out int bestRows)
        {
            bestColumns = 1;
            bestRows = count;

            float bestScore = float.NegativeInfinity;

            for (int columns = 1; columns <= count; columns++)
            {
                int rows =
                    Mathf.CeilToInt(
                        count / (float)columns);

                float cellWidth =
                    (width - (gap * (columns - 1))) /
                    columns;

                float cellDepth =
                    (depth - (gap * (rows - 1))) /
                    rows;

                if (cellWidth <= 0f ||
                    cellDepth <= 0f)
                {
                    continue;
                }

                float score =
                    Mathf.Min(
                        cellWidth,
                        cellDepth);

                if (score <= bestScore)
                    continue;

                bestScore = score;
                bestColumns = columns;
                bestRows = rows;
            }
        }

        private static void GetGridShape(
            int count,
            out int columns,
            out int rows)
        {
            if (count <= 3)
            {
                columns = count;
                rows = 1;
                return;
            }

            if (count == 4)
            {
                columns = 2;
                rows = 2;
                return;
            }

            if (count <= 6)
            {
                columns = 3;
                rows = 2;
                return;
            }

            if (count <= 8)
            {
                columns = 4;
                rows = 2;
                return;
            }

            columns =
                Mathf.CeilToInt(
                    Mathf.Sqrt(count));

            rows =
                Mathf.CeilToInt(
                    count / (float)columns);
        }
    }
}