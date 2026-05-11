// TypeScript interfaces mirroring the Python simulation's JSON output schema

export interface GlobalState {
  institution_strength: number;
  corruption_index: number;
  welfare_index: number;
  audit_strength: number;
  media_presence: number;
  city_budget: number;
  citizen_trust: number;
  unrest_level: number;
  dynasty_score: number;
}

export interface SimClock {
  tick: number;
  hour: number;
  day: number;
  year: number;
}

export interface AgentTraits {
  integrity: number;
  greed: number;
  ambition: number;
  family_loyalty: number;
  competence: number;
  empathy: number;
}

export interface AgentGoal {
  key: string;
  label: string;
  progress: number;
  public: boolean;
}

export type MemoryType = "observation" | "reflection" | "plan";
export type EmotionalTag = "neutral" | "satisfied" | "frustrated" | "fearful" | "angry";

export interface MemoryObject {
  memory_id: string;
  description: string;
  timestamp: number;
  last_accessed: number;
  importance: number;
  memory_type: MemoryType;
  emotional_tag: EmotionalTag;
}

export interface AgentSnapshot {
  id: number;
  name: string;
  role: string;
  family_id: string | null;
  location: string;
  task: string;
  satisfaction: number;
  wealth: number;
  corrupt_acts: number;
  honest_acts: number;
  traits: AgentTraits;
  goals: AgentGoal[];
  daily_plan: string | null;
  memory_stream: MemoryObject[] | null;
}

export type EventType = "political" | "crime" | "corruption" | "civic" | "economy";

export interface SimEvent {
  tick: number;
  hour: number;
  agent_id: number;
  agent_name: string;
  type: EventType;
  description: string;
}

export type ConversationOutcome = "positive" | "negative" | "neutral";

export interface Conversation {
  tick: number;
  hour: number;
  agent_a_id: number;
  agent_a_name: string;
  agent_b_id: number;
  agent_b_name: string;
  dialogue: string;
  outcome: ConversationOutcome;
  location: string;
}

export interface RelationshipSummary {
  num_nodes: number;
  num_edges: number;
  avg_trust: number;
  density: number;
}

export interface DaySnapshot {
  run_id: string;
  year: number;
  day: number;
  global: GlobalState;
  clock: SimClock;
  agents: AgentSnapshot[];
  events: SimEvent[];
  conversations: Conversation[];
  relationships: RelationshipSummary;
}

export interface RunMetadata {
  run_id: string;
  dynasty_enabled: boolean;
  total_days: number;
  day_files: string[];
}

export interface TimeSeriesPoint {
  tick: number;
  year: number;
  day: number;
  hour: number;
  institution_strength: number;
  corruption_index: number;
  welfare_index: number;
  audit_strength: number;
  media_presence: number;
  city_budget: number;
  citizen_trust: number;
  unrest_level: number;
  dynasty_score: number;
}

export type PlaybackSpeed = 1 | 2 | 5 | 10;
export type PlaybackState = "playing" | "paused";

export interface ReplayState {
  runId: string | null;
  currentYear: number;
  currentDay: number;
  currentHour: number;
  playback: PlaybackState;
  speed: PlaybackSpeed;
  dayData: DaySnapshot | null;
  loading: boolean;
  error: string | null;
}
