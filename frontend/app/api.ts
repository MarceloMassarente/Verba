import {
  ConnectPayload,
  HealthPayload,
  RAGConfig,
  QueryPayload,
  Credentials,
  DocumentsPreviewPayload,
  DocumentPayload,
  ChunkScore,
  ContentPayload,
  ChunksPayload,
  RAGConfigResponse,
  AllSuggestionsPayload,
  MetadataPayload,
  DatacountResponse,
  SuggestionsPayload,
  ChunkPayload,
  DocumentFilter,
  VectorsPayload,
  UserConfigResponse,
  ThemeConfigResponse,
  Theme,
  UserConfig,
  LabelsResponse,
  Themes,
} from "./types";

const checkUrl = async (url: string, timeout = 5000): Promise<boolean> => {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);
    return response.ok;
  } catch (error) {
    // Only log if not aborted
    if (error instanceof Error && error.name !== 'AbortError') {
      console.warn(`Failed to fetch from ${url}:`, error.message);
    }
    return false;
  }
};

// Cache the detected host to avoid repeated checks
let cachedHost: string | null = null;

export const detectHost = async (): Promise<string> => {
  // Return cached host if available
  if (cachedHost) {
    return cachedHost;
  }

  const localUrl = "http://localhost:8000/api/health";
  const rootUrl = "/api/health";

  // Check if we're in a production environment (not localhost)
  const isProduction = typeof window !== 'undefined' &&
    !window.location.hostname.includes('localhost') &&
    !window.location.hostname.includes('127.0.0.1');

  // In production (Railway, etc.), try relative URL first (faster, no CORS issues)
  if (isProduction) {
    const isRootHealthy = await checkUrl(rootUrl);
    if (isRootHealthy) {
      cachedHost = window.location.origin;
      return cachedHost;
    }

    // Retry once with a longer timeout
    const isRootHealthyRetry = await checkUrl(rootUrl, 10000);
    if (isRootHealthyRetry) {
      cachedHost = window.location.origin;
      return cachedHost;
    }
  } else {
    // In development, try localhost first
    const isLocalHealthy = await checkUrl(localUrl);
    if (isLocalHealthy) {
      cachedHost = "http://localhost:8000";
      return cachedHost;
    }

    const isRootHealthy = await checkUrl(rootUrl);
    if (isRootHealthy) {
      cachedHost = window.location.origin;
      return cachedHost;
    }
  }

  // If both fail in production, use origin anyway (the server might just be starting)
  if (isProduction) {
    console.warn("Health checks failed, using window.location.origin as fallback");
    cachedHost = window.location.origin;
    return cachedHost;
  }

  throw new Error("Both health checks failed, please check the Verba Server");
};

