"use client";

import React from "react";
import { ChunkScore, Message } from "@/app/types";
import ReactMarkdown from "react-markdown";
import { FaDatabase } from "react-icons/fa";
import { BiError } from "react-icons/bi";
import { IoNewspaper } from "react-icons/io5";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { IoDocumentAttach } from "react-icons/io5";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";

import VerbaButton from "../Navigation/VerbaButton";

import { Theme } from "@/app/types";

interface ChatMessageProps {
  message: Message;
  message_index: number;
  selectedTheme: Theme;
  selectedDocument: string | null;
  setSelectedDocument: (s: string | null) => void;
  setSelectedDocumentScore: (s: string | null) => void;
  setSelectedChunkScore: (s: ChunkScore[]) => void;
}

const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  selectedTheme,
  selectedDocument,
  setSelectedDocument,
  message_index,
  setSelectedDocumentScore,
  setSelectedChunkScore,
}) => {
  const colorTable = {
    user: "bg-bg-verba",
    system: "bg-bg-alt-verba",
    error: "bg-warning-verba",
    retrieval: "bg-bg-verba",
  };

  if (typeof message.content === "string") {
    return (
      <div
        className={`flex items-end gap-2 ${message.type === "user" ? "justify-end" : "justify-start"}`}
      >
        <div
          className={`flex flex-col items-start p-5 rounded-3xl animate-press-in text-sm lg:text-base ${colorTable[message.type]}`}
        >
          {message.cached && (
            <FaDatabase size={12} className="text-text-verba" />
          )}
          {message.type === "system" && (
            <ReactMarkdown
              className="prose md:prose-sm lg:prose-base p-3 prose-pre:bg-bg-alt-verba"
              components={{
                code({ node, inline, className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || "");
                  return !inline && match ? (
                    <SyntaxHighlighter
                      style={
                        selectedTheme.theme === "dark"
                          ? (oneDark as any)
                          : (oneLight as any)
                      }
                      language={match[1]}
                      PreTag="div"
                      {...props}
                    >
                      {String(children).replace(/\n$/, "")}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          )}
          {message.type === "user" && (
            <div className="whitespace-pre-wrap">{message.content}</div>
          )}
          {message.type === "error" && (
            <div className="whitespace-pre-wrap flex items-center gap-2 text-sm text-text-verba">
              <BiError size={15} />
              <p>{message.content}</p>
            </div>
          )}
        </div>
      </div>
    );
  } else {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 w-full items-center">
        {message.content.map((document, index) => (
          <button
            onClick={() => {
              setSelectedDocument(document.uuid);
              setSelectedDocumentScore(
                document.uuid + document.score + document.chunks.length
              );
              setSelectedChunkScore(document.chunks);
            }}
            key={"Retrieval" + document.title + index}
            className={`flex ${selectedDocument && selectedDocument === document.uuid + document.score + document.chunks.length ? "bg-secondary-verba hover:bg-button-hover-verba" : "bg-button-verba hover:bg-secondary-verba"} rounded-3xl p-3 items-center justify-between transition-colors duration-300 ease-in-out border-none`}
          >
            <div className="flex items-center justify-between w-full">
              <p
                className="text-xs flex-grow truncate mr-2"
                title={document.title}
              >
                {document.title}
              </p>
              <div className="flex gap-1 items-center text-text-verba flex-shrink-0">
                <IoNewspaper size={12} />
                <p className="text-sm">{document.chunks.length}</p>
              </div>
            </div>
          </button>
        ))}
        {message.debug_info && (
          <div className="col-span-full mt-2 p-3 bg-secondary-verba rounded-lg text-xs text-text-alt-verba border border-button-verba">
            <div className="font-semibold mb-2 text-text-verba">🔍 Debug Info</div>
            <div className="space-y-1">
              <div><strong>Query original:</strong> {message.debug_info.original_query}</div>
              {message.debug_info.rewritten_query && (
                <div><strong>Query reescrita:</strong> {message.debug_info.rewritten_query}</div>
              )}
              {message.debug_info.query_builder_used && (
                <div>✅ Query Builder usado</div>
              )}
              {message.debug_info.query_rewriter_used && (
                <div>✅ Query Rewriter usado</div>
              )}
              {message.debug_info.entities_detected && message.debug_info.entities_detected.length > 0 && (
                <div><strong>Entidades:</strong> {message.debug_info.entities_detected.join(", ")}</div>
              )}
              {message.debug_info.semantic_terms && message.debug_info.semantic_terms.length > 0 && (
                <div><strong>Termos semânticos:</strong> {message.debug_info.semantic_terms.join(", ")}</div>
              )}
              {message.debug_info.filters_applied && (
                <div><strong>Filtros:</strong> {message.debug_info.filters_applied.description || "N/A"}</div>
              )}
              {message.debug_info.alpha_used !== undefined && (
                <div><strong>Alpha:</strong> {message.debug_info.alpha_used}</div>
              )}
              {message.debug_info.search_mode && (
                <div><strong>Modo:</strong> {message.debug_info.search_mode}</div>
              )}
              {message.debug_info.explanation && (
                <div><strong>Explicação:</strong> {message.debug_info.explanation}</div>
              )}
            </div>
          </div>
        )}
        <VerbaButton
          Icon={IoDocumentAttach}
          className="btn-sm btn-square"
          onClick={() =>
            (
              document.getElementById(
                "context-modal-" + message_index
              ) as HTMLDialogElement
            ).showModal()
          }
        />
        <dialog id={"context-modal-" + message_index} className="modal">
          <div className="modal-box">
            <h3 className="font-bold text-lg">Context</h3>
            <p className="py-4">{message.context}</p>
            <div className="modal-action">
              <form method="dialog">
                <button className="btn focus:outline-none text-text-alt-verba bg-button-verba hover:bg-button-hover-verba hover:text-text-verba border-none shadow-none">
                  <p>Close</p>
                </button>
              </form>
            </div>
          </div>
        </dialog>
      </div>
    );
  }
};

export default ChatMessage;
