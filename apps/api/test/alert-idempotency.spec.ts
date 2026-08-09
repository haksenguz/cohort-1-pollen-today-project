import "reflect-metadata";
import { describe, it, expect, beforeAll, afterAll, beforeEach } from "vitest";
import { Model } from "mongoose";
import { PollenType, Region, RiskLevel } from "@pollen/contracts";
import {
  Alert,
  AlertSchema,
} from "../src/components/alerts/schemas/alert.schema";
import {
  startMongoMemoryServer,
  stopMongoMemoryServer,
  getMongoConnection,
} from "./setup-mongo";

describe("Alert Idempotency", () => {
  let alertModel: Model<Alert>;

  beforeAll(async () => {
    await startMongoMemoryServer();
    const connection = getMongoConnection();
    alertModel = connection.model<Alert>("Alert", AlertSchema);
    await alertModel.syncIndexes();
  });

  afterAll(async () => {
    await stopMongoMemoryServer();
  });

  beforeEach(async () => {
    await alertModel.collection.deleteMany({});
  });

  it("creates the unique delivery index", async () => {
    const indexes = await alertModel.collection.indexes();
    const uniqueIndex = indexes.find(
      (idx) => idx.name === "uniq_alert_delivery",
    );

    expect(uniqueIndex).toBeDefined();
    expect(uniqueIndex?.unique).toBe(true);
  });

  it("rejects a duplicate delivery at the database", async () => {
    const alertData = {
      channel: "telegram",
      region: Region.SEOUL,
      pollenType: PollenType.WEEDS,
      targetDate: "2026-08-10",
      riskLevel: RiskLevel.HIGH,
      sentAt: new Date(),
      messageText: "Test message",
    };

    await alertModel.create(alertData);

    await expect(alertModel.create(alertData)).rejects.toMatchObject({
      code: 11000,
    });
  });

  it("allows the same alert on a different targetDate", async () => {
    const baseData = {
      channel: "telegram",
      region: Region.SEOUL,
      pollenType: PollenType.WEEDS,
      riskLevel: RiskLevel.HIGH,
      sentAt: new Date(),
      messageText: "Test message",
    };

    await alertModel.create({
      ...baseData,
      targetDate: "2026-08-10",
    });

    const doc2 = await alertModel.create({
      ...baseData,
      targetDate: "2026-08-11",
    });

    expect(doc2.targetDate).toBe("2026-08-11");
  });

  it("allows the same day in a different region", async () => {
    const baseData = {
      channel: "telegram",
      pollenType: PollenType.WEEDS,
      targetDate: "2026-08-10",
      riskLevel: RiskLevel.HIGH,
      sentAt: new Date(),
      messageText: "Test message",
    };

    await alertModel.create({
      ...baseData,
      region: Region.SEOUL,
    });

    const doc2 = await alertModel.create({
      ...baseData,
      region: Region.BUSAN,
    });

    expect(doc2.region).toBe(Region.BUSAN);
  });
});
