export interface StuckBatch {
  batch_code: string;
  station: string;
  stuck_mins: number;
}

export interface InactiveStation {
  station: string;
  silent_mins: number | null;
  never_active: boolean;
}

export interface StationThroughput {
  station: string;
  completed_last_hour: number;
}

export interface OperationalState {
  type: "operational_state";
  stuck_batches: StuckBatch[];
  inactive_stations: InactiveStation[];
  station_throughput: StationThroughput[];
  computed_at: string;
}
