using System.Collections.Generic;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using Newtonsoft.Json;

namespace MathConstructVR.Core
{
    internal abstract class WorkspaceInteraction
    {
        protected WorkspaceInteraction(
            WorkspaceController host,
            QuestionDto question)
        {
            Host = host;
            Question = question;
        }

        protected WorkspaceController Host { get; }
        protected QuestionDto Question { get; }

        public abstract InteractionType InteractionType { get; }

        public virtual bool CanAddGroup => false;
        public virtual bool CanCopyGroup => false;
        public virtual bool CanRemoveEmptyGroup => false;

        public abstract void Build();

        public virtual bool CanPlace(
            ManipulativeObject manipulative,
            WorkspaceRegion targetRegion)
        {
            return targetRegion != null;
        }

        public virtual void OnPlacementChanged(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion)
        {
        }

        public abstract bool TryGetLearnerState(
            out object learnerState);

        public abstract bool HasMeaningfulAttempt();

        public abstract string GetStateSignature();

        public abstract string BuildMoveAction(
            ManipulativeObject manipulative,
            WorkspaceRegion previousRegion,
            WorkspaceRegion newRegion);

        public virtual string AdaptTutorText(
            string text)
        {
            return text;
        }

        public virtual string BuildTutorContext()
        {
            return "";
        }

        public virtual bool TryAddGroup(
            out string action)
        {
            action = "";
            return false;
        }

        public virtual bool TryCopyGroup(
            out string action)
        {
            action = "";
            return false;
        }

        public virtual bool TryRemoveEmptyGroup(
            out string action)
        {
            action = "";
            return false;
        }

        protected static int CountInRegion(
            IEnumerable<ManipulativeObject> objects,
            WorkspaceRegion region)
        {
            int count = 0;

            foreach (ManipulativeObject manipulative in objects)
            {
                if (manipulative != null &&
                    manipulative.CurrentRegion == region)
                {
                    count++;
                }
            }

            return count;
        }

        protected static string SerializeSignature(
            object value)
        {
            return JsonConvert.SerializeObject(
                value,
                Formatting.None);
        }

        protected string ObjectLabel()
        {
            string label = Question.Visual?.ObjectLabel;

            return string.IsNullOrWhiteSpace(label)
                ? "object"
                : label;
        }

        protected string ObjectPlural()
        {
            string label = Question.Visual?.ObjectPlural;

            return string.IsNullOrWhiteSpace(label)
                ? "objects"
                : label;
        }
    }
}