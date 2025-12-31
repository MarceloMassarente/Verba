"use client";

import React, { useState, useEffect, useCallback } from "react";
import { GoTriangleDown } from "react-icons/go";
import { RAGConfig, RAGComponentConfig, ConfigSetting, Credentials, RerankerPreset } from "@/app/types";
import VerbaButton from "../Navigation/VerbaButton";
import { fetchRerankerPresets, applyRerankerPreset } from "@/app/api";

interface RetrieverConfigBlocksProps {
  RAGConfig: RAGConfig;
  blocked: boolean | undefined;
  selectComponent: (component_n: string, selected_component: string) => void;
  updateConfig: (
    component_n: string,
    configTitle: string,
    value: string | boolean | string[]
  ) => void;
  saveComponentConfig: (
    component_n: string,
    selected_component: string,
    config: RAGComponentConfig
  ) => void;
  credentials: Credentials;
  currentQuery?: string;
}

interface ConfigBlock {
  name: string;
  title: string;
  description: string;
  configs: string[];
  mode?: "radio" | "checkbox";
  collapsible?: boolean;
  defaultOpen?: boolean;
  condition?: (config: any) => boolean;
  icon?: string;
  priority?: "critical" | "important" | "advanced";
}

const BLOCKS: ConfigBlock[] = [
  // ORDEM INTUITIVA: Top-Down Decision Flow

  // 1. ARQUITETURA - DecisÃ£o mais importante
  {
    name: "search_mode",
    title: "ðŸ—ï¸ Arquitetura de Busca",
    description: "Escolha como a busca serÃ¡ executada (mutuamente exclusivos)",
    mode: "radio",
    priority: "critical",
    defaultOpen: true,
    configs: [
      "Two-Phase Search Mode",
      "Two-Phase Search Filter Level",
      "Enable Multi-Vector Search",
      "Enable Aggregation"
    ],
  },

  // 2. FUNDAMENTOS - ParÃ¢metros principais
  {
    name: "fundamental",
    title: "âš™ï¸ Busca Fundamental",
    description: "ParÃ¢metros principais de busca e reranking",
    priority: "critical",
    defaultOpen: true,
    configs: [
      "Search Mode",
      "Use Section Hierarchy",
      "Limit Mode",
      "Limit/Sensitivity",
      "Alpha",
      "Reranker Top K",
    ],
  },

  // 3. FILTROS - Refinar resultados
  {
    name: "filters",
    title: "ðŸ” Filtros",
    description: "Aplique filtros independentes para refinar os resultados",
    priority: "important",
    defaultOpen: true,
    configs: [
      "Enable Entity Filter",
      "Entity Filter Mode",
      "Enable Semantic Search",
      "Enable Language Filter",
      "Enable Temporal Filter",
      "Date Field Name",
      "Enable Framework Filter",
    ],
  },

  // 4. OTIMIZAÃ‡Ã•ES - Melhorias (avanÃ§ado)
  {
    name: "optimizations",
    title: "âš¡ OtimizaÃ§Ãµes",
    description: "Melhorias opcionais de performance e qualidade (usuÃ¡rios avanÃ§ados)",
    priority: "advanced",
    collapsible: true,
    defaultOpen: false,
    configs: [
      "Enable Intelligent Cache",
      "Cache Similarity Threshold",
      "Enable Dynamic Reranking",
      "Reranking Recency Weight",
      "Reranking Entity Weight",
      "Reranker Preset",
      "Enable Query Expansion",
      "Enable Dynamic Alpha",
      "Enable Relative Score Fusion",
      "Enable Query Rewriting",
      "Query Rewriter Cache TTL",
      "Chunk Window",
    ],
  },

  // 5. RERANKER - Subdividido por provider
  {
    name: "reranker_basic",
    title: "ðŸŽ¯ Reranker - ConfiguraÃ§Ã£o BÃ¡sica",
    description: "Escolha o provedor de reranking",
    priority: "important",
    defaultOpen: true,
    configs: [
      "Reranker Provider",
      "Reranker Mode",
      "Top K",
      "Enable Metadata Reranker",
    ],
  },
  {
    name: "reranker_haystack",
    title: "ðŸŽ¯ Reranker - Haystack",
    description: "ConfiguraÃ§Ãµes especÃ­ficas do Haystack",
    priority: "advanced",
    collapsible: true,
    defaultOpen: false,
    condition: (config) => config["Enable Haystack Reranker"]?.value === true,
    configs: [
      "Enable Haystack Reranker",
      "Haystack Model",
    ],
  },
  {
    name: "reranker_cohere",
    title: "ðŸŽ¯ Reranker - Cohere",
    description: "ConfiguraÃ§Ãµes especÃ­ficas do Cohere",
    priority: "advanced",
    collapsible: true,
    defaultOpen: false,
    condition: (config) => config["Enable Cohere Reranker"]?.value === true,
    configs: [
      "Enable Cohere Reranker",
      "Cohere Model",
      "Cohere API Key",
      "Cohere Base URL",
    ],
  },
  {
    name: "reranker_jina",
    title: "ðŸŽ¯ Reranker - Jina",
    description: "ConfiguraÃ§Ãµes especÃ­ficas do Jina",
    priority: "advanced",
    collapsible: true,
    defaultOpen: false,
    condition: (config) => config["Enable Jina Reranker"]?.value === true,
    configs: [
      "Enable Jina Reranker",
      "Jina API Key",
      "Jina Base URL",
    ],
  },
  {
    name: "reranker_voyageai",
    title: "ðŸŽ¯ Reranker - VoyageAI",
    description: "ConfiguraÃ§Ãµes especÃ­ficas do VoyageAI",
    priority: "advanced",
    collapsible: true,
    defaultOpen: false,
    condition: (config) => config["Enable VoyageAI Reranker"]?.value === true,
    configs: [
      "Enable VoyageAI Reranker",
      "VoyageAI API Key",
      "VoyageAI Base URL",
    ],
  },
  {
    name: "reranker_contextualai",
    title: "ðŸŽ¯ Reranker - ContextualAI",
    description: "ConfiguraÃ§Ãµes especÃ­ficas do ContextualAI",
    priority: "advanced",
    collapsible: true,
    defaultOpen: false,
    condition: (config) => config["Enable ContextualAI Reranker"]?.value === true,
    configs: [
      "Enable ContextualAI Reranker",
      "ContextualAI Model",
      "ContextualAI Instruction",
      "ContextualAI API Key",
      "ContextualAI Base URL",
    ],
  },
];

