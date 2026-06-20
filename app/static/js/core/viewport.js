/** Match responsive.css mobile breakpoint. */
export function isMobileViewport(breakpointPx = 640) {
  return window.matchMedia(`(max-width: ${breakpointPx}px)`).matches;
}
