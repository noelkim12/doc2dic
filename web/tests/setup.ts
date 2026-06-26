import "@testing-library/jest-dom/vitest";

// Polyfills for jsdom test environment
class ResizeObserverPolyfill {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (!global.ResizeObserver) {
  global.ResizeObserver = ResizeObserverPolyfill as unknown as typeof ResizeObserver;
}

// Fix d3-drag incompatibility with jsdom (used internally by @xyflow/react)
if (!SVGElement.prototype.getScreenCTM) {
  SVGElement.prototype.getScreenCTM = () => null;
}
