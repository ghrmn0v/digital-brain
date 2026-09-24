-- DropIndex
DROP INDEX "CalendarEvent_source_externalId_idx";

-- DropIndex
DROP INDEX "Task_source_externalId_idx";

-- AlterTable
ALTER TABLE "Automation" ADD COLUMN "lastError" TEXT;

-- AlterTable
ALTER TABLE "CalendarEvent" ADD COLUMN "recurrenceRule" TEXT;
ALTER TABLE "CalendarEvent" ADD COLUMN "reminderAt" DATETIME;

-- AlterTable
ALTER TABLE "Job" ADD COLUMN "archivedAt" DATETIME;
ALTER TABLE "Job" ADD COLUMN "relevanceReason" TEXT;
ALTER TABLE "Job" ADD COLUMN "skills" JSONB;

-- AlterTable
ALTER TABLE "Task" ADD COLUMN "recurrenceRule" TEXT;
ALTER TABLE "Task" ADD COLUMN "seriesId" TEXT;

-- CreateTable
CREATE TABLE "IntegrationEvent" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "eventId" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL,
    "payload" JSONB NOT NULL,
    "metadata" JSONB,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "EventDelivery" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "eventId" TEXT NOT NULL,
    "consumer" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "nextAttemptAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deliveredAt" DATETIME,
    "lastError" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "EventDelivery_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES "IntegrationEvent" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AutomationRun" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "automationId" TEXT NOT NULL,
    "actionExecutionId" TEXT,
    "eventId" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "error" TEXT,
    "startedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" DATETIME,
    CONSTRAINT "AutomationRun_automationId_fkey" FOREIGN KEY ("automationId") REFERENCES "Automation" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "AutomationRun_actionExecutionId_fkey" FOREIGN KEY ("actionExecutionId") REFERENCES "ActionExecution" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AppSetting" (
    "key" TEXT NOT NULL PRIMARY KEY,
    "value" JSONB NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_ActionExecution" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "source" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "payload" JSONB NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
    "permissionLevel" TEXT,
    "idempotencyKey" TEXT,
    "correlationId" TEXT,
    "result" JSONB,
    "error" TEXT,
    "decidedBy" TEXT,
    "decisionReason" TEXT,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "version" INTEGER NOT NULL DEFAULT 1,
    "requestedAt" DATETIME NOT NULL,
    "decidedAt" DATETIME,
    "completedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
INSERT INTO "new_ActionExecution" ("action", "completedAt", "createdAt", "decidedAt", "error", "id", "payload", "permissionLevel", "requestedAt", "result", "source", "status", "updatedAt") SELECT "action", "completedAt", "createdAt", "decidedAt", "error", "id", "payload", "permissionLevel", "requestedAt", "result", "source", "status", "updatedAt" FROM "ActionExecution";
DROP TABLE "ActionExecution";
ALTER TABLE "new_ActionExecution" RENAME TO "ActionExecution";
CREATE UNIQUE INDEX "ActionExecution_idempotencyKey_key" ON "ActionExecution"("idempotencyKey");
CREATE INDEX "ActionExecution_status_requestedAt_idx" ON "ActionExecution"("status", "requestedAt");
CREATE INDEX "ActionExecution_action_idx" ON "ActionExecution"("action");
CREATE INDEX "ActionExecution_source_correlationId_idx" ON "ActionExecution"("source", "correlationId");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE UNIQUE INDEX "IntegrationEvent_eventId_key" ON "IntegrationEvent"("eventId");

-- CreateIndex
CREATE INDEX "IntegrationEvent_source_type_idx" ON "IntegrationEvent"("source", "type");

-- CreateIndex
CREATE INDEX "IntegrationEvent_createdAt_idx" ON "IntegrationEvent"("createdAt");

-- CreateIndex
CREATE INDEX "EventDelivery_status_nextAttemptAt_idx" ON "EventDelivery"("status", "nextAttemptAt");

-- CreateIndex
CREATE UNIQUE INDEX "EventDelivery_eventId_consumer_key" ON "EventDelivery"("eventId", "consumer");

-- CreateIndex
CREATE INDEX "AutomationRun_automationId_startedAt_idx" ON "AutomationRun"("automationId", "startedAt");

-- CreateIndex
CREATE INDEX "AutomationRun_status_startedAt_idx" ON "AutomationRun"("status", "startedAt");

-- CreateIndex
CREATE INDEX "CalendarEvent_reminderAt_idx" ON "CalendarEvent"("reminderAt");

-- CreateIndex
CREATE UNIQUE INDEX "CalendarEvent_source_externalId_key" ON "CalendarEvent"("source", "externalId");

-- CreateIndex
CREATE INDEX "Task_seriesId_idx" ON "Task"("seriesId");

-- CreateIndex
CREATE UNIQUE INDEX "Task_source_externalId_key" ON "Task"("source", "externalId");
