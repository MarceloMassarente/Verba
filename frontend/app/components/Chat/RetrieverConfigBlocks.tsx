"use client";

import React, { useState, useEffect, useCallback } from "react";
import { GoTriangleDown } from "react-icons/go";
import { RAGConfig, RAGComponentConfig, ConfigSetting } from "@/app/types";
import VerbaButton from "../Navigation/VerbaButton";

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
}

interface ConfigBlock {
  name: string;
  title: string;
  description: string;
  configs: string[];
  mode?: "radio" | "checkbox";
}

const BLOCKS: ConfigBlock[] = [
  {
    name: "fundamental",
    title: "Busca Fundamental",
    description: "Configurações básicas de busca",
    configs: [
      "Search Mode",
      "Limit Mode",
      "Limit/Sensitivity",
      "Alpha",
      "Reranker Top K",
    ],
  },
  {
    name: "filters",
    title: "Filtros",
    description: "Filtros independentes que podem ser combinados",
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
  {
    name: "search_mode",
    title: "Modo de Busca",
    description: "Escolha o modo de busca (mutuamente exclusivos)",
    mode: "radio",
    configs: ["Two-Phase Search Mode", "Enable Multi-Vector Search", "Enable Aggregation"],
  },
  {
    name: "optimizations",
    title: "Otimizações",
    description: "Melhorias opcionais de performance e qualidade",
    configs: [
      "Enable Query Expansion",
      "Enable Dynamic Alpha",
      "Enable Relative Score Fusion",
      "Enable Query Rewriting",
      "Query Rewriter Cache TTL",
      "Chunk Window",
    ],
  },
];

const RetrieverConfigBlocks: React.FC<RetrieverConfigBlocksProps> = ({
  RAGConfig,
  blocked,
  selectComponent,
  updateConfig,
  saveComponentConfig,
}) => {
  const [warnings, setWarnings] = useState<string[]>([]);
  const [disabledFields, setDisabledFields] = useState<Set<string>>(new Set());

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
          return "Desabilite 'Two-Phase Search Mode' no bloco 'Modo de Busca' para ativar";
        }
        if (aggregation?.value) {
          return "Desabilite 'Enable Aggregation' no bloco 'Modo de Busca' para ativar";
        }
      }
      return null;
    };
    
    const disabledMessage = getDisabledMessage();

    return (
      <div key={"Configuration" + configTitle} className="mb-4">
        <div className="flex gap-3 justify-between items-center text-text-verba lg:text-base text-sm">
          <p className="flex min-w-[8vw]">{configTitle}</p>

          {/* Dropdown */}
          {config.type === "dropdown" && (
            <div className="dropdown dropdown-bottom flex justify-start items-center w-full">
              <button
                tabIndex={0}
                role="button"
                disabled={blocked || isDisabled}
                className={`btn bg-button-verba hover:bg-button-hover-verba text-text-verba w-full flex justify-start border-none ${
                  isDisabled ? "opacity-50 cursor-not-allowed" : ""
                }`}
              >
                <GoTriangleDown size={15} />
                <p>{config.value}</p>
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
                className={`input flex text-sm items-center gap-2 w-full bg-bg-verba ${
                  isDisabled ? "opacity-50 cursor-not-allowed" : ""
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
            <div className="flex gap-5 justify-start items-center w-full my-4">
              <p className="lg:text-sm text-xs text-text-alt-verba text-start w-[250px]">
                {config.description}
              </p>
              <input
                type="checkbox"
                className="checkbox checkbox-md"
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
            </div>
          )}
        </div>

        {/* Description */}
        {config.type !== "bool" && (
          <div className="flex gap-2 items-center text-text-verba mt-3">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-text-alt-verba text-start">
              {config.description}
            </p>
          </div>
        )}

        {/* Warning */}
        {hasWarning && (
          <div className="flex gap-2 items-center text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-warning-verba text-start">
              {warnings.find((w) => w.includes(configTitle))}
            </p>
          </div>
        )}
        
        {/* Disabled Help Message */}
        {isDisabled && disabledMessage && (
          <div className="flex gap-2 items-center text-text-verba mt-2">
            <p className="flex min-w-[8vw]"></p>
            <p className="text-xs text-text-alt-verba italic text-start">
              💡 {disabledMessage}
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

    const blockConfigs = block.configs
      .map((configName) => ({
        name: configName,
        config: component.config[configName],
      }))
      .filter((item) => item.config !== undefined);

    if (blockConfigs.length === 0) return null;

    return (
      <div key={block.name} className="mb-6 p-4 bg-bg-alt-verba rounded-lg">
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-text-verba">
            {block.title}
          </h3>
          <p className="text-sm text-text-alt-verba">{block.description}</p>
        </div>

        {blockConfigs.map(({ name, config }) => renderConfigField(name, config))}
      </div>
    );
  };

  if (!RAGConfig?.Retriever) return null;

  const selected = RAGConfig.Retriever.selected;
  const component = RAGConfig.Retriever.components[selected];

  return (
    <div className="flex flex-col justify-start gap-3 rounded-2xl p-1 w-full">
      <div className="flex items-center justify-between">
        <div className="divider text-text-alt-verba flex-grow text-xs lg:text-sm">
          <p>{component?.name || selected} Settings</p>
          <VerbaButton
            title="Save"
            onClick={() => {
              if (component) {
                saveComponentConfig("Retriever", selected, component);
              }
            }}
          />
        </div>
      </div>

      {/* Component Selector */}
      <div className="flex flex-col gap-2">
        <div className="flex gap-2 justify-between items-center text-text-verba">
          <p className="flex min-w-[8vw] lg:text-base text-sm">Retriever</p>
          <div className="dropdown dropdown-bottom flex justify-start items-center w-full">
            <button
              tabIndex={0}
              role="button"
              disabled={blocked}
              className="btn bg-button-verba hover:bg-button-hover-verba text-text-verba w-full flex justify-start border-none"
            >
              <GoTriangleDown size={15} />
              <p>{selected}</p>
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

        <div className="flex gap-2 items-center text-text-verba">
          <p className="flex min-w-[8vw]"></p>
          <p className="lg:text-sm text-xs text-text-alt-verba text-start">
            {component?.description || ""}
          </p>
        </div>
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="p-3 bg-warning-verba/20 rounded-lg border border-warning-verba/50">
          <p className="text-sm font-semibold text-warning-verba mb-2">
            Avisos de Configuração:
          </p>
          <ul className="list-disc list-inside text-xs text-text-verba">
            {warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Render Blocks */}
      {BLOCKS.map((block) => renderBlock(block))}
    </div>
  );
};

export default RetrieverConfigBlocks;

