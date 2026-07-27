# ==============================================================================
# API Intermediária ANEEL — Indicadores de Continuidade Coletivos (Base Completa)
# ------------------------------------------------------------------------------
# Hospedagem recomendada : Render.com (free tier)
# Consumo no Power BI    : Web.Contents no Power Query (retorna CSV)
# Cache                  : Em disco, expira a cada 24 horas
# ==============================================================================

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
import requests
import zipfile
import urllib3
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings()

app = FastAPI(
    title="API ANEEL - Indicadores de Continuidade",
    description="Baixa e disponibiliza os Indicadores de Continuidade Coletivos da ANEEL sem filtros.",
    version="1.0.0",
)

# ------------------------------------------------------------------------------
# Configurações
# ------------------------------------------------------------------------------
URL_ANEEL = "https://dadosabertos.aneel.gov.br/dataset/d5f0712e-62f6-4736-8dff-9991f10758a7/resource/4493985c-baea-429c-9df5-3030422c71d7/download/indicadores-continuidade-coletivos-2020-2029.zip"
CACHE_DURACAO_HORAS = 24
ARQUIVO_CACHE = "indicadores_cache.csv" # Arquivo que ficará salvo no disco do Render

# ------------------------------------------------------------------------------
# Controle de Cache
# ------------------------------------------------------------------------------
_cache: dict = {
    "expira_em": None,
    "ultima_atualizacao": None,
    "erros": [],
}

def _cache_valido() -> bool:
    # O cache só é válido se estiver no prazo E se o arquivo físico existir no disco
    return (
        _cache["expira_em"] is not None
        and datetime.now() < _cache["expira_em"]
        and os.path.exists(ARQUIVO_CACHE)
    )

def _coletar_dados_aneel() -> None:
    erros = []
    
    session = requests.Session()
    retry = Retry(connect=5, read=5, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        # Usa uma pasta temporária apenas para baixar o ZIP
        with tempfile.TemporaryDirectory() as tmpdirname:
            zip_path = os.path.join(tmpdirname, "dados.zip")
            
            # 1. Download do arquivo ZIP
            response = session.get(URL_ANEEL, verify=False, stream=True, timeout=60)
            response.raise_for_status()
            
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        
            # 2. Extrai o CSV direto do ZIP e salva no diretório principal da API
            with zipfile.ZipFile(zip_path, 'r') as z:
                nome_arquivo = z.namelist()[0]
                
                # Copia os dados do ZIP para o nosso ARQUIVO_CACHE físico em disco
                with z.open(nome_arquivo) as source, open(ARQUIVO_CACHE, "wb") as target:
                    shutil.copyfileobj(source, target)

    except Exception as e:
        erros.append(str(e))

    # Atualiza o status do cache
    if os.path.exists(ARQUIVO_CACHE):
        _cache["expira_em"] = datetime.now() + timedelta(hours=CACHE_DURACAO_HORAS)
        _cache["ultima_atualizacao"] = datetime.now().isoformat()
    _cache["erros"] = erros


# ------------------------------------------------------------------------------
# Endpoints da API
# ------------------------------------------------------------------------------

@app.get("/", summary="Página Inicial")
def raiz():
    return {
        "status": "API ANEEL (Indicadores Coletivos) rodando!", 
        "instrucao": "Use o endpoint /dados no Power BI para obter o CSV."
    }

@app.get(
    "/dados",
    response_class=FileResponse,
    summary="Retorna o arquivo CSV completo",
    description="Use este endpoint no Power BI via Web.Contents.",
)
def get_dados():
    # Verifica se precisa baixar novamente
    if not _cache_valido():
        _coletar_dados_aneel()

    # Se mesmo após tentar baixar o arquivo não existir, retorna erro
    if not os.path.exists(ARQUIVO_CACHE):
        return Response(
            content="Nenhum dado disponível. A conexão com a ANEEL pode ter falhado.",
            status_code=503,
            media_type="text/plain",
        )

    # Transmite o arquivo CSV direto do disco (Gasto de RAM = Quase zero!)
    return FileResponse(
        path=ARQUIVO_CACHE,
        media_type="text/csv",
        filename="indicadores_continuidade.csv"
    )

@app.get("/status", summary="Status do cache e da última coleta")
def get_status():
    return {
        "cache_valido": _cache_valido(),
        "ultima_atualizacao": _cache["ultima_atualizacao"],
        "expira_em": _cache["expira_em"].isoformat() if _cache["expira_em"] else None,
        "tamanho_arquivo_mb": round(os.path.getsize(ARQUIVO_CACHE) / (1024 * 1024), 2) if os.path.exists(ARQUIVO_CACHE) else 0,
        "erros_na_ultima_coleta": _cache["erros"],
    }
