using System;
using UnityEngine;

namespace MathConstructVR.Core
{
    [RequireComponent(typeof(BoxCollider))]
    public sealed class WorkspaceRegion : MonoBehaviour
    {
        [SerializeField]
        private WorkspaceRegionView view;

        private BoxCollider dropVolume;

        private Vector2 regionSize;
        private int capacity;
        private float slotSpacing;
        private float padding;

        private ManipulativeObject[] occupants;

        public int Capacity => capacity;
        public float PreferredSlotSpacing => slotSpacing;

        public WorkspaceRegionView View
        {
            get
            {
                EnsureReferences();
                return view;
            }
        }

        // Logical capacity belongs to the interaction. PhysicalSlotCapacity
        // belongs only to geometry. This separation prevents layout from
        // encoding or leaking a mathematical answer.
        public int PhysicalSlotCapacity =>
            CalculatePhysicalSlotCapacity();

        public int OccupantCount
        {
            get
            {
                if (occupants == null)
                    return 0;

                int count = 0;

                foreach (ManipulativeObject occupant in occupants)
                {
                    if (occupant != null)
                        count++;
                }

                return count;
            }
        }

        public int CountOccupantsByRole(
            VisualRole role)
        {
            if (occupants == null)
                return 0;

            int count = 0;

            foreach (ManipulativeObject occupant in occupants)
            {
                if (occupant != null &&
                    occupant.SemanticVisualRole == role)
                {
                    count++;
                }
            }

            return count;
        }

        private void Awake()
        {
            EnsureReferences();
        }

        private void EnsureReferences()
        {
            if (dropVolume == null)
            {
                dropVolume = GetComponent<BoxCollider>();
            }

            if (view == null)
            {
                view = GetComponent<WorkspaceRegionView>();
            }
        }

        public void Configure(
            Vector3 worldPosition,
            Quaternion worldRotation,
            Vector2 size,
            int slotCapacity,
            float preferredSlotSpacing,
            string title,
            WorkspaceRegionStyle style)
        {
            EnsureReferences();

            capacity = Mathf.Max(1, slotCapacity);
            slotSpacing = Mathf.Max(0.01f, preferredSlotSpacing);
            padding = slotSpacing * 0.55f;

            occupants = new ManipulativeObject[capacity];

            ApplyLayout(
                worldPosition,
                worldRotation,
                size,
                title,
                style,
                refreshOccupants: false);
        }

        public void SetTitleOnPositiveZEdge(
            bool value)
        {
            EnsureReferences();

            if (view != null)
            {
                view.SetTitleOnPositiveZEdge(
                    value);
            }
        }


        public void Reflow(
            Vector3 worldPosition,
            Quaternion worldRotation,
            Vector2 size,
            string title,
            WorkspaceRegionStyle style)
        {
            EnsureReferences();

            ApplyLayout(
                worldPosition,
                worldRotation,
                size,
                title,
                style,
                refreshOccupants: true);
        }

        public void ResizeCapacity(
            int requestedCapacity)
        {
            EnsureReferences();

            int occupantCount = OccupantCount;

            int newCapacity =
                Mathf.Max(
                    1,
                    Mathf.Max(
                        occupantCount,
                        requestedCapacity));

            if (newCapacity == capacity)
                return;

            // Growing never requires compaction. Preserve every existing slot
            // index so a second hand can keep holding another object safely.
            if (newCapacity > capacity)
            {
                ManipulativeObject[] expanded =
                    new ManipulativeObject[newCapacity];

                if (occupants != null)
                {
                    Array.Copy(
                        occupants,
                        expanded,
                        occupants.Length);
                }

                occupants = expanded;
                capacity = newCapacity;
                return;
            }

            // Shrinking requires compaction. If another object from this
            // region is actively grabbed, defer the shrink until a later
            // reflow instead of changing that object's slot underneath it.
            if (HasGrabbedOccupant())
                return;

            ManipulativeObject[] compacted =
                new ManipulativeObject[newCapacity];

            int targetIndex = 0;

            if (occupants != null)
            {
                foreach (ManipulativeObject occupant in occupants)
                {
                    if (occupant == null)
                        continue;

                    compacted[targetIndex] = occupant;

                    occupant.UpdatePlacementReference(
                        this,
                        targetIndex);

                    targetIndex++;
                }
            }

            occupants = compacted;
            capacity = newCapacity;
        }

        private bool HasGrabbedOccupant()
        {
            if (occupants == null)
                return false;

            foreach (ManipulativeObject occupant in occupants)
            {
                if (occupant != null &&
                    occupant.IsBeingGrabbed)
                {
                    return true;
                }
            }

            return false;
        }

