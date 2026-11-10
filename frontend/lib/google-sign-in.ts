// Google Identity Services is loaded only on the login/registration screens.
// Keep initialization separate from the mounted screen's callback: initialize
// once, while safely replacing handlers as the user changes auth routes.
type Credential = { credential?: string };
type Identity = {
  initialize: (options: { client_id: string; callback: (response: Credential) => void; ux_mode: "popup"; auto_select: boolean }) => void;
  renderButton: (element: HTMLElement, options: { type: "standard"; theme: "outline"; size: "large"; text: "continue_with"; shape: "rectangular"; width: number }) => void;
};
let initializedClient: string | null = null;
let currentHandler: ((credential: string) => void) | null = null;
export function mountGoogleButton(element: HTMLElement, clientId: string, onCredential: (credential: string) => void) {
  const identity = (window as Window & { google?: { accounts?: { id?: Identity } } }).google?.accounts?.id;
  if (!identity) throw new Error("Google sign-in could not be loaded.");
  if (initializedClient && initializedClient !== clientId) throw new Error("Reload to update Google sign-in configuration.");
  if (!initializedClient) {
    identity.initialize({ client_id: clientId, ux_mode: "popup", auto_select: false, callback: response => currentHandler?.(response.credential ?? "") });
    initializedClient = clientId;
  }
  currentHandler = onCredential;
  let lastWidth = 0;
  const render = () => {
    const width = Math.max(200, Math.min(400, Math.floor(element.clientWidth)));
    if (width === lastWidth) return;
    lastWidth = width;
    element.replaceChildren();
    identity.renderButton(element, { type: "standard", theme: "outline", size: "large", text: "continue_with", shape: "rectangular", width });
  };
  render();
  const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(render) : null;
  observer?.observe(element);
  return () => {
    observer?.disconnect();
    if (currentHandler === onCredential) currentHandler = null;
    element.replaceChildren();
  };
}
