/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@pantry/shared-types"]
};

export default nextConfig;
