export const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
export const MAPBOX_STYLE = "mapbox://styles/mapbox/satellite-streets-v12";

export const DEFAULT_CENTER: [number, number] = [-79.2041, 35.7197];
export const DEFAULT_ZOOM = 15;

export function getMapboxToken(): string {
  if (!MAPBOX_TOKEN) {
    console.warn("NEXT_PUBLIC_MAPBOX_TOKEN is not set");
  }
  return MAPBOX_TOKEN;
}