        private void ApplyLayout(
            Vector3 worldPosition,
            Quaternion worldRotation,
            Vector2 size,
            string title,
            WorkspaceRegionStyle style,
            bool refreshOccupants)
        {
            regionSize = size;

            transform.SetPositionAndRotation(
                worldPosition,
                worldRotation);

            ConfigureDropVolume();

            if (view != null)
            {
                view.Configure(
                    size,
                    title,
                    style);
            }
            else
            {
                Debug.LogError(
                    "[MathConstructVR] WorkspaceRegion has no WorkspaceRegionView.",
                    this);
            }

            if (refreshOccupants)
            {
                RefreshOccupantPlacements();
            }
        }

        private void ConfigureDropVolume()
        {
            if (dropVolume == null)
            {
                dropVolume = GetComponent<BoxCollider>();
            }

            dropVolume.isTrigger = true;

            dropVolume.center =
                new Vector3(
                    0f,
                    0.08f,
                    0f);

            dropVolume.size =
                new Vector3(
                    regionSize.x,
                    0.16f,
                    regionSize.y);
        }

        public bool ContainsWorldPoint(
            Vector3 worldPoint)
        {
            Vector3 localPoint =
                transform.InverseTransformPoint(worldPoint);

            float halfWidth = regionSize.x * 0.5f;
            float halfDepth = regionSize.y * 0.5f;

            return
                Mathf.Abs(localPoint.x) <= halfWidth &&
                Mathf.Abs(localPoint.z) <= halfDepth &&
                localPoint.y >= -0.03f &&
                localPoint.y <= 0.22f;
        }

        public bool TryFindNearestAvailableSlot(
            Vector3 worldPoint,
            ManipulativeObject requester,
            out int slotIndex)
        {
            slotIndex = -1;
            float closestDistance = float.PositiveInfinity;

            int usableSlotCount =
                Mathf.Min(
                    capacity,
                    PhysicalSlotCapacity);

            for (int index = 0;
                 index < usableSlotCount;
                 index++)
            {
                ManipulativeObject occupant =
                    occupants[index];

                if (occupant != null &&
                    occupant != requester)
                {
                    continue;
                }

                Vector3 slotPosition =
                    GetSlotWorldPosition(
                        index);

                float distance =
                    (slotPosition - worldPoint)
                    .sqrMagnitude;

                if (distance >= closestDistance)
                    continue;

                closestDistance = distance;
                slotIndex = index;
            }

            return slotIndex >= 0;
        }


        public bool TryFindFirstAvailableSlot(
            ManipulativeObject requester,
            out int slotIndex)
        {
            slotIndex = -1;

            int usableSlotCount =
                Mathf.Min(
                    capacity,
                    PhysicalSlotCapacity);

            for (int index = 0;
                 index < usableSlotCount;
                 index++)
            {
                ManipulativeObject occupant =
                    occupants[index];

                if (occupant == null ||
                    occupant == requester)
                {
                    slotIndex = index;
                    return true;
                }
            }

            return false;
        }


        public void Assign(
            ManipulativeObject manipulative,
            int slotIndex)
        {
            if (manipulative == null)
            {
                throw new ArgumentNullException(
                    nameof(manipulative));
            }

            if (slotIndex < 0 ||
                slotIndex >= capacity)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(slotIndex));
            }

            if (slotIndex >= PhysicalSlotCapacity)
            {
                throw new InvalidOperationException(
                    $"Region '{name}' does not physically fit slot {slotIndex} " +
                    $"at preferred spacing {slotSpacing:F3}m. " +
                    $"Current geometric capacity is {PhysicalSlotCapacity}.");
            }

            ManipulativeObject occupant =
                occupants[slotIndex];

            if (occupant != null &&
                occupant != manipulative)
            {
                throw new InvalidOperationException(
                    $"Slot {slotIndex} in region '{name}' is already occupied.");
            }

