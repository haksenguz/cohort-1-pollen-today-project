import { MongoMemoryServer } from "mongodb-memory-server";
import { connect, Connection, disconnect } from "mongoose";

let mongoServer: MongoMemoryServer;
let mongoConnection: Connection;

/**
 * Start a MongoMemoryServer and connect mongoose to it.
 * Call this in beforeAll or setup hooks.
 */
export async function startMongoMemoryServer(): Promise<Connection> {
  // MongoDB publishes no Windows aarch64 build, and this machine reports
  // arm64. Windows runs x64 binaries under emulation, so ask for that
  // explicitly instead of letting the downloader pick a URL that 403s.
  const binary =
    process.platform === "win32" && process.arch === "arm64"
      ? { arch: "x64" as const }
      : undefined;

  mongoServer = await MongoMemoryServer.create({ binary });
  const uri = mongoServer.getUri();
  mongoConnection = (await connect(uri)).connection;
  return mongoConnection;
}

/**
 * Get the active mongoose connection.
 */
export function getMongoConnection(): Connection {
  if (!mongoConnection) {
    throw new Error(
      "MongoDB connection not established. Call startMongoMemoryServer first.",
    );
  }
  return mongoConnection;
}

/**
 * Stop the MongoMemoryServer and disconnect mongoose.
 * Call this in afterAll or teardown hooks.
 */
export async function stopMongoMemoryServer(): Promise<void> {
  if (mongoConnection) {
    await disconnect();
  }
  if (mongoServer) {
    await mongoServer.stop();
  }
}
