import type { Field, Zone, Recommendation, AgentTrace } from "@/types/api";
import type { Polygon } from "geojson";

const MOCK_MODE = true;
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Mock state (persists across calls within a session) ──────────────────────

let mockField: Field | null = null;
let mockZones: Zone[] | null = null;
let mockRecommendations: Recommendation[] | null = null;

// ─── Zone generation from a drawn polygon ─────────────────────────────────────

// Fixed NDVI profiles — one per colour band — applied to the 4 grid cells
const ZONE_PROFILES = [
  {
    label: "Zone A",
    ndvi: 88, ndwi: 72, ndre: 81,
    timeseries: [30, 52, 71, 85, 88].map((v, i) => ({
      ndvi: v, ndwi: Math.round(v * 0.82), ndre: Math.round(v * 0.92),
      captured_at: `2026-0${i + 5}-01T10:00:00Z`,
    })),
    action_type: "inspect" as const, urgency: "low" as const, confidence: 0.55,
    reason: "This zone is performing well with healthy canopy coverage. A routine physical inspection in the next two weeks will confirm satellite data and verify there is no pest pressure.",
  },
  {
    label: "Zone B",
    ndvi: 71, ndwi: 58, ndre: 65,
    timeseries: [28, 45, 60, 68, 71].map((v, i) => ({
      ndvi: v, ndwi: Math.round(v * 0.82), ndre: Math.round(v * 0.92),
      captured_at: `2026-0${i + 5}-01T10:00:00Z`,
    })),
    action_type: "monitor" as const, urgency: "medium" as const, confidence: 0.67,
    reason: "This zone is healthy but NDRE has plateaued over the last three captures, suggesting nitrogen uptake may be leveling off. Monitor for another week before deciding on a foliar application.",
  },
  {
    label: "Zone C",
    ndvi: 48, ndwi: 35, ndre: 42,
    timeseries: [25, 38, 44, 47, 48].map((v, i) => ({
      ndvi: v, ndwi: Math.round(v * 0.73), ndre: Math.round(v * 0.88),
      captured_at: `2026-0${i + 5}-01T10:00:00Z`,
    })),
    action_type: "irrigate" as const, urgency: "high" as const, confidence: 0.81,
    reason: "NDWI has fallen to 35, suggesting moderate water stress in this section. Irrigating within 48 hours should stabilize canopy health before temperatures spike this weekend.",
  },
  {
    label: "Zone D",
    ndvi: 22, ndwi: 14, ndre: 18,
    timeseries: [55, 48, 35, 28, 22].map((v, i) => ({
      ndvi: v, ndwi: Math.round(v * 0.64), ndre: Math.round(v * 0.82),
      captured_at: `2026-0${i + 5}-01T10:00:00Z`,
    })),
    action_type: "harvest" as const, urgency: "critical" as const, confidence: 0.94,
    reason: "This zone has dropped to NDVI 22, indicating severe crop stress and near-complete canopy loss. A major rain event is forecast in 36 hours — harvest immediately to avoid total yield loss.",
  },
];

