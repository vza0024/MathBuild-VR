using MathConstructVR.Core;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using UnityEngine;
using UnityEngine.UI;

namespace MathConstructVR.Presentation.UI
{
    public sealed class EqualGroupsControlsController : MonoBehaviour
    {
        [Header("Application")]
        [SerializeField]
        private SessionController session;

        [SerializeField]
        private WorkspaceController workspace;

        [Header("Presentation")]
        [Tooltip("Child containing the actual three-button controls. Keep this controller on an always-active host.")]
        [SerializeField]
        private GameObject controlsRoot;

        [SerializeField]
        private Button addGroupButton;

        [SerializeField]
        private Button copyGroupButton;

        [SerializeField]
        private Button removeEmptyGroupButton;

        private void OnEnable()
        {
            if (!ValidateReferences())
                return;

            session.CurrentQuestionChanged +=
                HandleQuestionChanged;

            workspace.GroupControlsAvailabilityChanged +=
                HandleAvailabilityChanged;

            RefreshVisibility();
        }

        private void OnDisable()
        {
            if (session != null)
            {
                session.CurrentQuestionChanged -=
                    HandleQuestionChanged;
            }

            if (workspace != null)
            {
                workspace.GroupControlsAvailabilityChanged -=
                    HandleAvailabilityChanged;
            }
        }

        public void AddGroup()
        {
            workspace?.AddGroup();
        }

        public void CopyGroup()
        {
            workspace?.CopyGroup();
        }

        public void RemoveEmptyGroup()
        {
            workspace?.RemoveEmptyGroup();
        }

        private void HandleQuestionChanged(
            QuestionDto question)
        {
            RefreshVisibility();
        }

        private void HandleAvailabilityChanged(
            bool canAdd,
            bool canCopy,
            bool canRemove)
        {
            bool visible =
                session.CurrentQuestion?.InteractionType ==
                InteractionType.EqualGroups;

            if (!visible)
            {
                if (controlsRoot != null)
                    controlsRoot.SetActive(false);

                return;
            }

            if (controlsRoot != null)
                controlsRoot.SetActive(true);

            if (addGroupButton != null)
                addGroupButton.interactable = canAdd;

            if (copyGroupButton != null)
                copyGroupButton.interactable = canCopy;

            if (removeEmptyGroupButton != null)
                removeEmptyGroupButton.interactable = canRemove;
        }

        private void RefreshVisibility()
        {
            bool visible =
                session != null &&
                session.CurrentQuestion?.InteractionType ==
                InteractionType.EqualGroups;

            if (controlsRoot != null)
            {
                controlsRoot.SetActive(visible);
            }

            if (!visible)
                return;

            if (addGroupButton != null)
                addGroupButton.interactable = workspace.CanAddGroup;

            if (copyGroupButton != null)
                copyGroupButton.interactable = workspace.CanCopyGroup;

            if (removeEmptyGroupButton != null)
                removeEmptyGroupButton.interactable = workspace.CanRemoveEmptyGroup;
        }

        private bool ValidateReferences()
        {
            bool valid =
                session != null &&
                workspace != null &&
                controlsRoot != null;

            if (!valid)
            {
                Debug.LogError(
                    "[MathConstructVR] EqualGroupsControlsController is missing required references.",
                    this);
            }

            return valid;
        }
    }
}
