import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone server output — needed for the lean production Docker image
  // (see frontend/Dockerfile), but it actively breaks a Vercel build: its
  // own post-build step expects the traditional serverless trace files
  // (.next/**/*.nft.json), which standalone mode restructures, producing
  // "ENOENT .next/next-server.js.nft.json". VERCEL=1 is set automatically
  // in Vercel's build environment, so skip it there — Vercel doesn't need
  // it anyway, it does its own serverless bundling.
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
