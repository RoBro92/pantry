/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@pantro/shared-types"]
};

module.exports = nextConfig;
