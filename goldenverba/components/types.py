from pydantic import BaseModel
from typing import Literal, Union, Optional, List, Dict, Any


class InputConfig(BaseModel):
    type: Literal["number", "text", "dropdown", "password", "bool", "multi", "textarea"]
    value: Union[int, str, bool]
    description: str
    values: list[str]
    # Campos opcionais para hierarquia e validação
    disabled_by: Optional[List[str]] = None  # Lista de flags que desabilitam este
    disables: Optional[List[str]] = None  # Lista de flags que este desabilita
    block: Optional[str] = None  # Nome do bloco (para agrupamento na UI)
    requires: Optional[Dict[str, Any]] = None  # Requisitos (ex: {"global": "Enable Named Vectors"})
    warning: Optional[str] = None  # Mensagem de aviso quando ativado
