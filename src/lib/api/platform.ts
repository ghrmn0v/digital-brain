import { ApiError } from "@/lib/api/errors";

export const CLIENT_PLATFORM_HEADER = "x-product-client-platform";

export type ProductClientPlatform = "desktop" | "mobile" | "unknown";

export function getClientPlatform(request: Request): ProductClientPlatform {
  const value = request.headers.get(CLIENT_PLATFORM_HEADER)?.trim().toLowerCase();
  if (value === "desktop" || value === "mobile") return value;
  return "unknown";
}

export function requireDesktopClient(request: Request): void {
  if (getClientPlatform(request) !== "desktop") {
    throw new ApiError(
      403,
      "DESKTOP_CLIENT_REQUIRED",
      "Developer Mode controls are available on the desktop client only.",
    );
  }
}
