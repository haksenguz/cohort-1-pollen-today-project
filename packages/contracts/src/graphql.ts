// GENERATED from apps/api/schema/*.graphql — DO NOT EDIT BY HAND.
// Regenerate with: pnpm --filter @pollen/contracts generate
export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string; }
  String: { input: string; output: string; }
  Boolean: { input: boolean; output: boolean; }
  Int: { input: number; output: number; }
  Float: { input: number; output: number; }
  DateTime: { input: Date; output: Date; }
  /** Mongo ObjectId, serialised as a 24-character hex string */
  ObjectId: { input: string; output: string; }
};

/** One alert that was delivered to a public Telegram channel. */
export type Alert = {
  channel: Scalars['String']['output'];
  id: Scalars['ObjectId']['output'];
  messageText: Scalars['String']['output'];
  pollenType: PollenType;
  region: Region;
  riskLevel: RiskLevel;
  sentAt: Scalars['DateTime']['output'];
  /** The day the alert is about, not the day it was sent. */
  targetDate: Scalars['String']['output'];
};

/** Three-day forecast. Beyond three days is out of scope — accuracy collapses. */
export type Forecast = {
  days: Array<ForecastDay>;
  generatedAt: Scalars['DateTime']['output'];
  /** e.g. "baseline-persistence-v1" or "gbm-v3". Never omitted. */
  modelVersion: Scalars['String']['output'];
  pollenType: PollenType;
  region: Region;
};

/** Predicted pollen risk for a single KST calendar day. */
export type ForecastDay = {
  /** 0–1. Null for the persistence baseline, which does not produce one. */
  confidence?: Maybe<Scalars['Float']['output']>;
  /** YYYY-MM-DD, KST. */
  date: Scalars['String']['output'];
  riskLevel: RiskLevel;
};

/** One execution of a scheduled job. */
export type JobRun = {
  error?: Maybe<Scalars['String']['output']>;
  finishedAt?: Maybe<Scalars['DateTime']['output']>;
  jobName: Scalars['String']['output'];
  /** Rows written or messages sent. Null while still running. */
  rowsAffected?: Maybe<Scalars['Int']['output']>;
  startedAt: Scalars['DateTime']['output'];
  status: JobStatus;
};

/** Outcome of a scheduled job run. */
export enum JobStatus {
  FAILED = 'FAILED',
  RUNNING = 'RUNNING',
  SUCCESS = 'SUCCESS'
}

export type PaginatedAlert = {
  hasMore: Scalars['Boolean']['output'];
  items: Array<Alert>;
  total: Scalars['Int']['output'];
};

/** Oak and pine run Apr–Jun; weeds and ragweed run Aug–Oct. */
export enum PollenType {
  OAK = 'OAK',
  PINE = 'PINE',
  WEEDS = 'WEEDS'
}

/** Root query type. Each component extends it in its own .graphql file. */
export type Query = {
  alertHistory: PaginatedAlert;
  forecast: Forecast;
  seasonTiming: SeasonTiming;
  systemStatus: SystemStatus;
};


/** Root query type. Each component extends it in its own .graphql file. */
export type QueryAlertHistoryArgs = {
  limit?: Scalars['Int']['input'];
  offset?: Scalars['Int']['input'];
  region?: InputMaybe<Region>;
};


/** Root query type. Each component extends it in its own .graphql file. */
export type QueryForecastArgs = {
  pollenType?: PollenType;
  region: Region;
};


/** Root query type. Each component extends it in its own .graphql file. */
export type QuerySeasonTimingArgs = {
  pollenType?: PollenType;
  region: Region;
};

/**
 * The 16 top-level Korean administrative regions (시/도), taken from the KMA DFS
 * zone tree. Each maps to an `areaNo` the KMA API accepts — see REGION_AREA_NO in
 * @pollen/contracts.
 *
 * Every slice keys off this: forecasts, charts, and Telegram channels.
 * GWANGJU_JEONNAM is the merged 전남광주통합특별시 (1200000000); there is no
 * separate 전라남도 entry in the current zone tree.
 */
export enum Region {
  BUSAN = 'BUSAN',
  CHUNGBUK = 'CHUNGBUK',
  CHUNGNAM = 'CHUNGNAM',
  DAEGU = 'DAEGU',
  DAEJEON = 'DAEJEON',
  GANGWON = 'GANGWON',
  GWANGJU_JEONNAM = 'GWANGJU_JEONNAM',
  GYEONGBUK = 'GYEONGBUK',
  GYEONGGI = 'GYEONGGI',
  GYEONGNAM = 'GYEONGNAM',
  INCHEON = 'INCHEON',
  JEJU = 'JEJU',
  JEONBUK = 'JEONBUK',
  SEJONG = 'SEJONG',
  SEOUL = 'SEOUL',
  ULSAN = 'ULSAN'
}

/** The four risk levels published daily by KMA. Ordered low to very high. */
export enum RiskLevel {
  HIGH = 'HIGH',
  LOW = 'LOW',
  MODERATE = 'MODERATE',
  VERY_HIGH = 'VERY_HIGH'
}

/** Season timing across years — has the season shifted? */
export type SeasonTiming = {
  /** Days per year. Positive means the season is lengthening. */
  lengthTrendDaysPerYear?: Maybe<Scalars['Float']['output']>;
  pollenType: PollenType;
  region: Region;
  seasons: Array<SeasonWindow>;
};

/** One pollen season, for one region and one year. */
export type SeasonWindow = {
  endDate: Scalars['String']['output'];
  lengthDays: Scalars['Int']['output'];
  pollenType: PollenType;
  region: Region;
  startDate: Scalars['String']['output'];
  year: Scalars['Int']['output'];
};

/** Ops status page. Stale when any job has not succeeded in over 26 hours. */
export type SystemStatus = {
  /** The most recent run of each job, one row per job name. */
  jobs: Array<JobRun>;
  stale: Scalars['Boolean']['output'];
};
