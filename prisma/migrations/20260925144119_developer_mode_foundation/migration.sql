-- CreateTable
CREATE TABLE "DeveloperProposal" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "eventId" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "decidedBy" TEXT,
    "decisionReason" TEXT,
    "decidedAt" DATETIME,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "DeveloperProposal_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES "IntegrationEvent" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "DeveloperProposal_eventId_key" ON "DeveloperProposal"("eventId");

-- CreateIndex
CREATE INDEX "DeveloperProposal_status_createdAt_idx" ON "DeveloperProposal"("status", "createdAt");
