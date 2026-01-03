"use client";

import React, { useState, useEffect, useCallback } from "react";
import { GoTriangleDown } from "react-icons/go";
import { RAGConfig, RAGComponentConfig, ConfigSetting, Credentials, RerankerPreset } from "@/app/types";
import VerbaButton from "../Navigation/VerbaButton";
import { fetchRerankerPresets, fetchPresetConfig } from "@/app/api";

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
  setRAGConfig?: (config: RAGConfig) => void;  // Para aplicar preset via backend
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

  // 1. ARQUITETURA - Decisão mais importante
  {
    name: "search_mode",
    title: "🏗️ Arquitetura de Busca",
    description: "Escolha como a busca será executada (mutuamente exclusivos)",
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

  // 2. FUNDAMENTOS - Parâmetros principais
  {
    name: "fundamental",
    title: "⚙️ Busca Fundamental",
    description: "Parâmetros principais de busca e reranking",
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
    title: "🔍 Filtros",
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

  // 4. OTIMIZAÇÕES - Melhorias (avançado)
  {
    name: "optimizations",
    title: "⚡ Otimizações",
    description: "Melhorias opcionais de performance e qualidade (usuários avançados)",
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
    title: "🎯 Reranker - Configuração Básica",
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
    title: "🎯 Reranker - Haystack",
    description: "Configurações específicas do Haystack",
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
    title: "🎯 Reranker - Cohere",
    description: "Configurações específicas do Cohere",
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
    title: "🎯 Reranker - Jina",
    description: "Configurações específicas do Jina",
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
    title: "🎯 Reranker - VoyageAI",
    description: "Configurações específicas do VoyageAI",
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
    title: "🎯 Reranker - ContextualAI",
    description: "Configurações específicas do ContextualAI",
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
  setRAGConfig,
}) => {
  const [warnings, setWarnings] = useState<string[]>([]);
  const [disabledFields, setDisabledFields] = useState<Set<string>>(new Set());
  const [rerankerPresets, setRerankerPresets] = useState<RerankerPreset[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<RerankerPreset | null>(null);
  const [loadingPresets, setLoadingPresets] = useState(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);

  // Debug log para presets
  console.log(`🔧 RetrieverConfigBlocks: selected="${RAGConfig.Retriever.selected}", presets=${rerankerPresets.length}, showPresets=${RAGConfig.Retriever.selected === "EntityAware"}`);


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

  // Validação e auto-ajuste no cliente
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
          "Modo Agregação: filtros e outros modos desabilitados automaticamente"
        );
        newDisabledFields.add("Enable Entity Filter");
        newDisabledFields.add("Entity Filter Mode");
        newDisabledFields.add("Two-Phase Search Mode");
        newDisabledFields.add("Enable Multi-Vector Search");
      }

      // REGRA 3: Multi-Vector requer Named Vectors (aviso apenas, não desabilita aqui)
      if (adjusted["Enable Multi-Vector Search"]?.value) {
        // Verificação seria feita no backend, aqui apenas aviso
        // newWarnings.push("Multi-Vector Search requer Enable Named Vectors (global)");
      }

      return { adjusted, warnings: newWarnings, disabledFields: newDisabledFields };
    },
    []
  );

  // Aplicar validação quando config muda
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
      if (presetConfig && typeof presetConfig.value === "string") {
        const presetName = presetConfig.value;
        const matchedPreset = rerankerPresets.find((p: RerankerPreset) => p.name === presetName);
        setSelectedPreset(matchedPreset || null);
      }
    }
  }, [RAGConfig, rerankerPresets]);

  const handlePresetChange = async (preset: RerankerPreset) => {
    if (blocked) return;

    setSelectedPreset(preset);
    setLoadingPresets(true);
    setPresetsError(null);

    try {
      if (!setRAGConfig) {
        throw new Error("setRAGConfig não disponível");
      }
      if (!credentials) {
        throw new Error("Credentials não disponível");
      }

      console.log(`🔄 Aplicando preset "${preset.name}" via backend...`);
      const result = await fetchPresetConfig(preset.name, credentials);

      if (!result) {
        throw new Error("Sem resposta do backend");
      }

      if (result.status !== 200) {
        throw new Error(result.status_msg || `Erro ${result.status}`);
      }

      if (!result.rag_config) {
        throw new Error("Backend não retornou rag_config");
      }

      setRAGConfig(result.rag_config);
      console.log(`✅ Preset "${preset.display_name || preset.name}" aplicado com sucesso`);

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : "Erro desconhecido";
      console.error(`❌ Erro ao aplicar preset: ${errorMsg}`, error);
      setPresetsError(`Erro ao aplicar preset: ${errorMsg}`);
    } finally {
      setLoadingPresets(false);
    }
  };

  const renderConfigOptions = (configKey: string) => {
    const selected = RAGConfig.Retriever.selected;
    const component = RAGConfig.Retriever.components[selected];
    if (!component?.config?.[configKey]) return null;

    return component.config[configKey].values?.map((configValue) => (
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
              💡 {config.description}
            </p>
          </div>
        )}

        {/* Warning */}
        {hasWarning && (
          <div className="flex gap-2 items-start text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-warning-verba text-start bg-warning-verba/10 p-2 rounded">
              ⚠️ {warnings.find((w) => w.includes(configTitle))}
            </p>
          </div>
        )}

        {/* Disabled Help Message */}
        {isDisabled && disabledMessage && (
          <div className="flex gap-2 items-start text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-text-alt-verba italic text-start bg-button-verba/10 p-2 rounded">
              🔒 {disabledMessage}
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
      return "Padrão";
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
                    Avançado
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
              <strong>🎯 Modo Ativo:</strong> {activeMode}
              {activeMode === "Padrão" && " (Entity Filter + Semantic Search)"}
              {activeMode === "Two-Phase" && " (Two-Phase Search)"}
              {activeMode === "Aggregation" && " (Análise Estatística)"}
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


  return (
    <div className="flex flex-col justify-start gap-3 rounded-2xl p-1 w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="divider text-text-alt-verba flex-grow text-xs lg:text-sm">
          <p>{component?.name || selected} - Busca Configurável</p>
          <VerbaButton
            title="Salvar"
            onClick={() => {
              if (component) {
                saveComponentConfig("Retriever", selected, component);
              }
            }}
          />
        </div>
      </div>

      {/* 1. RETRIEVER SELECTION */}
      <div className="flex flex-col gap-2 p-4 bg-bg-alt-verba rounded-lg border-l-4 border-button-verba">
        <div className="flex gap-2 justify-between items-center text-text-verba">
          <p className="flex min-w-[8vw] lg:text-base text-sm font-semibold">🔧 Retriever</p>
          <div className="dropdown dropdown-bottom flex justify-start items-center w-full">
            <button
              tabIndex={0}
              role="button"
              disabled={blocked}
              className="btn bg-button-verba hover:bg-button-hover-verba text-text-verba w-full flex justify-start border-none"
            >
              <GoTriangleDown size={15} />
              <p className="truncate">{selected}</p>
            </button>
            <ul
              tabIndex={0}
              className="dropdown-content menu bg-base-100 rounded-box z-[1] w-full p-2 shadow"
            >
              {Object.entries(RAGConfig.Retriever.components)
                .filter(([key, comp]) => comp.available)
                .map(([key, comp]) => (
                  <li
                    key={"ComponentDropdown_" + comp.name}
                    onClick={() => {
                      if (!blocked) {
                        selectComponent("Retriever", comp.name);
                      }
                    }}
                  >
                    <a>{comp.name}</a>
                  </li>
                ))}
            </ul>
          </div>
        </div>

        <div className="flex gap-2 items-start text-text-verba">
          <p className="flex min-w-[8vw]"></p>
          <p className="lg:text-sm text-xs text-text-alt-verba text-start bg-bg-verba/40 p-2 rounded italic flex-1">
            💡 {component?.description || "Selecione um retriever"}
          </p>
        </div>
      </div>

      {/* 2. PRESETS UNIFICADOS - Só aparece quando EntityAware está selecionado */}
      {selected === "EntityAware" && (
        <div className="flex flex-col gap-2 p-4 bg-bg-alt-verba rounded-lg border-l-4 border-secondary-verba">
          <div className="flex gap-2 justify-between items-center text-text-verba">
            <p className="flex min-w-[8vw] lg:text-base text-sm font-semibold">★ Presets de Busca</p>

            <div className="flex flex-grow gap-2 items-center">
              {loadingPresets ? (
                <div className="flex items-center gap-2 text-text-alt-verba text-sm">
                  <span className="loading loading-spinner loading-xs"></span>
                  Carregando presets...
                </div>
              ) : presetsError ? (
                <div className="text-warning-verba text-sm italic flex-grow">
                  {presetsError}
                </div>
              ) : rerankerPresets.length === 0 ? (
                <div className="text-text-alt-verba text-sm italic flex-grow">
                  Nenhum preset disponível.
                </div>
              ) : (
                <div className="dropdown dropdown-bottom flex justify-start items-center w-full">
                  <button
                    tabIndex={0}
                    role="button"
                    disabled={blocked}
                    className="btn bg-button-verba hover:bg-button-hover-verba text-text-verba w-full flex justify-start border-none"
                  >
                    <GoTriangleDown size={15} />
                    <p className="truncate">
                      {selectedPreset ? (selectedPreset.display_name || selectedPreset.name) : "Selecionar Preset..."}
                    </p>
                  </button>
                  <ul
                    tabIndex={0}
                    className="dropdown-content menu bg-base-100 rounded-box z-[1] w-full p-2 shadow max-h-60 overflow-y-auto"
                  >
                    {rerankerPresets.map((preset) => (
                      <li
                        key={"Preset_" + preset.name}
                        onClick={() => {
                          if (!blocked) {
                            setSelectedPreset(preset);
                          }
                        }}
                      >
                        <a>
                          <span className="font-bold">{preset.display_name || preset.name}</span>
                          {preset.description && (
                            <span className="text-xs opacity-70 ml-2"> - {preset.description}</span>
                          )}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {selectedPreset && !presetsError && !loadingPresets && (
                <VerbaButton
                  title="Aplicar"
                  disabled={blocked}
                  onClick={() => {
                    handlePresetChange(selectedPreset);
                  }}
                />
              )}
            </div>
          </div>

          <div className="flex gap-2 items-start text-text-verba">
            <p className="flex min-w-[8vw]"></p>
            <p className="lg:text-sm text-xs text-text-alt-verba text-start bg-bg-verba/40 p-2 rounded italic flex-1">
              💡 {selectedPreset ? selectedPreset.description : "Escolha uma configuração otimizada"}
            </p>
          </div>
        </div>
      )}

      {/* 3. WARNINGS */}
      {
        warnings.length > 0 && (
          <div className="p-3 bg-warning-verba/20 rounded-lg border border-warning-verba/50">
            <p className="text-sm font-semibold text-warning-verba mb-2">
              ⚠️ Avisos de Configuração:
            </p>
            <ul className="list-disc list-inside text-xs text-text-verba space-y-1">
              {warnings.map((warning, idx) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        )
      }

      {/* 4. CONFIG BLOCKS */}
      <div className="space-y-2">
        {BLOCKS.map((block) => renderBlock(block))}
      </div>
    </div>
  );
};

export default RetrieverConfigBlocks;
