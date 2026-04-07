/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@pantry/shared-types"]
};

module.exports = nextConfig;
