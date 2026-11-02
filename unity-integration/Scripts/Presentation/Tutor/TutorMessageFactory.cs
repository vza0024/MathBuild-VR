using System;
using MathConstructVR.Config;
using MathConstructVR.Networking.DTOs;

namespace MathConstructVR.Presentation.Tutor
{
    public enum StoryClueKind
    {
        WhoOrWhat,
        WhatHappens,
        WhatAreWeFinding
    }


    public static class TutorMessageFactory
    {
        public static string InitialTutorMessage(
            QuestionDto question,
            MathConstructTextCatalog textCatalog)
        {
            if (question == null)
                return "";

            if (textCatalog == null)
            {
                throw new ArgumentNullException(
                    nameof(textCatalog));
            }


            string template =
                textCatalog.GetOpeningTemplate(
                    question.InteractionType);


            return FillTemplate(
                template,
                question);
        }


        public static string StoryClue(
            QuestionDto question,
            StoryClueKind clueKind,
            MathConstructTextCatalog textCatalog)
        {
            if (question == null)
                return "";

            if (textCatalog == null)
            {
                throw new ArgumentNullException(
                    nameof(textCatalog));
            }


            string template;


            switch (clueKind)
            {
                case StoryClueKind.WhoOrWhat:

                    template =
                        textCatalog
                            .GetWhoOrWhatTemplate();

                    break;


                case StoryClueKind.WhatHappens:

                    template =
                        textCatalog
                            .GetWhatHappensTemplate(
                                question.InteractionType);

                    break;


                case StoryClueKind.WhatAreWeFinding:

                    template =
                        textCatalog
                            .GetFindingTemplate();

                    break;


                default:

                    return "";
            }


            return FillTemplate(
                template,
                question);
        }


        private static string FillTemplate(
            string template,
            QuestionDto question)
        {
            if (string.IsNullOrWhiteSpace(template))
                return "";


            string story =
                EnsureSentence(
                    question.Body);


            string objects =
                question.Visual?.ObjectPlural;


            if (string.IsNullOrWhiteSpace(objects))
            {
                objects = "objects";
            }


            string questionPhrase =
                BuildQuestionPhrase(
                    question.Question);


            return template
                .Replace(
                    "{story}",
                    story)

                .Replace(
                    "{objects}",
                    objects)

                .Replace(
                    "{question}",
                    questionPhrase)

                .Trim();
        }


        private static string EnsureSentence(
            string text)
        {
            string value =
                text?.Trim();


            if (string.IsNullOrWhiteSpace(value))
                return "";


            char lastCharacter =
                value[
                    value.Length - 1];


            if (lastCharacter != '.' &&
                lastCharacter != '?' &&
                lastCharacter != '!')
            {
                value += ".";
            }


            return value;
        }


        private static string BuildQuestionPhrase(
            string text)
        {
            string value =
                text?.Trim();


            if (string.IsNullOrWhiteSpace(value))
            {
                return
                    "what the story is asking";
            }


            value =
                value.TrimEnd(
                    '?',
                    '.',
                    '!');


            if (value.Length == 0)
                return value;


            if (char.IsUpper(value[0]))
            {
                value =
                    char.ToLowerInvariant(
                        value[0]) +
                    value.Substring(1);
            }


            return value;
        }
    }
}