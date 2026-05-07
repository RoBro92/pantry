import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Pantro",
    short_name: "Pantro",
    description: "Self-hosted household pantry and shopping flows.",
    start_url: "/app",
    scope: "/",
    display: "standalone",
    background_color: "#f4efe8",
    theme_color: "#ad5b1f",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable"
      },
      {
        src: "/apple-icon.svg",
        sizes: "180x180",
        type: "image/svg+xml",
        purpose: "any"
      }
    ]
  };
}
