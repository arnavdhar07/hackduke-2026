import type { Polygon } from "geojson";

export interface Field {
  id: string;
  name: string;
  polygon: Polygon;
  crop_type: string;
  planting_date: string;
}

export interface ZoneScores {
  ndvi: number;
  ndwi: number;
  ndre: number;
  captured_at: string;
}

export interface Zone {
  id: string;
  field_id: string;
  label: string;
  polygon: Polygon;
  latest_scores: ZoneScores;
  timeseries: ZoneScores[];
}

export type ActionType = "harvest" | "irrigate" | "monitor" | "inspect";
export type Urgency = "low" | "medium" | "high" | "critical";
export type RecommendationStatus = "pending" | "accepted" | "deferred" | "dismissed";

export interface Recommendation {
  id: string;
  field_id: string;
  zone_id: string;
  zone_label: string;
  action_type: ActionType;
  urgency: Urgency;
  reason: string;
  confidence: number;
  status: RecommendationStatus;
  created_at: string;
  // New fields from backend
  estimated_yield_bushels: number;   // 0 if unknown
  days_remaining: number;            // -1 if N/A, 0 if past peak
  crop_health_rating: number;        // 1-10, 0 if unknown
  crop_health_summary: string;       // AI natural language health summary
}

export interface AgentNode {
  name: string;
  inputs: object;
  outputs: object;
}

export interface AgentTrace {
  field_id: string;
  run_at: string;
  nodes: AgentNode[];
}

// ─── Weather forecast — GET /fields/{field_id}/weather ───────────────────────
// Person 2 implements this endpoint via OpenWeather API.
// Shape mirrors OpenWeather daily forecast, simplified to what the UI needs.

export type WeatherCondition = "clear" | "cloudy" | "rain" | "storm";

export interface WeatherDay {
  date: string;          // YYYY-MM-DD
  temp_high_c: number;
  temp_low_c: number;
  precip_mm: number;
  condition: WeatherCondition;
  wind_kph: number;
}

export interface WeatherForecast {
  field_id: string;
  days: WeatherDay[];    // 3 days
}
