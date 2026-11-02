using System.Text;
using MathConstructVR.Domain;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class WorkspaceRegionDebug : MonoBehaviour
    {
        [SerializeField]
        private WorkspaceController workspaceController;

        private int lastRegionCount = -1;

        private void OnEnable()
        {
            if (workspaceController != null)
            {
                workspaceController.InteractionChanged +=
                    HandleInteractionChanged;
            }

            lastRegionCount = -1;
        }

        private void OnDisable()
        {
            if (workspaceController != null)
            {
                workspaceController.InteractionChanged -=
                    HandleInteractionChanged;
            }
        }

        private void Update()
        {
            if (workspaceController == null)
                return;

            int currentCount =
                workspaceController.ActiveRegions.Count;

            if (currentCount == lastRegionCount)
                return;

            PrintActiveRegions();
        }

        private void HandleInteractionChanged(
            InteractionType interactionType)
        {
            PrintActiveRegions();
        }

        [ContextMenu("Print Active Workspace Regions")]
        public void PrintActiveRegions()
        {
            if (workspaceController == null)
            {
                Debug.LogWarning(
                    "[POV] WorkspaceController is not assigned.",
                    this);

                return;
            }

            StringBuilder message = new();

            message.AppendLine(
                $"[POV] Active workspace regions: " +
                $"{workspaceController.ActiveRegions.Count}");

            foreach (WorkspaceRegion region
                     in workspaceController.ActiveRegions)
            {
                if (region == null)
                    continue;

                message.AppendLine(
                    $"  • {region.name}" +
                    $" | occupants={region.OccupantCount}" +
                    $" | capacity={region.Capacity}" +
                    $" | position={region.transform.position}");
            }

            Debug.Log(
                message.ToString(),
                this);

            lastRegionCount =
                workspaceController.ActiveRegions.Count;
        }
    }
}