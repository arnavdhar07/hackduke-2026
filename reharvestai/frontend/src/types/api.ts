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