function bbox(polygon: Polygon): { minLng: number; maxLng: number; minLat: number; maxLat: number } {
  const coords = polygon.coordinates[0];
  const lngs = coords.map((c) => c[0]);
  const lats = coords.map((c) => c[1]);
  return {
    minLng: Math.min(...lngs),
    maxLng: Math.max(...lngs),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}

function generateZones(field: Field): Zone[] {
  const { minLng, maxLng, minLat, maxLat } = bbox(field.polygon);
  const midLng = (minLng + maxLng) / 2;
  const midLat = (minLat + maxLat) / 2;

  // 2×2 grid: NW, NE, SW, SE
  const grid: [number, number, number, number][] = [
    [minLng, midLat,  midLng, maxLat],  // NW → Zone A (healthy)
    [midLng, midLat,  maxLng, maxLat],  // NE → Zone B (watch)
    [minLng, minLat,  midLng, midLat],  // SW → Zone C (stressed)
    [midLng, minLat,  maxLng, midLat],  // SE → Zone D (critical)
  ];

  return grid.map(([w, s, e, n], i) => {
    const profile = ZONE_PROFILES[i];
    const zoneId = `zone-${String(i + 1).padStart(3, "0")}`;
    return {
      id: zoneId,
      field_id: field.id,
      label: profile.label,
      polygon: {
        type: "Polygon",
        coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
      } as Polygon,
      latest_scores: {
        ndvi: profile.ndvi,
        ndwi: profile.ndwi,
        ndre: profile.ndre,
        captured_at: "2026-03-20T10:00:00Z",
      },
      timeseries: profile.timeseries,
    };
  });
}

function generateRecommendations(field: Field, zones: Zone[]): Recommendation[] {
  return ZONE_PROFILES.map((profile, i) => {
    const zone = zones[i];
    return {
      id: `rec-${String(i + 1).padStart(3, "0")}`,
      field_id: field.id,
      zone_id: zone.id,
      zone_label: profile.label,
      action_type: profile.action_type,
      urgency: profile.urgency,
      reason: profile.reason,
      confidence: profile.confidence,
      status: "pending" as const,
      created_at: `2026-03-20T08:${String(i * 5).padStart(2, "0")}:00Z`,
    };
  });
}

function generateAgentTrace(field: Field, zones: Zone[]): AgentTrace {
  const classifications = Object.fromEntries(
    zones.map((z, i) => [z.id, ["healthy", "watch", "stressed", "critical"][i]])
  );
  return {
    field_id: field.id,
    run_at: "2026-03-20T08:00:00Z",
    nodes: [
      {
        name: "context_builder",
        inputs: { field_id: field.id, requested_at: "2026-03-20T08:00:00Z" },
        outputs: {
          field: { name: field.name, crop_type: field.crop_type, planting_date: field.planting_date },
          weather: { forecast_72h: "heavy rain", temp_high_c: 28 },
          zones_loaded: zones.length,
        },
      },
      {
        name: "zone_classifier",
        inputs: { zones: zones.map((z) => z.id) },
        outputs: { classifications },
      },
      {
        name: "risk_evaluator",
        inputs: { classifications: { [zones[3].id]: "critical", [zones[2].id]: "stressed" }, weather: { forecast_72h: "heavy rain" } },
        outputs: {
          risks: [
            { zone_id: zones[3].id, risk: "total yield loss", probability: 0.91 },
            { zone_id: zones[2].id, risk: "water stress escalation", probability: 0.74 },
          ],
        },
      },
      {
        name: "action_generator",
        inputs: { risks: [{ zone_id: zones[3].id }, { zone_id: zones[2].id }] },
        outputs: {
          actions: zones.map((z, i) => ({
            zone_id: z.id,
            action: ZONE_PROFILES[i].action_type,
            urgency: ZONE_PROFILES[i].urgency,
          })).reverse(),
        },
      },
      {
        name: "output_formatter",
        inputs: { actions: 4, locale: "en-US" },
        outputs: {
          recommendations_written: 4,
          critical_count: 1,
          summary: `Immediate harvest required in ${zones[3].label}. Three additional lower-priority actions generated for ${field.name}.`,
        },
      },
    ],
  };
}

// ─── Seed default mock data (used when navigating directly to /dashboard/field-001) ──

function seedDefault() {
  if (mockField) return;
  const field: Field = {
    id: "field-001",
    name: "Thornfield Farm",
    crop_type: "corn",
    planting_date: "2026-04-15",
    polygon: {
      type: "Polygon",
      coordinates: [[[-78.9, 36.0], [-78.88, 36.0], [-78.88, 36.015], [-78.9, 36.015], [-78.9, 36.0]]],
    },
  };
  mockField = field;
  mockZones = generateZones(field);
  mockRecommendations = generateRecommendations(field, mockZones);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

// ─── API functions ─────────────────────────────────────────────────────────────

export async function createField(body: Omit<Field, "id">): Promise<Field> {
  if (MOCK_MODE) {
    const field: Field = { ...body, id: `field-${Date.now()}` };
    const zones = generateZones(field);
    mockField = field;
    mockZones = zones;
    mockRecommendations = generateRecommendations(field, zones);
    return field;
  }
  return apiFetch<Field>("/fields", { method: "POST", body: JSON.stringify(body) });
}

export async function getField(fieldId: string): Promise<Field> {
  if (MOCK_MODE) { seedDefault(); return mockField!; }
  return apiFetch<Field>(`/fields/${fieldId}`);
}

export async function getZones(fieldId: string): Promise<Zone[]> {
  if (MOCK_MODE) { seedDefault(); return mockZones!; }
  return apiFetch<Zone[]>(`/fields/${fieldId}/zones`);
}

export async function getRecommendations(fieldId: string): Promise<Recommendation[]> {
  if (MOCK_MODE) { seedDefault(); return mockRecommendations!; }
  return apiFetch<Recommendation[]>(`/fields/${fieldId}/recommendations`);
}

export async function patchRecommendation(id: string, status: Recommendation["status"]): Promise<Recommendation> {
  if (MOCK_MODE) {
    seedDefault();
    const rec = mockRecommendations!.find((r) => r.id === id);
    if (!rec) throw new Error(`Mock: recommendation ${id} not found`);
    rec.status = status;
    return { ...rec };
  }
  return apiFetch<Recommendation>(`/recommendations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export async function getAgentTrace(fieldId: string): Promise<AgentTrace> {
  if (MOCK_MODE) {
    seedDefault();
    return generateAgentTrace(mockField!, mockZones!);
  }
  return apiFetch<AgentTrace>(`/fields/${fieldId}/agent/trace`);
}
