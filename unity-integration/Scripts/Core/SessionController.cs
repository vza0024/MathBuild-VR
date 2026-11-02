using System;
using System.Collections.Generic;
using System.Linq;
using MathConstructVR.Domain;
using MathConstructVR.Networking.DTOs;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class SessionController : MonoBehaviour
    {
        private readonly List<QuestionDto> allQuestions = new();
        private readonly List<QuestionDto> filteredQuestions = new();

        public event Action<QuestionDto> CurrentQuestionChanged;

        public IReadOnlyList<QuestionDto> AllQuestions => allQuestions;
        public IReadOnlyList<QuestionDto> FilteredQuestions => filteredQuestions;

        public QuestionFilter SelectedFilter { get; private set; } = QuestionFilter.ALL;

        public QuestionDto CurrentQuestion { get; private set; }

        public int CurrentQuestionIndex { get; private set; } = -1;

        public int CurrentQuestionNumber => CurrentQuestionIndex + 1;

        public int CurrentPoolCount => filteredQuestions.Count;

        public string SessionId { get; private set; }

        public bool IsInitialized { get; private set; }


        public void Initialize(IEnumerable<QuestionDto> questions)
        {
            if (questions == null)
                throw new ArgumentNullException(nameof(questions));

            QuestionDto[] loadedQuestions = questions
                .Where(question => question != null)
                .ToArray();

            if (loadedQuestions.Length == 0)
                throw new InvalidOperationException(
                    "SessionController cannot initialize without questions.");

            allQuestions.Clear();
            allQuestions.AddRange(loadedQuestions);

            SessionId = Guid.NewGuid().ToString("N");
            IsInitialized = true;

            SetFilter(QuestionFilter.ALL);
        }


        public void SetFilter(QuestionFilter filter)
        {
            EnsureInitialized();

            SelectedFilter = filter;

            filteredQuestions.Clear();

            if (filter == QuestionFilter.ALL)
            {
                filteredQuestions.AddRange(allQuestions);
            }
            else
            {
                string interactionName = filter.ToString();

                filteredQuestions.AddRange(
                    allQuestions.Where(question =>
                        string.Equals(
                            question.Interaction,
                            interactionName,
                            StringComparison.OrdinalIgnoreCase)));
            }

            if (filteredQuestions.Count == 0)
            {
                throw new InvalidOperationException(
                    $"No questions exist for filter '{filter}'.");
            }

            SetQuestion(0);
        }


        public void SetQuestion(int index)
        {
            EnsureInitialized();

            if (index < 0 || index >= filteredQuestions.Count)
            {
                throw new ArgumentOutOfRangeException(
                    nameof(index),
                    index,
                    $"Question index must be between 0 and {filteredQuestions.Count - 1}.");
            }

            CurrentQuestionIndex = index;
            CurrentQuestion = filteredQuestions[index];

            CurrentQuestionChanged?.Invoke(CurrentQuestion);
        }


        public void NextQuestion()
        {
            EnsureInitialized();

            int nextIndex = CurrentQuestionIndex + 1;

            if (nextIndex >= filteredQuestions.Count)
                nextIndex = 0;

            SetQuestion(nextIndex);
        }


        public void PreviousQuestion()
        {
            EnsureInitialized();

            int previousIndex = CurrentQuestionIndex - 1;

            if (previousIndex < 0)
                previousIndex = filteredQuestions.Count - 1;

            SetQuestion(previousIndex);
        }


        private void EnsureInitialized()
        {
            if (!IsInitialized)
            {
                throw new InvalidOperationException(
                    "SessionController has not been initialized.");
            }
        }
    }
}