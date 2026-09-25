export type DeveloperToolCapability =
  | "repository_context"
  | "git"
  | "testing"
  | "deployment";

export interface RepositoryProjectContext {
  repository: string;
  project?: string;
  branch?: string;
  revision?: string;
}

export interface DeveloperToolPort {
  readonly capability: DeveloperToolCapability;
  isAvailable(): Promise<boolean>;
}

export interface RepositoryProjectPort extends DeveloperToolPort {
  readonly capability: "repository_context";
  getContext(): Promise<RepositoryProjectContext>;
}

export interface GitPort extends DeveloperToolPort {
  readonly capability: "git";
}

export interface TestingPort extends DeveloperToolPort {
  readonly capability: "testing";
}

export interface DeploymentPort extends DeveloperToolPort {
  readonly capability: "deployment";
}
