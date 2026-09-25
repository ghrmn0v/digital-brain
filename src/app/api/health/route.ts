import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    await prisma.$queryRaw`SELECT 1`;
    await prisma.$queryRaw`SELECT 1 FROM "Task" LIMIT 1`;

    return NextResponse.json({
      service: "digital-brain-product",
      phase: 2,
      database: "connected",
      schema: "ready",
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Database readiness check failed.", error);
    return NextResponse.json(
      {
        service: "digital-brain-product",
        phase: 2,
        database: "unavailable",
        schema: "not_ready",
        timestamp: new Date().toISOString(),
      },
      { status: 503 },
    );
  }
}
