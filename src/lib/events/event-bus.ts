import "server-only";

import { EventEmitter2 } from "eventemitter2";
import type { ActionRequest, ActionResponse } from "@/lib/actions";
import type { NormalizedEvent } from "@/lib/events/normalized-event";

export const PRODUCT_EVENTS = {
  CONNECTOR_EVENT: "connector.event",
  ACTION_REQUESTED: "action.requested",
  ACTION_RESPONSE: "action.response",
} as const;

type ProductEventName = (typeof PRODUCT_EVENTS)[keyof typeof PRODUCT_EVENTS];

type ProductEventMap = {
  [PRODUCT_EVENTS.CONNECTOR_EVENT]: [event: NormalizedEvent];
  [PRODUCT_EVENTS.ACTION_REQUESTED]: [request: ActionRequest];
  [PRODUCT_EVENTS.ACTION_RESPONSE]: [response: ActionResponse];
};

class ProductEventBus {
  private readonly emitter = new EventEmitter2({
    delimiter: ".",
    maxListeners: 50,
    wildcard: false,
  });

  on<K extends ProductEventName>(
    eventName: K,
    listener: (...args: ProductEventMap[K]) => void | Promise<void>,
  ): () => void {
    this.emitter.on(eventName, listener);
    return () => this.emitter.off(eventName, listener);
  }

  async emit<K extends ProductEventName>(
    eventName: K,
    ...args: ProductEventMap[K]
  ): Promise<void> {
    await this.emitter.emitAsync(eventName, ...args);
  }

  listenerCount(eventName: ProductEventName): number {
    return this.emitter.listenerCount(eventName);
  }
}

const globalForEventBus = globalThis as unknown as {
  productEventBus?: ProductEventBus;
};

export const eventBus =
  globalForEventBus.productEventBus ?? new ProductEventBus();

if (process.env.NODE_ENV !== "production") {
  globalForEventBus.productEventBus = eventBus;
}
