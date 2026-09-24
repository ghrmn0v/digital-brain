import "dotenv/config";
import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";
import { PrismaClient } from "../src/generated/prisma/client";

const connectionString = process.env.DATABASE_URL ?? "file:./dev.db";
const adapter = new PrismaBetterSqlite3({ url: connectionString });
const prisma = new PrismaClient({ adapter });

const permissionDefaults = [
  {
    source: "core_brain",
    action: "tasks.create_task",
    level: "ASK_FIRST" as const,
    description: "Create a local task requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "tasks.update_task",
    level: "ASK_FIRST" as const,
    description: "Update a local task requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "tasks.complete_task",
    level: "ASK_FIRST" as const,
    description: "Complete a local task requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "tasks.delete_task",
    level: "OFF" as const,
    description: "Delete a local task requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "calendar.create_event",
    level: "ASK_FIRST" as const,
    description: "Create a local calendar event requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "calendar.update_event",
    level: "ASK_FIRST" as const,
    description: "Update a local calendar event requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "calendar.delete_event",
    level: "OFF" as const,
    description: "Delete a local calendar event requested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "jobs.save_job",
    level: "ASK_FIRST" as const,
    description: "Save a job suggested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "jobs.ignore_job",
    level: "ASK_FIRST" as const,
    description: "Hide a job suggested by Core Brain.",
  },
  {
    source: "core_brain",
    action: "jobs.apply_job",
    level: "OFF" as const,
    description: "Apply to a job. External application execution is disabled by default.",
  },
] as const;

const connectorDefaults = [
  { id: "linkedin", name: "LinkedIn", type: "linkedin" },
  { id: "calendar", name: "Calendar", type: "calendar" },
  { id: "whatsapp", name: "WhatsApp", type: "whatsapp" },
  { id: "telegram", name: "Telegram", type: "telegram" },
  { id: "browser", name: "Browser", type: "browser" },
  { id: "notes", name: "Notes", type: "notes" },
] as const;

async function main() {
  for (const permission of permissionDefaults) {
    await prisma.permission.upsert({
      where: {
        source_action: {
          source: permission.source,
          action: permission.action,
        },
      },
      update: {
        level: permission.level,
        description: permission.description,
        enabled: true,
      },
      create: permission,
    });
  }

  for (const connector of connectorDefaults) {
    await prisma.connector.upsert({
      where: { id: connector.id },
      update: {
        name: connector.name,
        type: connector.type,
      },
      create: connector,
    });
  }

  await prisma.appSetting.upsert({
    where: { key: "product.locale" },
    update: {},
    create: { key: "product.locale", value: "az" },
  });

  await prisma.appSetting.upsert({
    where: { key: "jobs.daily_report_time" },
    update: {},
    create: { key: "jobs.daily_report_time", value: "09:00" },
  });
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (error: unknown) => {
    console.error("Database seed failed.", error);
    await prisma.$disconnect();
    process.exitCode = 1;
  });
