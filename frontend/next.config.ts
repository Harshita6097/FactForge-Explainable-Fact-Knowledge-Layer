import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "standalone",
  compress: true,
  poweredByHeader: false,
  async redirects() {
    return [
      { source: "/facts",         destination: "/explore?view=table",         permanent: false },
      { source: "/facts/:id",     destination: "/explore?view=table",         permanent: false },
      { source: "/relationships", destination: "/explore?view=relationships", permanent: false },
      { source: "/timeline",      destination: "/explore?view=timeline",      permanent: false },
      { source: "/upload",        destination: "/",                           permanent: false },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
