export const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
export const MAPBOX_STYLE = "mapbox://styles/mapbox/dark-v11";

export const DEFAULT_CENTER: [number, number] = [-78.89, 36.0075];
export const DEFAULT_ZOOM = 13;

export function getMapboxToken(): string {
  if (!MAPBOX_TOKEN) {
    console.warn("NEXT_PUBLIC_MAPBOX_TOKEN is not set");
  }
  return MAPBOX_TOKEN;
}
