import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone server output — copies only the production node_modules
  // subset actually used, needed for a lean production Docker image
  // (see frontend/Dockerfile). No effect on `next dev`/`next start` as run
  // outside Docker.
  output: "standalone",
};

export default nextConfig;
