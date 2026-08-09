
/*
 * -------------------------------------------------------
 * THIS FILE WAS AUTOMATICALLY GENERATED (DO NOT MODIFY)
 * -------------------------------------------------------
 */

/* tslint:disable */
/* eslint-disable */

// GENERATED FROM src/schema/*.graphql — DO NOT EDIT BY HAND.
// Regenerate with: pnpm --filter @pollen/api schema:generate

export enum RiskLevel {
    LOW = "LOW",
    MODERATE = "MODERATE",
    HIGH = "HIGH",
    VERY_HIGH = "VERY_HIGH"
}

export enum PollenType {
    OAK = "OAK",
    PINE = "PINE",
    WEEDS = "WEEDS"
}

export enum Region {
    SEOUL = "SEOUL",
    BUSAN = "BUSAN",
    DAEGU = "DAEGU",
    INCHEON = "INCHEON",
    DAEJEON = "DAEJEON",
    ULSAN = "ULSAN",
    SEJONG = "SEJONG",
    GWANGJU_JEONNAM = "GWANGJU_JEONNAM",
    GYEONGGI = "GYEONGGI",
    GANGWON = "GANGWON",
    CHUNGBUK = "CHUNGBUK",
    CHUNGNAM = "CHUNGNAM",
    JEONBUK = "JEONBUK",
    GYEONGBUK = "GYEONGBUK",
    GYEONGNAM = "GYEONGNAM",
    JEJU = "JEJU"
}

export enum JobStatus {
    SUCCESS = "SUCCESS",
    FAILED = "FAILED",
    RUNNING = "RUNNING"
}

export interface Alert {
    id: ObjectId;
    region: Region;
    pollenType: PollenType;
    targetDate: string;
    riskLevel: RiskLevel;
    channel: string;
    sentAt: DateTime;
    messageText: string;
}

export interface PaginatedAlert {
    items: Alert[];
    total: number;
    hasMore: boolean;
}

export interface IQuery {
    alertHistory?: PaginatedAlert;
    seasonTiming?: SeasonTiming;
    forecast?: Forecast;
    systemStatus: SystemStatus;
}

export interface SeasonWindow {
    year: number;
    region: Region;
    pollenType: PollenType;
    startDate: string;
    endDate: string;
    lengthDays: number;
}

export interface SeasonTiming {
    region: Region;
    pollenType: PollenType;
    seasons: SeasonWindow[];
    lengthTrendDaysPerYear?: Nullable<number>;
}

export interface ForecastDay {
    date: string;
    riskLevel: RiskLevel;
    confidence?: Nullable<number>;
}

export interface Forecast {
    region: Region;
    pollenType: PollenType;
    days: ForecastDay[];
    modelVersion: string;
    generatedAt: DateTime;
}

export interface JobRun {
    jobName: string;
    startedAt: DateTime;
    finishedAt?: Nullable<DateTime>;
    status: JobStatus;
    rowsAffected?: Nullable<number>;
    error?: Nullable<string>;
}

export interface SystemStatus {
    jobs: JobRun[];
    stale: boolean;
}

export type DateTime = Date;
export type ObjectId = string;
type Nullable<T> = T | null;
