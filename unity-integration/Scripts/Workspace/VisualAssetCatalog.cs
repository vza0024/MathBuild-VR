using System;
using System.Collections.Generic;
using MathConstructVR.Networking.DTOs;
using UnityEngine;

namespace MathConstructVR.Core
{
    public enum VisualRole
    {
        Object,
        Initial,
        Change,
        PartA,
        PartB
    }


    [CreateAssetMenu(
        fileName = "VisualAssetCatalog",
        menuName = "MathConstructVR/Visual Asset Catalog")]
    public sealed class VisualAssetCatalog : ScriptableObject
    {
        [Serializable]
        private sealed class AssetEntry
        {
            public string label;
            public string code;
            public GameObject prefab;
        }


        [Serializable]
        private sealed class QuestionOverride
        {
            public string questionId;
            public VisualRole role;
            public GameObject prefab;
        }


        [Header("Fallback")]
        [Tooltip(
            "Used whenever no question override, code, or semantic label " +
            "matches a dedicated 3D manipulative prefab.")]
        [SerializeField]
        private GameObject defaultPrefab;


        [Header("Assets")]
        [SerializeField]
        private List<AssetEntry> assets = new();


        [Header("Question Overrides")]
        [SerializeField]
        private List<QuestionOverride> questionOverrides = new();


        [Header("Debug")]
        [SerializeField]
        private bool logFallbackUsage = true;


        private readonly HashSet<string> warnedFallbacks =
            new();


        public GameObject Resolve(
            QuestionDto question,
            VisualRole role)
        {
            if (question == null)
            {
                throw new ArgumentNullException(
                    nameof(question));
            }


            // -------------------------------------------------
            // QUESTION-SPECIFIC OVERRIDE
            // -------------------------------------------------

            foreach (QuestionOverride visualOverride
                     in questionOverrides)
            {
                if (visualOverride.prefab == null)
                    continue;

                if (!string.Equals(
                        visualOverride.questionId,
                        question.Id,
                        StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (visualOverride.role == role)
                {
                    return visualOverride.prefab;
                }
            }


            string label = null;
            string code = null;


            if (question.Visual != null)
            {
                GetRoleIdentity(
                    question.Visual,
                    role,
                    out label,
                    out code);


                // ---------------------------------------------
                // EXACT LABEL + CODE
                // ---------------------------------------------

                foreach (AssetEntry entry in assets)
                {
                    if (entry.prefab == null)
                        continue;

                    if (Same(entry.label, label) &&
                        Same(entry.code, code))
                    {
                        return entry.prefab;
                    }
                }


                // ---------------------------------------------
                // CODE
                // ---------------------------------------------

                if (!string.IsNullOrWhiteSpace(
                        code))
                {
                    foreach (AssetEntry entry in assets)
                    {
                        if (entry.prefab != null &&
                            Same(entry.code, code))
                        {
                            return entry.prefab;
                        }
                    }
                }


                // ---------------------------------------------
                // SEMANTIC LABEL
                // ---------------------------------------------

                if (!string.IsNullOrWhiteSpace(
                        label))
                {
                    foreach (AssetEntry entry in assets)
                    {
                        if (entry.prefab != null &&
                            Same(entry.label, label))
                        {
                            return entry.prefab;
                        }
                    }
                }
            }


            // -------------------------------------------------
            // DEFAULT TOKEN
            // -------------------------------------------------

            return ResolveFallback(
                question,
                role,
                label,
                code);
        }


        private GameObject ResolveFallback(
            QuestionDto question,
            VisualRole role,
            string label,
            string code)
        {
            if (defaultPrefab == null)
            {
                throw new InvalidOperationException(
                    $"No VR manipulative asset exists for question " +
                    $"'{question.Id}', role '{role}', " +
                    $"label '{label}', code '{code}', and the " +
                    $"VisualAssetCatalog has no Default Prefab assigned.");
            }


            string warningKey =
                $"{question.Id}|{role}|{label}|{code}";


            if (logFallbackUsage &&
                warnedFallbacks.Add(
                    warningKey))
            {
                Debug.LogWarning(
                    $"[MathConstructVR] Using DefaultToken for " +
                    $"question '{question.Id}'. " +
                    $"Role={role}, Label='{label}', Code='{code}'.");
            }


            return defaultPrefab;
        }


        private static void GetRoleIdentity(
            QuestionVisualDto visual,
            VisualRole role,
            out string label,
            out string code)
        {
            switch (role)
            {
                case VisualRole.Initial:

                    label =
                        visual.InitialObjectLabel ??
                        visual.ObjectLabel;

                    code =
                        visual.InitialObjectCode ??
                        visual.ObjectCode;

                    return;


                case VisualRole.Change:

                    label =
                        visual.ChangeObjectLabel ??
                        visual.ObjectLabel;

                    code =
                        visual.ChangeObjectCode ??
                        visual.ObjectCode;

                    return;


                case VisualRole.PartA:

                    label =
                        visual.PartALabel;

                    code = null;

                    return;


                case VisualRole.PartB:

                    label =
                        visual.PartBLabel;

                    code = null;

                    return;


                default:

                    label =
                        visual.ObjectLabel;

                    code =
                        visual.ObjectCode;

                    return;
            }
        }


        private static bool Same(
            string left,
            string right)
        {
            if (string.IsNullOrWhiteSpace(left) ||
                string.IsNullOrWhiteSpace(right))
            {
                return false;
            }


            return string.Equals(
                left.Trim(),
                right.Trim(),
                StringComparison.OrdinalIgnoreCase);
        }
    }
}