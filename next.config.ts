import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=()",
  },
];

  const nextConfig: NextConfig = {
    poweredByHeader: false,
    // The desktop installer ships Product inside the app rather than asking the
    // person to run a Node server themselves. Standalone emits a server and only
    // the node_modules it actually reached, which is the difference between an
    // installer of tens of megabytes and one of a gigabyte.
    output: "standalone",
    async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
