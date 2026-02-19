import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

const tenantId = import.meta.env.VITE_AZURE_TENANT_ID as string;
const clientId = import.meta.env.VITE_AZURE_CLIENT_ID as string;

const redirectUri = import.meta.env.VITE_AZURE_REDIRECT_URI as string;
const postLogoutRedirectUri = import.meta.env.VITE_AZURE_POST_LOGOUT_REDIRECT_URI as string;

if (!tenantId || !clientId) {
  throw new Error("Missing VITE_AZURE_TENANT_ID or VITE_AZURE_CLIENT_ID in .env");
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