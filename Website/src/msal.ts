import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

// Required env vars
const tenantId = String(import.meta.env.VITE_AZURE_TENANT_ID || "");
const clientId = String(import.meta.env.VITE_AZURE_CLIENT_ID || "");
const redirectUri = String(import.meta.env.VITE_AZURE_REDIRECT_URI || "http://localhost:5173");
const postLogoutRedirectUri = String(
  import.meta.env.VITE_AZURE_POST_LOGOUT_REDIRECT_URI || "http://localhost:5173/login"
);

if (!tenantId || !clientId) {
  throw new Error("Missing VITE_AZURE_TENANT_ID or VITE_AZURE_CLIENT_ID in Website/.env");
}

export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
    postLogoutRedirectUri,
  },
  cache: {
    cacheLocation: "localStorage",
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);
