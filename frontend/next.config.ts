import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" is for Docker/Node self-hosting; Vercel handles its own output.
  // Set NEXT_OUTPUT=standalone in Containerfile; leave unset for Vercel.
  output: (process.env.NEXT_OUTPUT as "standalone" | undefined) || undefined,
};

export default nextConfig;