const RetrieverConfigBlocks: React.FC<RetrieverConfigBlocksProps> = ({
  RAGConfig,
  blocked,
  selectComponent,
  updateConfig,
  saveComponentConfig,
  credentials,
  currentQuery = "",
}) => {
  const [warnings, setWarnings] = useState<string[]>([]);
  const [disabledFields, setDisabledFields] = useState<Set<string>>(new Set());
  const [rerankerPresets, setRerankerPresets] = useState<RerankerPreset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>("consulting_frameworks");
  const [loadingPresets, setLoadingPresets] = useState(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);

  // Estado para collapse de blocos
  const [expandedBlocks, setExpandedBlocks] = useState<Set<string>>(
    new Set(BLOCKS.filter(b => b.defaultOpen !== false).map(b => b.name))
  );

  const toggleBlock = (blockName: string) => {
    setExpandedBlocks(prev => {
      const next = new Set(prev);
      if (next.has(blockName)) {
        next.delete(blockName);
      } else {
        next.add(blockName);
      }
      return next;
    });
  };

  // ValidaÃ§Ã£o e auto-ajuste no cliente
  const validateAndAdjust = useCallback(
    (config: { [key: string]: ConfigSetting }) => {
      const newWarnings: string[] = [];
      const newDisabledFields = new Set<string>();
      const adjusted = { ...config };

      // REGRA 1: Two-Phase Search desabilita Entity Filter
      const twoPhase = adjusted["Two-Phase Search Mode"];
      if (twoPhase && twoPhase.value !== "disabled") {
        if (adjusted["Enable Entity Filter"]?.value) {
          adjusted["Enable Entity Filter"].value = false;
          newWarnings.push(
            "Entity Filter desabilitado automaticamente (redundante com Two-Phase Search)"
          );
        }
        newDisabledFields.add("Enable Entity Filter");
        newDisabledFields.add("Entity Filter Mode");
      }

      // REGRA 2: Aggregation desabilita tudo
      if (adjusted["Enable Aggregation"]?.value) {
        if (adjusted["Enable Entity Filter"]?.value) {
          adjusted["Enable Entity Filter"].value = false;
        }
        if (adjusted["Two-Phase Search Mode"]?.value !== "disabled") {
          adjusted["Two-Phase Search Mode"].value = "disabled";
        }
        if (adjusted["Enable Multi-Vector Search"]?.value) {
          adjusted["Enable Multi-Vector Search"].value = false;
        }
        newWarnings.push(
          "Modo AgregaÃ§Ã£o: filtros e outros modos desabilitados automaticamente"
        );
        newDisabledFields.add("Enable Entity Filter");
        newDisabledFields.add("Entity Filter Mode");
        newDisabledFields.add("Two-Phase Search Mode");
        newDisabledFields.add("Enable Multi-Vector Search");
      }

      // REGRA 3: Multi-Vector requer Named Vectors (aviso apenas, nÃ£o desabilita aqui)
      if (adjusted["Enable Multi-Vector Search"]?.value) {
        // VerificaÃ§Ã£o seria feita no backend, aqui apenas aviso
        // newWarnings.push("Multi-Vector Search requer Enable Named Vectors (global)");
      }

      return { adjusted, warnings: newWarnings, disabledFields: newDisabledFields };
    },
    []
  );

  // Aplicar validaÃ§Ã£o quando config muda
  useEffect(() => {
    if (RAGConfig?.Retriever) {
      const selected = RAGConfig.Retriever.selected;
      const component = RAGConfig.Retriever.components[selected];
      if (component?.config) {
        const { warnings: newWarnings, disabledFields: newDisabled } =
          validateAndAdjust(component.config);
        setWarnings(newWarnings);
        setDisabledFields(newDisabled);
      }
    }
  }, [RAGConfig, validateAndAdjust]);

  // Carrega presets ao montar componente
  useEffect(() => {
    if (!credentials) return;

    const loadPresets = async () => {
      setLoadingPresets(true);
      setPresetsError(null);
      try {
        const data = await fetchRerankerPresets(credentials);
        if (data && data.presets) {
          setRerankerPresets(data.presets);
        }
        if (data && data.error) {
          setPresetsError(data.error);
        }
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : "Erro desconhecido ao carregar presets";
        console.error("Error loading presets:", error);
        setPresetsError(errorMsg);
      } finally {
        setLoadingPresets(false);
      }
    };
    loadPresets();
  }, [credentials]);

  // Detecta preset atual do config
  useEffect(() => {
    if (RAGConfig?.Retriever) {
      const selected = RAGConfig.Retriever.selected;
      const component = RAGConfig.Retriever.components[selected];
      const presetConfig = component?.config?.["Reranker Preset"];
      if (presetConfig) {
        const presetValue = typeof presetConfig.value === "string" ? presetConfig.value : "auto";
        setSelectedPreset(presetValue);
      }
    }
  }, [RAGConfig]);

  const handlePresetChange = async (presetName: string) => {
    if (blocked || !credentials) return;

    setSelectedPreset(presetName);

    try {
      const result = await applyRerankerPreset(
        presetName,
        currentQuery || null,
        credentials
      );

      if (result && result.status === 200) {
        // Recarrega RAG config para refletir mudanÃ§as
        window.location.reload();
      } else {
        console.error("Failed to apply preset:", result?.status_msg);
      }
    } catch (error) {
      console.error("Error applying preset:", error);
    }
  };

  const renderConfigOptions = (configKey: string) => {
    const selected = RAGConfig.Retriever.selected;
    const component = RAGConfig.Retriever.components[selected];
    if (!component?.config[configKey]) return null;

    return component.config[configKey].values.map((configValue) => (
      <li
        key={"ConfigValue" + configValue}
        className="text-sm"
        onClick={() => {
          if (!blocked) {
            updateConfig("Retriever", configKey, configValue);
          }
        }}
      >
        <a>{configValue}</a>
      </li>
    ));
  };

  const renderConfigField = (configTitle: string, config: ConfigSetting) => {
    const isDisabled = disabledFields.has(configTitle);
    const hasWarning = warnings.some((w) => w.includes(configTitle));

    // Mensagem de ajuda para campos desabilitados
    const getDisabledMessage = () => {
      if (!isDisabled) return null;
      const selected = RAGConfig.Retriever.selected;
      const component = RAGConfig.Retriever.components[selected];
      const twoPhase = component?.config["Two-Phase Search Mode"];
      const aggregation = component?.config["Enable Aggregation"];

      if (configTitle === "Enable Entity Filter" || configTitle === "Entity Filter Mode") {
        if (twoPhase?.value && twoPhase.value !== "disabled") {
          return "Desabilite 'Two-Phase Search Mode' no bloco 'Arquitetura de Busca' para ativar";
        }
        if (aggregation?.value) {
          return "Desabilite 'Enable Aggregation' no bloco 'Arquitetura de Busca' para ativar";
        }
      }
      return null;
    };

    const disabledMessage = getDisabledMessage();

    return (
      <div key={"Configuration" + configTitle} className="mb-4">
        {/* Field Label and Input */}
        <div className="flex gap-3 justify-between items-start text-text-verba lg:text-base text-sm">
          <p className="flex min-w-[8vw] mt-1">{configTitle}</p>

          {/* Dropdown */}
          {config.type === "dropdown" && (
            <div className="dropdown dropdown-bottom flex justify-start items-center w-full">
              <button
                tabIndex={0}
                role="button"
                disabled={blocked || isDisabled}
                className={`btn bg-button-verba hover:bg-button-hover-verba text-text-verba w-full flex justify-start border-none ${isDisabled ? "opacity-50 cursor-not-allowed" : ""
                  }`}
              >
                <GoTriangleDown size={15} />
                <p className="truncate">{config.value}</p>
              </button>
              <ul
                tabIndex={0}
                className="dropdown-content menu bg-base-100 max-h-[20vh] overflow-auto rounded-box z-[1] w-full p-2 shadow"
              >
                {renderConfigOptions(configTitle)}
              </ul>
            </div>
          )}

          {/* Text/Number Input */}
          {typeof config.value !== "boolean" &&
            ["text", "number", "password"].includes(config.type) && (
              <label
                className={`input flex text-sm items-center gap-2 w-full bg-bg-verba ${isDisabled ? "opacity-50 cursor-not-allowed" : ""
                  }`}
              >
                <input
                  type={config.type}
                  className="grow w-full"
                  value={config.value}
                  disabled={blocked || isDisabled}
                  onChange={(e) => {
                    if (!blocked && !isDisabled) {
                      updateConfig("Retriever", configTitle, e.target.value);
                    }
                  }}
                />
              </label>
            )}

          {/* Checkbox Input */}
          {config.type === "bool" && (
            <div className="flex gap-3 justify-start items-center w-full">
              <input
                type="checkbox"
                className="checkbox checkbox-md mt-1"
                disabled={blocked || isDisabled}
                onChange={(e) => {
                  if (!blocked && !isDisabled) {
                    updateConfig(
                      "Retriever",
                      configTitle,
                      (e.target as HTMLInputElement).checked
                    );
                  }
                }}
                checked={
                  typeof config.value === "boolean" ? config.value : false
                }
              />
              <p className="lg:text-sm text-xs text-text-alt-verba text-start flex-1">
                {config.description}
              </p>
            </div>
          )}
        </div>

        {/* Description - Always visible (except for bool which has inline) */}
        {config.type !== "bool" && config.description && (
          <div className="flex gap-2 items-start text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-text-alt-verba text-start bg-bg-verba/40 p-2 rounded italic">
              ðŸ’¡ {config.description}
            </p>
          </div>
        )}

        {/* Warning */}
        {hasWarning && (
          <div className="flex gap-2 items-start text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-warning-verba text-start bg-warning-verba/10 p-2 rounded">
              âš ï¸ {warnings.find((w) => w.includes(configTitle))}
            </p>
          </div>
        )}

        {/* Disabled Help Message */}
        {isDisabled && disabledMessage && (
          <div className="flex gap-2 items-start text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-text-alt-verba italic text-start bg-button-verba/10 p-2 rounded">
              ðŸ”’ {disabledMessage}
            </p>
          </div>
        )}
      </div>
    );
  };

  const renderBlock = (block: ConfigBlock) => {
    const selected = RAGConfig.Retriever.selected;
    const component = RAGConfig.Retriever.components[selected];
    if (!component?.config) return null;

    // Verificar condiÃ§Ã£o do bloco
    if (block.condition && !block.condition(component.config)) {
      return null;
    }

    const blockConfigs = block.configs
      .map((configName) => ({
        name: configName,
        config: component.config[configName],
      }))
      .filter((item) => item.config !== undefined);

    if (blockConfigs.length === 0) return null;

    // Determinar modo ativo para bloco "search_mode"
    const getActiveMode = () => {
      if (block.name !== "search_mode") return null;
      const twoPhase = component.config["Two-Phase Search Mode"];
      const aggregation = component.config["Enable Aggregation"];

      if (aggregation?.value) return "Aggregation";
      if (twoPhase?.value && twoPhase.value !== "disabled") return "Two-Phase";
      return "PadrÃ£o";
    };

    const activeMode = getActiveMode();
    const isExpanded = expandedBlocks.has(block.name);
    const isCollapsible = block.collapsible !== false && (blockConfigs.length > 3 || block.collapsible);

    // Color coding por prioridade
    const priorityColors = {
      critical: "bg-bg-alt-verba border-l-4 border-button-verba",
      important: "bg-bg-alt-verba border-l-4 border-button-verba/60",
      advanced: "bg-bg-verba/30 border-l-4 border-button-verba/30",
    };

    const bgColor = priorityColors[block.priority || "important"] || priorityColors.important;

    return (
      <div key={block.name} className={`mb-4 p-4 rounded-lg ${bgColor} transition-all`}>
        <div className="mb-4">
          {/* Header com toggle para collapse */}
          <div className="flex items-center justify-between cursor-pointer"
            onClick={() => isCollapsible && toggleBlock(block.name)}>
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-text-verba">
                {block.title}
                {block.priority === "advanced" && (
                  <span className="ml-2 text-xs bg-button-verba/20 px-2 py-1 rounded">
                    AvanÃ§ado
                  </span>
                )}
              </h3>
              <p className="text-sm text-text-alt-verba">{block.description}</p>
            </div>
            {isCollapsible && (
              <button
                className={`text-text-verba transition-transform ml-2 ${isExpanded ? "" : "-rotate-90"}`}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleBlock(block.name);
                }}
              >
                <GoTriangleDown size={20} />
              </button>
            )}
          </div>

          {/* Status ativo para Modo de Busca */}
          {activeMode && (
            <div className="mt-3 p-2 bg-button-verba/20 rounded text-xs text-text-verba">
              <strong>ðŸŽ¯ Modo Ativo:</strong> {activeMode}
              {activeMode === "PadrÃ£o" && " (Entity Filter + Semantic Search)"}
              {activeMode === "Two-Phase" && " (Two-Phase Search)"}
              {activeMode === "Aggregation" && " (AnÃ¡lise EstatÃ­stica)"}
            </div>
          )}
        </div>

        {/* ConteÃºdo - colapsÃ¡vel */}
        {(!isCollapsible || isExpanded) && (
          <div className="space-y-3">
            {blockConfigs.map(({ name, config }) => renderConfigField(name, config))}
          </div>
        )}

        {/* Indicador de collapse */}
        {isCollapsible && !isExpanded && (
          <div className="text-xs text-text-alt-verba italic text-center py-2">
            Clique para expandir ({blockConfigs.length} campo{blockConfigs.length !== 1 ? 's' : ''})
          </div>
        )}
      </div>
    );
  };

  if (!RAGConfig?.Retriever) return null;

  const selected = RAGConfig.Retriever.selected;
  const component = RAGConfig.Retriever.components[selected];


  return null;
};

export default RetrieverConfigBlocks;
