export const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
export const MAPBOX_STYLE = "mapbox://styles/mapbox/satellite-streets-v12";

export const DEFAULT_CENTER: [number, number] = [-98.5795, 39.8283];
export const DEFAULT_ZOOM = 4;

export function getMapboxToken(): string {
  if (!MAPBOX_TOKEN) {
    console.warn("NEXT_PUBLIC_MAPBOX_TOKEN is not set");
  }
  return MAPBOX_TOKEN;
}
