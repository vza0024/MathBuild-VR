using System;
using System.Text;
using System.Threading.Tasks;
using MathConstructVR.Networking.DTOs;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.Networking;

namespace MathConstructVR.Networking
{
    public sealed class BackendClient : MonoBehaviour
    {
        [SerializeField]
        private BackendConfig config;


        public async Task<HealthResponseDto> GetHealthAsync()
        {
            ValidateConfig();

            string url =
                BuildUrl("/api/health");

            using UnityWebRequest request =
                UnityWebRequest.Get(url);

            request.timeout =
                config.RequestTimeoutSeconds;

            await SendAsync(
                request,
                "Backend health request");

            HealthResponseDto response =
                Deserialize<HealthResponseDto>(
                    request.downloadHandler.text,
                    "backend health response");

            return response;
        }


        public async Task<QuestionDto[]> GetQuestionsAsync()
        {
            ValidateConfig();

            string url =
                BuildUrl("/api/questions");

            using UnityWebRequest request =
                UnityWebRequest.Get(url);

            request.timeout =
                config.RequestTimeoutSeconds;

            await SendAsync(
                request,
                "Questions request");

            QuestionDto[] questions =
                Deserialize<QuestionDto[]>(
                    request.downloadHandler.text,
                    "questions response");

            if (questions.Length == 0)
            {
                throw new InvalidOperationException(
                    "Backend returned no questions.");
            }

            return questions;
        }


        public async Task<TutorResponseDto> PostTutorAsync(
            TutorRequestDto tutorRequest)
        {
            if (tutorRequest == null)
            {
                throw new ArgumentNullException(
                    nameof(tutorRequest));
            }

            ValidateConfig();

            string url =
                BuildUrl("/api/tutor");


            // --------------------------------------------------------
            // REQUEST-TIME POV METADATA
            //
            // snapshot_age_ms must describe how old the selected
            // viewpoint snapshot is at the moment this tutor request
            // is actually prepared for transmission.
            // --------------------------------------------------------

            if (tutorRequest.View != null)
            {
                long requestTimeMs =
                    DateTimeOffset.UtcNow
                        .ToUnixTimeMilliseconds();

                long snapshotTimestamp =
                    tutorRequest.View.TimestampMs ??
                    requestTimeMs;

                tutorRequest.View.SnapshotAgeMs =
                    Math.Max(
                        0L,
                        requestTimeMs -
                        snapshotTimestamp);
            }


            // --------------------------------------------------------
            // SERIALIZE EXACT REQUEST BODY
            // --------------------------------------------------------

            string json =
                JsonConvert.SerializeObject(
                    tutorRequest);


            // --------------------------------------------------------
            // INTEGRATION DEBUG CAPTURE
            //
            // This is the exact JSON body that will be sent to
            // POST /api/tutor. It can be copied directly from the
            // Unity Console for backend integration verification.
            // --------------------------------------------------------

            Debug.Log(
                $"[TUTOR REQUEST JSON]\n{json}",
                this);


            byte[] body =
                Encoding.UTF8.GetBytes(json);

            using UnityWebRequest request =
                new UnityWebRequest(
                    url,
                    UnityWebRequest.kHttpVerbPOST);

            request.uploadHandler =
                new UploadHandlerRaw(body);

            request.downloadHandler =
                new DownloadHandlerBuffer();

            request.SetRequestHeader(
                "Content-Type",
                "application/json");

            request.timeout =
                config.RequestTimeoutSeconds;

            await SendAsync(
                request,
                "Tutor request");

            TutorResponseDto response =
                Deserialize<TutorResponseDto>(
                    request.downloadHandler.text,
                    "tutor response");

            return response;
        }


        private async Task SendAsync(
            UnityWebRequest request,
            string requestName)
        {
            UnityWebRequestAsyncOperation operation =
                request.SendWebRequest();

            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result ==
                UnityWebRequest.Result.Success)
            {
                return;
            }

            throw new InvalidOperationException(
                $"{requestName} failed.\n" +
                $"URL: {request.url}\n" +
                $"HTTP: {request.responseCode}\n" +
                $"Error: {request.error}\n" +
                $"Response: {request.downloadHandler?.text}");
        }


        private static T Deserialize<T>(
            string json,
            string description)
        {
            T response;

            try
            {
                response =
                    JsonConvert.DeserializeObject<T>(
                        json);
            }
            catch (JsonException exception)
            {
                throw new InvalidOperationException(
                    $"Could not deserialize {description}.\n" +
                    $"Response: {json}",
                    exception);
            }

            if (response == null)
            {
                throw new InvalidOperationException(
                    $"Backend returned an empty {description}.");
            }

            return response;
        }


        private void ValidateConfig()
        {
            if (config == null)
            {
                throw new InvalidOperationException(
                    "BackendClient has no BackendConfig assigned.");
            }

            if (string.IsNullOrWhiteSpace(
                    config.BaseUrl))
            {
                throw new InvalidOperationException(
                    "BackendConfig BaseUrl is empty.");
            }
        }


        private string BuildUrl(
            string endpoint)
        {
            return
                $"{config.BaseUrl}/" +
                $"{endpoint.TrimStart('/')}";
        }
    }
}