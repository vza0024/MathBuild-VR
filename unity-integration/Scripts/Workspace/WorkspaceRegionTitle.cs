using MathConstructVR.Presentation;
using UnityEngine;

namespace MathConstructVR.Core
{
    public sealed class WorkspaceRegionTitle : MonoBehaviour
    {
        private WorldFacingLabel label;


        public void Configure(
            string title,
            Vector2 regionSize)
        {
            if (label == null)
            {
                GameObject labelObject =
                    new GameObject(
                        "RegionTitle");


                labelObject.transform.SetParent(
                    transform,
                    false);


                label =
                    labelObject.AddComponent<
                        WorldFacingLabel>();
            }


            float width =
                Mathf.Clamp(
                    regionSize.x * 0.82f,
                    0.22f,
                    0.55f);


            label.transform.localPosition =
                new Vector3(
                    0f,
                    0.065f,

                    (-regionSize.y * 0.5f) +
                    0.045f);


            label.Configure(
                title,
                new Vector2(
                    width,
                    0.065f),
                34f);
        }


        public void SetTitle(
            string title)
        {
            if (label == null)
                return;

            label.SetText(
                title);
        }
    }
}