export const fetchData = async <T>(endpoint: string): Promise<T | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}${endpoint}`, { method: "GET" });
    const data = await response.json();

    if (!data) {
      console.warn(`Could not retrieve data from ${endpoint}`);
    }

    return data;
  } catch (error) {
    console.error(`Failed to fetch data from ${endpoint}:`, error);
    return null;
  }
};

// Endpoint /api/health
export const fetchHealth = (): Promise<HealthPayload | null> =>
  fetchData<HealthPayload>("/api/health");

// Endpoint /api/connect
export const connectToVerba = async (
  deployment: string,
  url: string,
  apiKey: string,
  port: string
): Promise<ConnectPayload | null> => {
  const host = await detectHost();
  const response = await fetch(`${host}/api/connect`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      credentials: {
        deployment: deployment,
        url: url,
        key: apiKey,
      },
      port: port,
    }),
  });
  const data = await response.json();
  return data;
};

// Endpoint /api/get_rag_config
export const fetchRAGConfig = async (
  credentials: Credentials
): Promise<RAGConfigResponse | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_rag_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });
    const data: RAGConfigResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/set_rag_config
export const updateRAGConfig = async (
  RAG: RAGConfig | null,
  credentials: Credentials
): Promise<boolean> => {
  if (!RAG) {
    return false;
  }

  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/set_rag_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ rag_config: RAG, credentials: credentials }),
    });

    return response.status === 200;
  } catch (error) {
    console.error("Error setting config:", error);
    return false;
  }
};

// Endpoint /api/get_user_config
export const fetchUserConfig = async (
  credentials: Credentials
): Promise<UserConfigResponse | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_user_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });
    const data: UserConfigResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/set_user_config
export const updateUserConfig = async (
  user_config: UserConfig,
  credentials: Credentials
): Promise<boolean> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/set_user_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_config: user_config,
        credentials: credentials,
      }),
    });

    return response.status === 200;
  } catch (error) {
    console.error("Error setting config:", error);
    return false;
  }
};

// Endpoint /api/get_theme_config
export const fetchThemeConfig = async (
  credentials: Credentials
): Promise<ThemeConfigResponse | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_theme_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });
    const data: ThemeConfigResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/set_theme_config
export const updateThemeConfig = async (
  themes: Themes,
  theme: Theme,
  credentials: Credentials
): Promise<boolean> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/set_theme_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        themes: themes,
        theme: theme,
        credentials: credentials,
      }),
    });

    return response.status === 200;
  } catch (error) {
    console.error("Error setting config:", error);
    return false;
  }
};

// Endpoint /api/get_reranker_presets
export const fetchRerankerPresets = async (
  credentials: Credentials
): Promise<{ presets: any[]; error: string } | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_reranker_presets`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ credentials }),
    });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving reranker presets:", error);
    return null;
  }
};

// Endpoint /api/apply_reranker_preset
export const applyRerankerPreset = async (
  preset_name: string,
  query: string | null,
  credentials: Credentials
): Promise<{ status: number; preset_applied?: string; config?: any; status_msg?: string } | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/apply_reranker_preset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preset_name: preset_name,
        query: query,
        credentials: credentials,
      }),
    });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error applying reranker preset:", error);
    return null;
  }
};

// Endpoint /api/get_preset_config - Retorna RAGConfig completo com preset aplicado
export const fetchPresetConfig = async (
  presetName: string,
  credentials: Credentials
): Promise<{ status: number; rag_config?: RAGConfig; preset_applied?: string; status_msg?: string } | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_preset_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preset_name: presetName,
        credentials: credentials,
      }),
    });
    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error fetching preset config:", error);
    return null;
  }
};

// Endpoint /api/query
export const sendUserQuery = async (
  query: string,
  RAG: RAGConfig | null,
  labels: string[],
  documentFilter: DocumentFilter[],
  credentials: Credentials
): Promise<QueryPayload | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query,
        RAG: RAG,
        labels: labels,
        documentFilter: documentFilter,
        credentials: credentials,
      }),
    });

    const data: QueryPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error sending query", error);
    return null;
  }
};

// Endpoint /api/get_document
export const fetchSelectedDocument = async (
  uuid: string | null,
  credentials: Credentials
): Promise<DocumentPayload | null> => {
  if (!uuid) {
    return null;
  }

  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_document`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        credentials: credentials,
      }),
    });
    const data: DocumentPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving selected document", error);
    return null;
  }
};

// Endpoint /api/get_datacount
export const fetchDatacount = async (
  embedding_model: string,
  documentFilter: DocumentFilter[],
  credentials: Credentials
): Promise<DatacountResponse | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_datacount`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        embedding_model: embedding_model,
        documentFilter: documentFilter,
        credentials: credentials,
      }),
    });
    const data: DatacountResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/get_labels
export const fetchLabels = async (
  credentials: Credentials
): Promise<LabelsResponse | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_labels`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });
    const data: LabelsResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/get_content
export const fetchContent = async (
  uuid: string | null,
  page: number,
  chunkScores: ChunkScore[],
  credentials: Credentials
): Promise<ContentPayload | null> => {
  if (!uuid) {
    return null;
  }

  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_content`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        page: page,
        chunkScores: chunkScores,
        credentials: credentials,
      }),
    });
    const data: ContentPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/get_vectors