            occupants[slotIndex] = manipulative;
        }

        public void Release(
            ManipulativeObject manipulative)
        {
            if (manipulative == null ||
                occupants == null)
            {
                return;
            }

            for (int index = 0; index < occupants.Length; index++)
            {
                if (occupants[index] != manipulative)
                    continue;

                occupants[index] = null;
                return;
            }
        }

        public bool TryDestroyAllOccupants(
            out int destroyedCount)
        {
            destroyedCount = 0;

            if (occupants == null)
                return true;

            // Do not delete a group while the learner is actively holding
            // one of its objects.
            if (HasGrabbedOccupant())
                return false;

            for (int index = 0;
                 index < occupants.Length;
                 index++)
            {
                ManipulativeObject occupant =
                    occupants[index];

                if (occupant == null)
                    continue;

                occupants[index] = null;
                destroyedCount++;

                Destroy(
                    occupant.gameObject);
            }

            return true;
        }


        public void RefreshSlotLayout()
        {
            CompactSlotsIfSafe();
            RefreshOccupantPlacements();
        }


        private void CompactSlotsIfSafe()
        {
            if (occupants == null ||
                HasGrabbedOccupant())
            {
                return;
            }

            int writeIndex = 0;

            for (int readIndex = 0;
                 readIndex < occupants.Length;
                 readIndex++)
            {
                ManipulativeObject occupant =
                    occupants[readIndex];

                if (occupant == null)
                    continue;

                if (readIndex != writeIndex)
                {
                    occupants[writeIndex] = occupant;
                    occupants[readIndex] = null;

                    occupant.UpdatePlacementReference(
                        this,
                        writeIndex);
                }

                writeIndex++;
            }
        }


        private int HighestOccupiedSlotPlusOne()
        {
            if (occupants == null)
                return 0;

            for (int index = occupants.Length - 1;
                 index >= 0;
                 index--)
            {
                if (occupants[index] != null)
                    return index + 1;
            }

            return 0;
        }


        private int CalculatePhysicalSlotCapacity()
        {
            float usableWidth =
                Mathf.Max(
                    0.01f,
                    regionSize.x - (padding * 2f));

            float usableDepth =
                Mathf.Max(
                    0.01f,
                    regionSize.y - (padding * 2f));

            int columns =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableWidth / slotSpacing) + 1);

            int rows =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableDepth / slotSpacing) + 1);

            return
                Mathf.Max(
                    1,
                    columns * rows);
        }


        public Vector3 GetSlotWorldPosition(
            int index)
        {
            if (index < 0 ||
                index >= capacity)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(index));
            }

            if (index >= PhysicalSlotCapacity)
            {
                throw new InvalidOperationException(
                    $"Region '{name}' cannot place slot {index} without overlap. " +
                    $"Physical capacity is {PhysicalSlotCapacity} at preferred spacing.");
            }

            float usableWidth =
                Mathf.Max(
                    0.01f,
                    regionSize.x - (padding * 2f));

            float usableDepth =
                Mathf.Max(
                    0.01f,
                    regionSize.y - (padding * 2f));

            int maximumColumns =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableWidth / slotSpacing) + 1);

            int maximumRows =
                Mathf.Max(
                    1,
                    Mathf.FloorToInt(
                        usableDepth / slotSpacing) + 1);

            int layoutCount =
                Mathf.Max(
                    1,
                    Mathf.Max(
                        HighestOccupiedSlotPlusOne(),
                        index + 1));

            layoutCount =
                Mathf.Min(
                    layoutCount,
                    PhysicalSlotCapacity);

            float aspect =
                usableWidth /
                Mathf.Max(
                    0.01f,
                    usableDepth);

            int columns =
                Mathf.Clamp(
                    Mathf.CeilToInt(
                        Mathf.Sqrt(
                            layoutCount * aspect)),
                    1,
                    Mathf.Min(
                        maximumColumns,
                        layoutCount));

            int rows =
                Mathf.CeilToInt(
                    layoutCount /
                    (float)columns);

            while (rows > maximumRows &&
                   columns < maximumColumns)
            {
                columns++;

                rows =
                    Mathf.CeilToInt(
                        layoutCount /
                        (float)columns);
            }

            int row =
                index / columns;

            int column =
                index % columns;

            int firstIndexInRow =
                row * columns;

            int itemsInThisRow =
                Mathf.Min(
                    columns,
                    layoutCount - firstIndexInRow);

            float rowWidth =
                (itemsInThisRow - 1) *
                slotSpacing;

            float x =
                (-rowWidth * 0.5f) +
                (column * slotSpacing);

            float totalDepth =
                (rows - 1) *
                slotSpacing;

            float z =
                (totalDepth * 0.5f) -
                (row * slotSpacing);

            Vector3 localPosition =
                new Vector3(
                    x,
                    0.002f,
                    z);

            return
                transform.TransformPoint(
                    localPosition);
        }


        public Quaternion GetSlotWorldRotation()
        {
            return transform.rotation;
        }

        private void RefreshOccupantPlacements()
        {
            if (occupants == null)
                return;

            foreach (ManipulativeObject manipulative in occupants)
            {
                if (manipulative != null &&
                    !manipulative.IsBeingGrabbed)
                {
                    manipulative.ReturnToCurrentPlacement();
                }
            }
        }
    }
}