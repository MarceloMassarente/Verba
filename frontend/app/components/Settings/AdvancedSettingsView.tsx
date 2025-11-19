"use client";

import React, { useState, useEffect } from "react";
import { Credentials, RAGConfig } from "@/app/types";
import { updateRAGConfig, fetchRAGConfig } from "@/app/api";
import VerbaButton from "../Navigation/VerbaButton";
import { IoSettingsSharp } from "react-icons/io5";
import { MdCancel } from "react-icons/md";

interface AdvancedSettingsViewProps {
  credentials: Credentials;
  RAGConfig: RAGConfig | null;
  setRAGConfig: React.Dispatch<React.SetStateAction<RAGConfig | null>>;
  addStatusMessage: (
    message: string,
    type: "INFO" | "WARNING" | "SUCCESS" | "ERROR"
  ) => void;
}

const AdvancedSettingsView: React.FC<AdvancedSettingsViewProps> = ({
  credentials,
  RAGConfig,
  setRAGConfig,
  addStatusMessage,
}) => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [hasChanges, setHasChanges] = useState<boolean>(false);

  useEffect(() => {
    if (!RAGConfig) {
      loadConfig();
    }
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const response = await fetchRAGConfig(credentials);
      if (response && response.rag_config) {
        setRAGConfig(response.rag_config);
      }
    } catch (error) {
      addStatusMessage("Failed to load configuration", "ERROR");
    } finally {
      setIsLoading(false);
    }
  };

  const updateAdvancedSetting = (settingKey: string, value: boolean) => {
    if (!RAGConfig) return;

    setRAGConfig((prevRAGConfig) => {
      if (prevRAGConfig && (prevRAGConfig as any)["Advanced"]) {
        const newRAGConfig = { ...prevRAGConfig } as any;
        if (newRAGConfig["Advanced"] && newRAGConfig["Advanced"][settingKey]) {
          newRAGConfig["Advanced"][settingKey] = {
            ...newRAGConfig["Advanced"][settingKey],
            value: value,
          };
        }
        return newRAGConfig;
      }
      return prevRAGConfig;
    });
    setHasChanges(true);
  };

  const saveConfig = async () => {
    if (!RAGConfig) return;

    setIsLoading(true);
    try {
      const response = await updateRAGConfig(RAGConfig, credentials);
      if (response) {
        addStatusMessage("Advanced settings saved successfully", "SUCCESS");
        setHasChanges(false);
      } else {
        addStatusMessage("Failed to save advanced settings", "ERROR");
      }
    } catch (error) {
      addStatusMessage("Failed to save advanced settings", "ERROR");
    } finally {
      setIsLoading(false);
    }
  };

  const resetConfig = () => {
    loadConfig();
    setHasChanges(false);
    addStatusMessage("Configuration reset", "INFO");
  };

  if (isLoading && !RAGConfig) {
    return (
      <div className="flex justify-center items-center h-full">
        <span className="loading loading-spinner loading-lg"></span>
      </div>
    );
  }

  const advancedConfig = (RAGConfig as any)?.["Advanced"];

  if (!RAGConfig || !advancedConfig) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <p className="text-lg font-bold text-text-verba">
          Advanced Settings
        </p>
        <p className="text-text-alt-verba">
          No advanced settings available. Please ensure the configuration is loaded.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full h-full p-4">
      <div className="flex justify-between items-center mb-4">
        <p className="text-2xl font-bold text-text-verba">Advanced Settings</p>
        <div className="flex gap-2">
          <VerbaButton
            title="Save"
            onClick={saveConfig}
            disabled={!hasChanges || isLoading}
            loading={isLoading}
            Icon={IoSettingsSharp}
          />
          <VerbaButton
            title="Reset"
            onClick={resetConfig}
            disabled={!hasChanges || isLoading}
            Icon={MdCancel}
          />
        </div>
      </div>

      <div className="flex-grow overflow-y-auto">
        <div className="gap-4 flex flex-col p-4 text-text-verba">
          <p className="font-bold text-lg">Weaviate Advanced Features</p>

          {Object.entries(advancedConfig).map(([settingKey, setting]: [string, any]) => {
            if (setting.type === "bool") {
              return (
                <div
                  key={settingKey}
                  className="flex flex-col border-2 border-bg-verba shadow-sm p-4 rounded-lg gap-3"
                >
                  <div className="flex justify-between items-center">
                    <div className="flex flex-col gap-1">
                      <p className="text-sm lg:text-base font-semibold text-text-alt-verba">
                        {settingKey}
                      </p>
                      <p className="text-sm text-text-verba">
                        {setting.description}
                      </p>
                    </div>
                    <input
                      type="checkbox"
                      checked={setting.value as boolean}
                      onChange={(e) => updateAdvancedSetting(settingKey, e.target.checked)}
                      className="toggle toggle-primary"
                    />
                  </div>
                  {settingKey === "Enable Named Vectors" && setting.value && (
                    <div className="alert alert-warning mt-2">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="stroke-current shrink-0 h-6 w-6"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2"
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                      </svg>
                      <div>
                        <h3 className="font-bold">Warning</h3>
                        <div className="text-xs">
                          Named vectors can only be added when creating collections.
                          Existing collections will need to be deleted and recreated.
                          This will temporarily remove all data from those collections.
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            }
            return null;
          })}
        </div>
      </div>
    </div>
  );
};

export default AdvancedSettingsView;