export const fetch_vectors = async (
  uuid: string | null,
  showAll: boolean,
  credentials: Credentials
): Promise<VectorsPayload | null> => {
  if (!uuid) {
    return null;
  }

  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_vectors`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        showAll: showAll,
        credentials: credentials,
      }),
    });
    const data: VectorsPayload | null = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/get_chunks
export const fetch_chunks = async (
  uuid: string | null,
  page: number,
  pageSize: number,
  credentials: Credentials
): Promise<ChunksPayload | null> => {
  if (!uuid) {
    return null;
  }

  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_chunks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        page: page,
        pageSize: pageSize,
        credentials: credentials,
      }),
    });
    const data: ChunksPayload | null = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/get_chunk
export const fetch_chunk = async (
  uuid: string | null,
  embedder: string,
  credentials: Credentials
): Promise<ChunkPayload | null> => {
  if (!uuid) {
    return null;
  }

  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_chunk`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        embedder: embedder,
        credentials: credentials,
      }),
    });
    const data: ChunkPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving content", error);
    return null;
  }
};

// Endpoint /api/get_all_documents
export const retrieveAllDocuments = async (
  query: string,
  labels: string[],
  page: number,
  pageSize: number,
  credentials: Credentials
): Promise<DocumentsPreviewPayload | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_all_documents`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query,
        labels: labels,
        page: page,
        pageSize: pageSize,
        credentials: credentials,
      }),
    });
    const data: DocumentsPreviewPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving all documents", error);
    return null;
  }
};

// Endpoint /api/delete_document
export const deleteDocument = async (
  uuid: string,
  credentials: Credentials
): Promise<boolean> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/delete_document`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        credentials: credentials,
      }),
    });
    return response.status === 200;
  } catch (error) {
    console.error("Error deleting document", error);
    return false;
  }
};

// Endpoint /api/reset
export const deleteAllDocuments = async (
  resetMode: string,
  credentials: Credentials
): Promise<boolean> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/reset`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        resetMode: resetMode,
        credentials: credentials,
      }),
    });
    return response.status === 200;
  } catch (error) {
    console.error("Error deleting all documents", error);
    return false;
  }
};

// Endpoint /api/get_meta
export const fetchMeta = async (
  credentials: Credentials
): Promise<MetadataPayload | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_meta`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(credentials),
    });
    const data: MetadataPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving selected document", error);
    return null;
  }
};

// Endpoint /api/get_suggestions
export const fetchSuggestions = async (
  query: string,
  limit: number,
  credentials: Credentials
): Promise<SuggestionsPayload | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_suggestions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query: query,
        limit: limit,
        credentials: credentials,
      }),
    });
    const data: SuggestionsPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving suggestions", error);
    return null;
  }
};

// Endpoint /api/delete_suggestion
export const deleteSuggestion = async (
  uuid: string,
  credentials: Credentials
): Promise<boolean> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/delete_suggestion`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        uuid: uuid,
        credentials: credentials,
      }),
    });
    return response.status === 200;
  } catch (error) {
    console.error("Error deleting suggestion", error);
    return false;
  }
};

// Endpoint /api/get_all_suggestions
export const fetchAllSuggestions = async (
  page: number,
  pageSize: number,
  credentials: Credentials
): Promise<AllSuggestionsPayload | null> => {
  try {
    const host = await detectHost();
    const response = await fetch(`${host}/api/get_all_suggestions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        page: page,
        pageSize: pageSize,
        credentials: credentials,
      }),
    });
    const data: AllSuggestionsPayload = await response.json();
    return data;
  } catch (error) {
    console.error("Error retrieving all suggestions", error);
    return null;
  }
};
