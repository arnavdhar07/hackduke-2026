/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config) => {
    // Required for mapbox-gl to work in Next.js
    config.resolve.alias = {
      ...config.resolve.alias,
      "mapbox-gl": "mapbox-gl",
    };
    return config;
  },
};

export default nextConfig;
