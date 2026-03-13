type EventPayload = Record<string, string | number | boolean | null | undefined>;

type WindowWithTracking = Window & {
    dataLayer?: Array<Record<string, unknown>>;
    gtag?: (command: "event", eventName: string, params?: Record<string, unknown>) => void;
};

export function trackEvent(eventName: string, payload: EventPayload = {}): void {
    if (typeof window === "undefined") {
        return;
    }

    const trackingWindow = window as WindowWithTracking;
    const eventPayload = {
        event: eventName,
        ...payload,
        ts: Date.now(),
    };

    if (typeof trackingWindow.gtag === "function") {
        trackingWindow.gtag("event", eventName, payload);
    }

    if (Array.isArray(trackingWindow.dataLayer)) {
        trackingWindow.dataLayer.push(eventPayload);
    }

    window.dispatchEvent(new CustomEvent("app:track", { detail: eventPayload }));
}
